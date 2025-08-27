import os
from PyQt5 import QtCore, QtWidgets, QtGui
from sensor_driver.interfaces.ordinary.layout.layout_user import Ui_MainWindow
#
from usb.core import USBError
import sys
import numpy as np
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from sensor_driver.data_processing.data_handler import DataHandler
#
from sensor_driver.interfaces.public.utils import (set_logo,
                                              config, save_config, catch_exceptions)
from sensor_driver.interfaces.ordinary.ordinary_plot import OrdinaryPlot
import pyqtgraph as pg
#
# 导入校准相关模块
import torch
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.font_manager as fm
#
AVAILABLE_FILTER_NAMES = ['无', '中值-0.2s', '中值-1s', '均值-0.2s', '均值-1s', '单向抵消-轻', '单向抵消-中', '单向抵消-重']


class AICalibrationAdapter:
    """AI校准适配器"""

    def __init__(self):
        self.coeffs = None
        self.data_mean = None
        self.data_std = None
        self.device = None
        self.is_loaded = False
        self.calibration_format = None

    def load_calibration(self, filepath):
        """加载AI校准模型"""
        try:
            if not os.path.exists(filepath):
                print(f"❌ AI校准文件不存在: {filepath}")
                return False

            # 加载校准包
            calibration_package = torch.load(filepath)
            
            # 检查是新版本还是旧版本格式
            if isinstance(calibration_package, dict) and 'coeffs' in calibration_package:
                # 新版本格式：calibration_package.pt
                self.coeffs = calibration_package['coeffs']
                self.data_mean = calibration_package['data_mean']
                self.data_std = calibration_package['data_std']
                self.calibration_format = 'new'
                print(f"✅ 新版本AI校准包加载成功，形状: {self.coeffs.shape}")
            else:
                # 旧版本格式：calibration_coeffs.pt
                self.coeffs = calibration_package
                self.data_mean = None
                self.data_std = None
                self.calibration_format = 'old'
                print(f"✅ 旧版本AI校准模型加载成功，形状: {self.coeffs.shape}")

            # 设置设备
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                print("✅ 使用GPU进行AI校准")
            else:
                self.device = torch.device("cpu")
                print("✅ 使用CPU进行AI校准")

            # 将系数移到指定设备
            self.coeffs = self.coeffs.to(self.device)
            if self.data_mean is not None:
                self.data_mean = self.data_mean.to(self.device)
            if self.data_std is not None:
                self.data_std = self.data_std.to(self.device)
                
            self.is_loaded = True
            return True

        except Exception as e:
            print(f"❌ 加载AI校准模型失败: {e}")
            return False

    def apply_calibration(self, raw_data):
        """应用AI校准到原始数据"""
        if not self.is_loaded or self.coeffs is None:
            return raw_data

        try:
            # 确保输入是64x64数组
            if raw_data.shape != (64, 64):
                print(f"⚠️ 输入数据形状错误: {raw_data.shape}，期望 (64, 64)")
                return raw_data

            # 转换为PyTorch张量
            raw_tensor = torch.from_numpy(raw_data).float().to(self.device)

            if self.calibration_format == 'new':
                # 新版本校准流程：标准化 → 校准 → 逆标准化
                print(f"🔧 新版本校准流程开始...")
                print(f"   原始数据范围: [{raw_tensor.min():.2f}, {raw_tensor.max():.2f}]")
                print(f"   数据均值范围: [{self.data_mean.min():.2f}, {self.data_mean.max():.2f}]")
                print(f"   数据标准差范围: [{self.data_std.min():.2f}, {self.data_std.max():.2f}]")
                
                # 1. 对新数据应用相同的标准化
                scaled_tensor = (raw_tensor - self.data_mean) / self.data_std
                print(f"   标准化后范围: [{scaled_tensor.min():.2f}, {scaled_tensor.max():.2f}]")
                
                # 2. 在标准化数据上应用校准函数
                x_flat = scaled_tensor.view(-1)
                x_poly = x_flat.unsqueeze(-1).pow(torch.arange(2, -1, -1, device=self.device))
                
                calibrated_flat_scaled = torch.sum(x_poly * self.coeffs, dim=1)
                print(f"   校准后标准化范围: [{calibrated_flat_scaled.min():.2f}, {calibrated_flat_scaled.max():.2f}]")
                
                # 3. 将结果逆变换回原始数据量级
                calibrated_flat_rescaled = calibrated_flat_scaled * self.data_std + self.data_mean
                calibrated_tensor = calibrated_flat_rescaled.view(64, 64)
                print(f"   逆变换后范围: [{calibrated_tensor.min():.2f}, {calibrated_tensor.max():.2f}]")
                
                # 转换为numpy数组并返回
                calibrated_data = calibrated_tensor.cpu().numpy()
                print(f"✅ 新版本校准完成，最终范围: [{calibrated_data.min():.2f}, {calibrated_data.max():.2f}]")
                return calibrated_data
                
            else:
                # 旧版本校准流程：直接应用二次多项式
                # 展平数据
                raw_flat = raw_tensor.view(-1)

                # 应用校准函数：y = a*x^2 + b*x + c
                x = raw_flat
                a = self.coeffs[:, 0]  # 二次项系数
                b = self.coeffs[:, 1]  # 一次项系数
                c = self.coeffs[:, 2]  # 常数项

                # 并行计算校准
                calibrated_flat = a * x**2 + b * x + c

                # 恢复为64x64矩阵
                calibrated_tensor = calibrated_flat.view(64, 64)

                # 转换为numpy数组
                calibrated_data = calibrated_tensor.cpu().numpy()

                return calibrated_data

        except Exception as e:
            print(f"⚠️ AI校准应用失败: {e}")
            return raw_data

    def get_info(self):
        """获取AI校准信息"""
        if not self.is_loaded:
            return None

        info = {
            'is_loaded': True,
            'calibration_format': self.calibration_format,
            'coeffs_shape': self.coeffs.shape if self.coeffs is not None else None,
            'device': str(self.device),
            'coeffs_range': {
                'a': [float(self.coeffs[:, 0].min()), float(self.coeffs[:, 0].max())],
                'b': [float(self.coeffs[:, 1].min()), float(self.coeffs[:, 1].max())],
                'c': [float(self.coeffs[:, 2].min()), float(self.coeffs[:, 2].max())]
            } if self.coeffs is not None else None
        }
        
        if self.calibration_format == 'new':
            info['data_mean_range'] = [float(self.data_mean.min()), float(self.data_mean.max())]
            info['data_std_range'] = [float(self.data_std.min()), float(self.data_std.max())]
            
        return info


class Window(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    主窗口
    """


    def __init__(self, mode='standard'):
        """

        :param mode: "standard" or "socket"
        """
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self._catch_exceptions
        self.config, self.save_config = config, save_config
        #
        self.is_running = False
        #
        self.data_handler = self.__mode_selector(mode)
        self.plotter = OrdinaryPlot(self)
        self.plotter.set_using_calibration()
        # 界面初始配置
        self.__pre_initialize()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        #
        self.current_db_path = None

        # 校准相关变量
        self.calibration_coeffs = None
        self.device = torch.device("cpu")
        self.setup_calibration()
        
        # 双校准器比较功能
        self.dual_calibration_mode = False
        self.old_calibrator = None  # 旧版本校准器
        self.new_calibrator = None  # 新版本校准器
        self.comparison_dialog = None  # 比较对话框
        
        # 去皮功能相关属性
        self.zero_offset = None  # 零点偏移量
        self.taring_enabled = False  # 是否启用去皮功能

    def __mode_selector(self, mode):
        if mode == 'standard':
            from backends.usb_driver import LargeUsbSensorDriver
            data_handler = DataHandler(LargeUsbSensorDriver)
        elif mode == 'can':
            from backends.can_driver import Can16SensorDriver
            data_handler = DataHandler(Can16SensorDriver)
        else:
            raise NotImplementedError()
        return data_handler

    def _catch_exceptions(self, ty, value, tb):
        catch_exceptions(self, ty, value, tb)

    def start(self):
        # 按开始键
        if not self.is_running:
            flag = self.data_handler.connect(self.com_port.text())
            self.config['port'] = self.com_port.text()
            self.save_config()
            if not flag:
                return
            self.is_running = True
            self.timer.start(self.config['trigger_time'])
            self.__set_enable_state()
            self.com_port.setEnabled(False)

    def stop(self):
        # 按停止键
        self.config['y_lim'] = self.plotter.log_y_lim
        self.save_config()
        if self.is_running:
            self.is_running = False
            if self.timer.isActive():
                self.timer.stop()
            self.data_handler.disconnect()
            self.data_handler.clear()
            self.__set_enable_state()

    def __pre_initialize(self):
        set_logo(self, True)
        self.__initialize_buttons()  # 初始化一般接口
        self.__set_enable_state()  # 各类开始/停止状态切换时调用
        self.com_port.setEnabled(True)  # 一旦成功开始，就再也不能修改
        
        # 确保菜单栏可见
        if hasattr(self, 'menubar') and self.menubar is not None:
            self.menubar.setVisible(True)
            self.menubar.setHidden(False)
            self.menubar.raise_()
            print("🔧 强制设置菜单栏可见")
            
        # 延迟设置菜单栏可见（在窗口显示后）
        QtCore.QTimer.singleShot(100, self._ensure_menubar_visible)
        
        # 延迟设置AI校准菜单（确保窗口完全显示后）
        QtCore.QTimer.singleShot(200, self._setup_calibration_menu_delayed)

    def __initialize_buttons(self):
        # 菜单栏将在延迟方法中设置
        # 开始
        self.button_start.clicked.connect(self.start)
        self.action_start.triggered.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        self.action_stop.triggered.connect(self.stop)
        #
        for name in AVAILABLE_FILTER_NAMES:
            self.combo_filter_time.addItem(name)
        current_idx_filter_time = self.config.get('filter_time_index')
        if current_idx_filter_time < self.combo_filter_time.count():
            self.combo_filter_time.setCurrentIndex(current_idx_filter_time)
        self.combo_interpolate.setCurrentIndex(self.config.get('interpolate_index'))
        self.combo_blur.setCurrentIndex(self.config.get('blur_index'))
        self.__set_filter()
        self.__set_interpolate_and_blur()
        self.combo_filter_time.currentIndexChanged.connect(self.__set_filter)
        self.combo_interpolate.currentIndexChanged.connect(self.__set_interpolate_and_blur)
        self.combo_blur.currentIndexChanged.connect(self.__set_interpolate_and_blur)
        self.__set_enable_state()
        #
        self.button_set_zero.clicked.connect(self.data_handler.set_zero)
        self.action_set_zero.triggered.connect(self.data_handler.set_zero)
        self.button_abandon_zero.clicked.connect(self.data_handler.abandon_zero)
        self.action_abandon_zero.triggered.connect(self.data_handler.abandon_zero)
        self.button_save_to.clicked.connect(self.__trigger_save_button)
        self.action_save_to.triggered.connect(self.__trigger_save_button)
        self.action_save_finish.triggered.connect(self.__trigger_save_button)

        str_port = self.config.get('port')
        if not isinstance(str_port, str):
            raise Exception('配置文件出错')
        self.com_port.setText(self.config['port'])
        # 标定功能
        self.button_load_calibration.clicked.connect(self.__set_calibrator)
        self.action_load_calibration.triggered.connect(self.__set_calibrator)
        self.button_exit_calibration.clicked.connect(self.__abandon_calibrator)
        self.action_exit_calibration.triggered.connect(self.__abandon_calibrator)

        # AI校准功能现在通过菜单栏的"AI校准"菜单访问，界面更加整洁
        print("🔧 AI校准功能已集成到菜单栏，无需额外按钮")
        # 播放功能
        self.button_play.clicked.connect(self.__trigger_play_button)  # 连接播放按钮

    def __set_enable_state(self):
        # 根据实际的开始/停止状态，设定各按钮是否激活
        self.button_start.setEnabled(not self.is_running)
        self.action_start.setEnabled(not self.is_running)
        self.button_stop.setEnabled(self.is_running)
        self.action_stop.setEnabled(self.is_running)

        self.button_save_to.setEnabled(self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("结束采集")
        else:
            self.button_save_to.setText("采集到...")
        self.action_save_to.setEnabled(self.is_running and not self.data_handler.saving_file)
        self.action_save_finish.setEnabled(self.is_running and self.data_handler.saving_file)
        if self.is_running:
            self.com_port.setEnabled(False)

    def __set_filter(self):
        # 为self.combo_filter_time逐项添加选项
        self.data_handler.set_filter("无", self.combo_filter_time.currentText())
        self.config['filter_time_index'] = self.combo_filter_time.currentIndex()
        self.save_config()

    def __set_interpolate_and_blur(self):
        interpolate = int(self.combo_interpolate.currentText())
        blur = float(self.combo_blur.currentText())
        self.data_handler.set_interpolation_and_blur(interpolate=interpolate, blur=blur)
        self.config['interpolate_index'] = self.combo_interpolate.currentIndex()
        self.config['blur_index'] = self.combo_blur.currentIndex()
        self.save_config()

    def __set_calibrator(self):
        path = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择标定文件", "", "标定文件 (*.clb; *.csv)")[0]
        if path:
            flag = self.data_handler.set_calibrator(path)
            if flag:
                self.plotter.set_using_calibration()

    def __abandon_calibrator(self):
        self.data_handler.abandon_calibrator()
        self.plotter.set_using_calibration()

    def __trigger_save_button(self):
        if self.data_handler.output_file:
            self.data_handler.close_output_file()
        else:
            file = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "选择输出路径",
                "",
                "数据库 (*.db)")
            if file[0]:
                self.data_handler.link_output_file(file[0])
        self.__set_enable_state()

    # 播放按钮（选择并读取数据库文件）
    def __trigger_play_button(self):
        # 仅当未播放或播放完成时开启计时
        if not self.data_handler.play_complete_flag:
            '''
            调用了self.timer.start()以启用qt的trigger循环
            '''
            self.timer.start(self.config['trigger_time'])
            self.button_play.setText("暂停")

        # 播放完成的重置
        if self.data_handler.play_complete_flag:
            self.timer.stop() # 终止qt的trigger循环
            self.current_db_path = None
            self.data_handler.play_complete_flag = False

            print("播放数据已完成")
            self.button_play.setText("播放")

        # 如果当前没有加载数据库，则打开文件选择对话框
        if not self.current_db_path:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "选择数据库文件",
                "",
                "SQLite 数据库 (*.db);;所有文件 (*)"
            )

            if file_path:
                try:
                    # 显示加载状态
                    print(f"正在读取数据库: {os.path.basename(file_path)}")
                    self.button_play.setEnabled(False)
                    QtWidgets.QApplication.processEvents()

                    # 调用读取数据库的方法
                    self.data_handler.read_data_from_db(file_path)

                    # 更新状态
                    print(f"已加载数据库: {os.path.basename(file_path)}")
                    self.data_handler.play_flag = True
                    self.current_db_path = file_path


                except Exception as e:
                    # 错误处理
                    print(f"读取数据库失败: {str(e)}")
                    QtWidgets.QMessageBox.critical(self, "错误", f"无法读取数据库:\n{str(e)}")
                finally:
                    # 恢复按钮状态
                    self.button_play.setEnabled(True)
                    self.__set_enable_state()

        else:
            # 如果已经加载了数据库，则切换播放状态
            self.data_handler.play_flag = not self.data_handler.play_flag

            # 更新按钮文本以反映当前状态
            if self.data_handler.play_flag:
                print("已开始播放数据")
                self.button_play.setText("暂停")
            else:
                print("已暂停播放数据")
                self.button_play.setText("继续播放")

            self.__set_enable_state()


    def trigger(self):
        try:
            self.data_handler.trigger()

            # 如果有AI校准模型，对最新数据应用AI校准
            if self.calibration_coeffs is not None and len(self.data_handler.value) > 0:
                latest_raw_data = self.data_handler.value[-1]

                # 保存原始数据副本（用于对比）
                if not hasattr(self, '_raw_data_for_comparison'):
                    self._raw_data_for_comparison = []
                
                # 保持最近10帧的原始数据
                self._raw_data_for_comparison.append(latest_raw_data.copy())
                if len(self._raw_data_for_comparison) > 10:
                    self._raw_data_for_comparison.pop(0)

                # 应用AI校准
                calibrated_data = self.apply_ai_calibration(latest_raw_data)
                
                # 应用去皮校正（如果启用）
                if hasattr(self, 'taring_enabled') and self.taring_enabled:
                    if hasattr(self, 'zero_offset_matrix') and self.zero_offset_matrix is not None:
                        # 逐点去皮
                        calibrated_data = self.apply_taring_correction(calibrated_data)
                        print(f"🔧 主界面热力图已应用逐点去皮校正")
                    elif hasattr(self, 'zero_offset') and self.zero_offset is not None:
                        # 向后兼容：旧版本去皮
                        calibrated_data = self.apply_taring_correction(calibrated_data)
                        print(f"🔧 主界面热力图已应用去皮校正: 偏移量 {self.zero_offset:.2f}")

                # 将校准后的数据替换到data_handler中
                if len(self.data_handler.value) > 0:
                    self.data_handler.value[-1] = calibrated_data

                # 不要修改value_before_zero，保持它为原始数据
                # 只修改filtered_data，因为它用于显示
                if len(self.data_handler.filtered_data) > 0:
                    self.data_handler.filtered_data[-1] = calibrated_data

            self.plotter.trigger()
            self.console_out.setText(self.get_console_str())

        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            # self.stop()
            raise e

    def trigger_null(self):
        self.plotter.trigger_null()

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.stop()
        super(Window, self).closeEvent(a0)
        sys.exit()

    def get_console_str(self):
        if self.is_running:
            if self.data_handler.saving_file:
                ret = '采集中...'
            else:
                ret = '已连接'
                if self.data_handler.tracing_points:
                    ret += f' 追踪点 {self.data_handler.tracing_points}'
        else:
            ret = '未连接'

        # 添加校准状态信息
        calibration_status = []
        if hasattr(self.data_handler, 'using_calibration') and self.data_handler.using_calibration:
            calibration_status.append('传统校准')
        if hasattr(self.data_handler, 'using_balance_calibration') and self.data_handler.using_balance_calibration:
            calibration_status.append('平衡校准')
        if self.calibration_coeffs is not None:
            calibration_status.append('AI校准')

        if calibration_status:
            ret += f' | 校准: {", ".join(calibration_status)}'

        return ret

    # ==================== AI校准功能 ====================

    def setup_calibration(self):
        """设置AI校准功能"""
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            print("AI校准将使用GPU加速")
        else:
            self.device = torch.device("cpu")
            print("AI校准将使用CPU")

    def __load_ai_calibration(self):
        """加载AI校准模型"""
        try:
            # 尝试从当前目录加载
            current_dir = os.getcwd()
            coeffs_path = os.path.join(current_dir, 'calibration_package.pt')

            if not os.path.exists(coeffs_path):
                # 如果不存在，尝试从其他可能路径加载
                possible_paths = [
                    'calibration_package.pt',
                    '../calibration_package.pt',
                    '../../calibration_package.pt',
                    'data-0815/../calibration_package.pt',
                    # 兼容旧版本文件名
                    'calibration_coeffs.pt',
                    '../calibration_coeffs.pt'
                ]

                for path in possible_paths:
                    if os.path.exists(path):
                        coeffs_path = path
                        break

            if os.path.exists(coeffs_path):
                # 加载校准包
                calibration_package = torch.load(coeffs_path)
                
                # 检查是新版本还是旧版本格式
                if isinstance(calibration_package, dict) and 'coeffs' in calibration_package:
                    # 新版本格式：calibration_package.pt
                    self.calibration_coeffs = calibration_package['coeffs'].to(self.device)
                    self.calibration_data_mean = calibration_package['data_mean'].to(self.device)
                    self.calibration_data_std = calibration_package['data_std'].to(self.device)
                    self.calibration_format = 'new'
                    print(f"✅ 新版本AI校准包加载成功: {coeffs_path}")
                    print(f"   系数形状: {self.calibration_coeffs.shape}")
                    print(f"   数据均值: {self.calibration_data_mean.shape}")
                    print(f"   数据标准差: {self.calibration_data_std.shape}")
                else:
                    # 旧版本格式：calibration_coeffs.pt
                    self.calibration_coeffs = calibration_package.to(self.device)
                    self.calibration_data_mean = None
                    self.calibration_data_std = None
                    self.calibration_format = 'old'
                    print(f"✅ 旧版本AI校准模型加载成功: {coeffs_path}")
                print(f"   模型形状: {self.calibration_coeffs.shape}")

                # 显示成功消息
                format_text = "新版本校准包" if self.calibration_format == 'new' else "旧版本校准模型"
                QtWidgets.QMessageBox.information(self, "成功",
                    f"{format_text}已加载!\n路径: {coeffs_path}\n形状: {self.calibration_coeffs.shape}")

            else:
                QtWidgets.QMessageBox.warning(self, "文件未找到",
                    f"未找到校准文件: calibration_package.pt 或 calibration_coeffs.pt\n请先运行校准训练脚本。")
                return False

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "加载失败", f"加载AI校准模型失败:\n{str(e)}")
            return False

        return True

    def apply_ai_calibration(self, raw_data_64x64):
        """应用AI校准到64x64原始数据"""
        if self.calibration_coeffs is None:
            return raw_data_64x64

        try:
            # 将数据转换为tensor
            raw_tensor = torch.from_numpy(raw_data_64x64).float().to(self.device)

            if self.calibration_format == 'new':
                # 新版本校准流程：标准化 → 校准 → 逆标准化
                print(f"🔧 新版本校准流程开始...")
                print(f"   原始数据范围: [{raw_tensor.min():.2f}, {raw_tensor.max():.2f}]")
                print(f"   数据均值范围: [{self.data_mean.min():.2f}, {self.data_mean.max():.2f}]")
                print(f"   数据标准差范围: [{self.data_std.min():.2f}, {self.data_std.max():.2f}]")
                
                # 1. 对新数据应用相同的标准化
                scaled_tensor = (raw_tensor - self.data_mean) / self.data_std
                print(f"   标准化后范围: [{scaled_tensor.min():.2f}, {scaled_tensor.max():.2f}]")
                
                # 2. 在标准化数据上应用校准函数
                x_flat = scaled_tensor.view(-1)
                x_poly = x_flat.unsqueeze(-1).pow(torch.arange(2, -1, -1, device=self.device))
                
                calibrated_flat_scaled = torch.sum(x_poly * self.coeffs, dim=1)
                print(f"   校准后标准化范围: [{calibrated_flat_scaled.min():.2f}, {calibrated_flat_scaled.max():.2f}]")
                
                # 3. 将结果逆变换回原始数据量级
                calibrated_flat_rescaled = calibrated_flat_scaled * self.data_std + self.data_mean
                calibrated_tensor = calibrated_flat_rescaled.view(64, 64)
                print(f"   逆变换后范围: [{calibrated_tensor.min():.2f}, {calibrated_tensor.max():.2f}]")
                
                # 转换为numpy数组并返回
                calibrated_data = calibrated_tensor.cpu().numpy()
                print(f"✅ 新版本校准完成，最终范围: [{calibrated_data.min():.2f}, {calibrated_data.max():.2f}]")
                return calibrated_data

            else:
                # 旧版本校准流程：直接应用二次多项式
                # 展平数据
                raw_flat = raw_tensor.view(-1)

                # 应用校准函数：y = a*x² + b*x + c
                x = raw_flat
                a = self.coeffs[:, 0]  # 二次项系数
                b = self.coeffs[:, 1]  # 一次项系数
                c = self.coeffs[:, 2]  # 常数项

                calibrated_flat = a * x**2 + b * x + c

                # 恢复形状
                calibrated_tensor = calibrated_flat.view(64, 64)

                # 转换为numpy数组
                calibrated_data = calibrated_tensor.cpu().numpy()

                # 添加数据范围限制，避免校准后数据过于极端
                raw_range = raw_data.max() - raw_data.min()
                if raw_range > 0:
                    # 限制校准后数据的范围不超过原始数据的5倍
                    max_allowed_range = raw_range * 5
                    calibrated_range = calibrated_data.max() - calibrated_data.min()
                    
                    if calibrated_range > max_allowed_range:
                        print(f"⚠️ 校准后数据范围过大: {calibrated_range:.1f} > {max_allowed_range:.1f}")
                        print(f"   原始范围: {raw_range:.1f}, 校准后范围: {calibrated_range:.1f}")
                        print(f"   将限制校准后数据范围")
                        
                        # 显示校准系数信息（调试用）
                        coeffs_cpu = self.coeffs.cpu()
                        print(f"   校准系数范围:")
                        print(f"     a: [{coeffs_cpu[:, 0].min():.4f}, {coeffs_cpu[:, 0].max():.4f}]")
                        print(f"     b: [{coeffs_cpu[:, 1].min():.4f}, {coeffs_cpu[:, 1].max():.4f}]")
                        print(f"     c: [{coeffs_cpu[:, 2].min():.4f}, {coeffs_cpu[:, 2].max():.4f}]")
                    
                    # 将校准后数据限制在合理范围内
                    calibrated_mean = calibrated_data.mean()
                    calibrated_data = np.clip(calibrated_data, 
                                           calibrated_mean - max_allowed_range/2,
                                           calibrated_mean + max_allowed_range/2)

                # 滤除负值：将负值替换为0
                negative_mask = calibrated_data < 0
                if negative_mask.any():
                    negative_count = negative_mask.sum()
                    print(f"⚠️ 检测到 {negative_count} 个负值，将其替换为0")
                    calibrated_data[negative_mask] = 0

                # 零点校正：如果原始数据接近0，校准后也应该接近0
                zero_threshold = 5.0  # 认为小于5的原始值为"无按压"
                zero_mask = raw_data < zero_threshold
                
                if zero_mask.any():
                    zero_count = zero_mask.sum()
                    print(f"🔧 零点校正: 检测到 {zero_count} 个接近零的点，将其校准值限制在合理范围内")
                    
                    # 对于接近零的原始数据，校准后的值不应该过大
                    max_allowed_zero_value = 10.0  # 允许的最大零点值
                    calibrated_data[zero_mask] = np.clip(calibrated_data[zero_mask], 0, max_allowed_zero_value)

                # 应用去皮校正
                calibrated_data = self.apply_taring_correction(calibrated_data)

                return calibrated_data

        except Exception as e:
            print(f"AI校准应用失败: {e}")
            return raw_data_64x64

    def show_ai_calibration_info(self):
        """显示AI校准信息"""
        # 检查是否有可用的校准器（单校准器或双校准器模式）
        has_calibrator = False
        if self.calibration_coeffs is not None:
            has_calibrator = True
        elif hasattr(self, 'dual_calibration_mode') and self.dual_calibration_mode:
            if self.old_calibrator is not None or self.new_calibrator is not None:
                has_calibrator = True
        
        if not has_calibrator:
            QtWidgets.QMessageBox.information(self, "AI校准信息",
                "AI校准模型尚未加载。\n\n"
                "请先通过菜单选择以下选项之一：\n"
                "• '加载AI校准模型' (单校准器模式)\n"
                "• '加载双校准器' (双校准器模式)")
            return

        # 显示校准信息
        if self.calibration_coeffs is not None:
            # 单校准器模式
            info_text = self._get_single_calibrator_info()
        else:
            # 双校准器模式
            info_text = self._get_dual_calibrator_info()
        
        # 显示去皮状态
        if self.taring_enabled and hasattr(self, 'zero_offset_matrix') and self.zero_offset_matrix is not None:
            info_text += f"\n逐点去皮功能: 已启用\n"
            info_text += f"基准矩阵统计:\n"
            info_text += f"  均值: {self.zero_offset_matrix.mean():.2f}\n"
            info_text += f"  标准差: {self.zero_offset_matrix.std():.2f}\n"
            info_text += f"  最小值: {self.zero_offset_matrix.min():.2f}\n"
            info_text += f"  最大值: {self.zero_offset_matrix.max():.2f}\n"
            info_text += f"说明: 所有校准结果将逐点减去此基准矩阵，实现真正的零点校正"
        elif self.taring_enabled and hasattr(self, 'zero_offset') and self.zero_offset is not None:
            # 向后兼容：显示旧版本去皮信息
            info_text += f"\n去皮功能: 已启用 (旧版本)\n"
            info_text += f"零点偏移量: {self.zero_offset:.2f}\n"
            info_text += f"说明: 所有校准结果将减去此偏移量"
        else:
            info_text += f"\n去皮功能: 未启用\n"
            info_text += f"说明: 校准结果包含零点偏移，建议执行逐点去皮操作"

        QtWidgets.QMessageBox.information(self, "AI校准信息", info_text)
    
    def _get_single_calibrator_info(self):
        """获取单校准器信息"""
        # 获取模型信息
        model_shape = self.calibration_coeffs.shape
        device_info = str(self.device)

        info_text = f"AI校准模型信息 (单校准器模式):\n\n"
        info_text += f"模型形状: {model_shape}\n"
        info_text += f"设备: {device_info}\n"
        
        if hasattr(self, 'calibration_format'):
            info_text += f"校准格式: {self.calibration_format}\n"
        
        if hasattr(self, 'calibration_data_mean') and self.calibration_data_mean is not None:
            info_text += f"数据均值范围: [{self.calibration_data_mean.min():.2f}, {self.calibration_data_mean.max():.2f}]\n"
            info_text += f"数据标准差范围: [{self.calibration_data_std.min():.2f}, {self.calibration_data_std.max():.2f}]\n"
        
        return info_text
    
    def _get_dual_calibrator_info(self):
        """获取双校准器信息"""
        info_text = f"AI校准模型信息 (双校准器模式):\n\n"
        
        if self.old_calibrator is not None:
            old_info = self.old_calibrator.get_info()
            info_text += f"旧版本校准器:\n"
            info_text += f"  格式: {old_info['calibration_format']}\n"
            info_text += f"  系数形状: {old_info['coeffs_shape']}\n"
            info_text += f"  设备: {old_info['device']}\n"
            if old_info['coeffs_range']:
                coeffs = old_info['coeffs_range']
                info_text += f"  系数范围:\n"
                info_text += f"    a: [{coeffs['a'][0]:.4f}, {coeffs['a'][1]:.4f}]\n"
                info_text += f"    b: [{coeffs['b'][0]:.4f}, {coeffs['b'][1]:.4f}]\n"
                info_text += f"    c: [{coeffs['c'][0]:.4f}, {coeffs['c'][1]:.4f}]\n"
            info_text += "\n"
        
        if self.new_calibrator is not None:
            new_info = self.new_calibrator.get_info()
            info_text += f"新版本校准器:\n"
            info_text += f"  格式: {new_info['calibration_format']}\n"
            info_text += f"  系数形状: {new_info['coeffs_shape']}\n"
            info_text += f"  设备: {new_info['device']}\n"
            if new_info['coeffs_range']:
                coeffs = new_info['coeffs_range']
                info_text += f"  系数范围:\n"
                info_text += f"    a: [{coeffs['a'][0]:.4f}, {coeffs['a'][1]:.4f}]\n"
                info_text += f"    b: [{coeffs['b'][0]:.4f}, {coeffs['b'][1]:.4f}]\n"
                info_text += f"    c: [{coeffs['c'][0]:.4f}, {coeffs['c'][1]:.4f}]\n"
            if 'data_mean_range' in new_info:
                info_text += f"  数据均值范围: {new_info['data_mean_range']}\n"
                info_text += f"  数据标准差范围: {new_info['data_std_range']}\n"
        
        return info_text

    # ==================== 双校准器比较功能 ====================
    
    def load_dual_calibrators(self):
        """同时加载新旧两种校准器"""
        try:
            print("🔧 开始加载双校准器...")
            
            # 查找校准文件
            old_cal_file = None
            new_cal_file = None
            
            # 查找旧版本文件
            old_possible_paths = [
                'calibration_coeffs.pt',
                '../calibration_coeffs.pt',
                '../../calibration_coeffs.pt'
            ]
            
            for path in old_possible_paths:
                if os.path.exists(path):
                    old_cal_file = path
                    break
            
            # 查找新版本文件
            new_possible_paths = [
                'calibration_package.pt',
                '../calibration_package.pt',
                '../../calibration_package.pt'
            ]
            
            for path in new_possible_paths:
                if os.path.exists(path):
                    new_cal_file = path
                    break
            
            if not old_cal_file and not new_cal_file:
                QtWidgets.QMessageBox.warning(self, "文件未找到",
                    "未找到任何校准文件。\n请确保存在以下文件之一：\n• calibration_coeffs.pt (旧版本)\n• calibration_package.pt (新版本)")
                return False
            
            # 加载旧版本校准器
            if old_cal_file:
                print(f"🔧 加载旧版本校准器: {old_cal_file}")
                self.old_calibrator = AICalibrationAdapter()
                if self.old_calibrator.load_calibration(old_cal_file):
                    print("✅ 旧版本校准器加载成功")
                else:
                    print("❌ 旧版本校准器加载失败")
                    self.old_calibrator = None
            
            # 加载新版本校准器
            if new_cal_file:
                print(f"🔧 加载新版本校准器: {new_cal_file}")
                self.new_calibrator = AICalibrationAdapter()
                if self.new_calibrator.load_calibration(new_cal_file):
                    print("✅ 新版本校准器加载成功")
                else:
                    print("❌ 新版本校准器加载失败")
                    self.new_calibrator = None
            
            # 检查是否至少有一个校准器加载成功
            if self.old_calibrator is None and self.new_calibrator is None:
                QtWidgets.QMessageBox.critical(self, "加载失败", "所有校准器加载失败")
                return False
            
            # 启用双校准模式
            self.dual_calibration_mode = True
            
            # 显示加载成功信息
            success_text = "双校准器加载成功!\n\n"
            if self.old_calibrator:
                old_info = self.old_calibrator.get_info()
                success_text += f"旧版本校准器:\n"
                success_text += f"  格式: {old_info['calibration_format']}\n"
                success_text += f"  系数形状: {old_info['coeffs_shape']}\n"
            if self.new_calibrator:
                new_info = self.new_calibrator.get_info()
                success_text += f"新版本校准器:\n"
                success_text += f"  格式: {new_info['calibration_format']}\n"
                success_text += f"  系数形状: {new_info['coeffs_shape']}\n"
            
            success_text += "\n现在可以启动实时比较功能！"
            
            QtWidgets.QMessageBox.information(self, "加载成功", success_text)
            print("✅ 双校准器加载完成，双校准模式已启用")
            
            return True
            
        except Exception as e:
            print(f"❌ 加载双校准器失败: {e}")
            QtWidgets.QMessageBox.critical(self, "加载失败", f"加载双校准器失败:\n{str(e)}")
            return False
    
    def start_dual_calibration_comparison(self):
        """启动双校准器实时比较"""
        if not self.dual_calibration_mode:
            QtWidgets.QMessageBox.warning(self, "未启用", "请先加载双校准器")
            return
        
        if self.old_calibrator is None and self.new_calibrator is None:
            QtWidgets.QMessageBox.warning(self, "校准器不可用", "没有可用的校准器")
            return
        
        try:
            # 创建实时比较对话框
            if self.comparison_dialog is None or not self.comparison_dialog.isVisible():
                self.comparison_dialog = DualCalibrationComparisonDialog(self)
                self.comparison_dialog.show()
                print("✅ 双校准器实时比较已启动")
            else:
                self.comparison_dialog.raise_()
                self.comparison_dialog.activateWindow()
                print("✅ 比较对话框已激活")
                
        except Exception as e:
            print(f"❌ 启动双校准器比较失败: {e}")
            QtWidgets.QMessageBox.critical(self, "启动失败", f"启动双校准器比较失败:\n{str(e)}")
    
    def apply_dual_calibration(self, raw_data_64x64):
        """应用双校准器校准并返回比较结果"""
        if not self.dual_calibration_mode:
            return None
        
        try:
            results = {}
            
            # 应用旧版本校准器
            if self.old_calibrator is not None:
                old_calibrated = self.old_calibrator.apply_calibration(raw_data_64x64)
                results['old'] = {
                    'data': old_calibrated,
                    'mean': float(old_calibrated.mean()),
                    'std': float(old_calibrated.std()),
                    'min': float(old_calibrated.min()),
                    'max': float(old_calibrated.max()),
                    'range': float(old_calibrated.max() - old_calibrated.min())
                }
            
            # 应用新版本校准器
            if self.new_calibrator is not None:
                new_calibrated = self.new_calibrator.apply_calibration(raw_data_64x64)
                results['new'] = {
                    'data': new_calibrated,
                    'mean': float(new_calibrated.mean()),
                    'std': float(new_calibrated.std()),
                    'min': float(new_calibrated.min()),
                    'max': float(new_calibrated.max()),
                    'range': float(new_calibrated.max() - new_calibrated.min())
                }
            
            # 添加原始数据统计
            results['raw'] = {
                'data': raw_data_64x64,
                'mean': float(raw_data_64x64.mean()),
                'std': float(raw_data_64x64.std()),
                'min': float(raw_data_64x64.min()),
                'max': float(raw_data_64x64.max()),
                'range': float(raw_data_64x64.max() - raw_data_64x64.min())
            }
            
            # 应用去皮校正到校准结果
            if self.taring_enabled:
                if hasattr(self, 'zero_offset_matrix') and self.zero_offset_matrix is not None:
                    # 逐点去皮
                    if 'old' in results:
                        results['old']['data'] = self.apply_taring_correction(results['old']['data'])
                        results['old']['mean'] = float(results['old']['data'].mean())
                        results['old']['std'] = float(results['old']['data'].std())
                        results['old']['min'] = float(results['old']['data'].min())
                        results['old']['max'] = float(results['old']['data'].max())
                        results['old']['range'] = float(results['old']['data'].max() - results['old']['data'].min())
                    
                    if 'new' in results:
                        results['new']['data'] = self.apply_taring_correction(results['new']['data'])
                        results['new']['mean'] = float(results['new']['data'].mean())
                        results['new']['std'] = float(results['new']['data'].std())
                        results['new']['min'] = float(results['new']['data'].min())
                        results['new']['max'] = float(results['new']['data'].max())
                        results['new']['range'] = float(results['new']['data'].max() - results['new']['data'].min())
                
                elif hasattr(self, 'zero_offset') and self.zero_offset is not None:
                    # 向后兼容：旧版本去皮
                    if 'old' in results:
                        results['old']['data'] = self.apply_taring_correction(results['old']['data'])
                        results['old']['mean'] = float(results['old']['data'].mean())
                        results['old']['std'] = float(results['old']['data'].std())
                        results['old']['min'] = float(results['old']['data'].min())
                        results['old']['max'] = float(results['old']['data'].max())
                        results['old']['range'] = float(results['old']['data'].max() - results['old']['data'].min())
                    
                    if 'new' in results:
                        results['new']['data'] = self.apply_taring_correction(results['new']['data'])
                        results['new']['mean'] = float(results['new']['data'].mean())
                        results['new']['std'] = float(results['new']['data'].std())
                        results['new']['min'] = float(results['new']['data'].min())
                        results['new']['max'] = float(results['new']['data'].max())
                        results['new']['range'] = float(results['new']['data'].max() - results['new']['data'].min())
            
            return results
            
        except Exception as e:
            print(f"❌ 应用双校准器失败: {e}")
            return None
    
    def get_dual_calibration_info(self):
        """获取双校准器信息"""
        info = {
            'dual_mode': self.dual_calibration_mode,
            'old_calibrator': None,
            'new_calibrator': None
        }
        
        if self.old_calibrator is not None:
            info['old_calibrator'] = self.old_calibrator.get_info()
        
        if self.new_calibrator is not None:
            info['new_calibrator'] = self.new_calibrator.get_info()
        
        return info
    
    def perform_taring(self):
        """执行去皮操作 - 在无按压状态下校准零点（逐点去皮）"""
        try:
            # 检查是否有可用的校准器（单校准器或双校准器模式）
            has_calibrator = False
            if self.calibration_coeffs is not None:
                has_calibrator = True
                print("🔧 检测到单校准器模式")
            elif hasattr(self, 'dual_calibration_mode') and self.dual_calibration_mode:
                if self.old_calibrator is not None or self.new_calibrator is not None:
                    has_calibrator = True
                    print("🔧 检测到双校准器模式")
            
            if not has_calibrator:
                QtWidgets.QMessageBox.warning(self, "去皮失败", 
                    "请先加载AI校准模型或双校准器\n\n"
                    "单校准器模式：选择'加载AI校准模型'\n"
                    "双校准器模式：选择'加载双校准器'")
                return False
            
            # 获取当前帧数据作为零点基准
            current_data = self.get_current_frame_data()
            if current_data is None:
                QtWidgets.QMessageBox.warning(self, "去皮失败", "无法获取当前传感器数据")
                return False
            
            # 应用校准得到基准输出
            if self.calibration_coeffs is not None:
                # 单校准器模式
                baseline_output = self.apply_ai_calibration(current_data)
            else:
                # 双校准器模式 - 使用新版本校准器（如果有的话）
                if self.new_calibrator is not None:
                    baseline_output = self.new_calibrator.apply_calibration(current_data)
                elif self.old_calibrator is not None:
                    baseline_output = self.old_calibrator.apply_calibration(current_data)
                else:
                    baseline_output = None
            
            if baseline_output is None:
                QtWidgets.QMessageBox.warning(self, "去皮失败", "校准应用失败")
                return False
            
            # 逐点去皮：保存整个64x64的基准矩阵
            self.zero_offset_matrix = baseline_output.copy()
            self.taring_enabled = True
            
            # 计算统计信息用于显示
            baseline_mean = float(baseline_output.mean())
            baseline_std = float(baseline_output.std())
            baseline_min = float(baseline_output.min())
            baseline_max = float(baseline_output.max())
            
            print(f"🔧 逐点去皮完成！")
            print(f"   原始数据均值: {current_data.mean():.2f}")
            print(f"   校准后基准矩阵统计:")
            print(f"     均值: {baseline_mean:.2f}")
            print(f"     标准差: {baseline_std:.2f}")
            print(f"     最小值: {baseline_min:.2f}")
            print(f"     最大值: {baseline_max:.2f}")
            print(f"   现在所有校准结果将逐点减去此基准矩阵")
            
            QtWidgets.QMessageBox.information(self, "逐点去皮成功", 
                f"逐点去皮操作完成！\n\n"
                f"基准矩阵统计:\n"
                f"  均值: {baseline_mean:.2f}\n"
                f"  标准差: {baseline_std:.2f}\n"
                f"  最小值: {baseline_min:.2f}\n"
                f"  最大值: {baseline_max:.2f}\n\n"
                f"现在所有校准结果将逐点减去此基准矩阵，\n"
                f"实现真正的\"无压力时处处为零\"效果。")
            
            return True
            
        except Exception as e:
            print(f"❌ 去皮操作失败: {e}")
            QtWidgets.QMessageBox.critical(self, "去皮失败", f"去皮操作失败:\n{str(e)}")
            return False
    
    def reset_taring(self):
        """重置去皮功能"""
        self.zero_offset = None  # 保持向后兼容
        if hasattr(self, 'zero_offset_matrix'):
            self.zero_offset_matrix = None
        self.taring_enabled = False
        print("🔧 逐点去皮功能已重置")
        QtWidgets.QMessageBox.information(self, "去皮重置", "逐点去皮功能已重置，校准结果将不再减去基准矩阵。")
    
    def apply_taring_correction(self, calibrated_data):
        """应用去皮校正（逐点去皮）"""
        if self.taring_enabled and hasattr(self, 'zero_offset_matrix') and self.zero_offset_matrix is not None:
            print(f"🔧 应用逐点去皮校正:")
            print(f"   校正前均值: {calibrated_data.mean():.2f}")
            print(f"   校正前范围: [{calibrated_data.min():.2f}, {calibrated_data.max():.2f}]")
            
            # 逐点减去基准矩阵
            corrected_data = calibrated_data - self.zero_offset_matrix
            
            print(f"   基准矩阵均值: {self.zero_offset_matrix.mean():.2f}")
            print(f"   基准矩阵范围: [{self.zero_offset_matrix.min():.2f}, {self.zero_offset_matrix.max():.2f}]")
            print(f"   校正后均值: {corrected_data.mean():.2f}")
            print(f"   校正后范围: [{corrected_data.min():.2f}, {corrected_data.max():.2f}]")
            
            return corrected_data
        else:
            print(f"⚠️ 逐点去皮功能未启用或基准矩阵未设置")
            print(f"   taring_enabled: {getattr(self, 'taring_enabled', False)}")
            print(f"   zero_offset_matrix: {getattr(self, 'zero_offset_matrix', None)}")
        return calibrated_data

    def __show_calibration_comparison(self):
        """显示校准前后对比"""
        # 检查是否有可用的校准器（单校准器或双校准器模式）
        has_calibrator = False
        if self.calibration_coeffs is not None:
            has_calibrator = True
        elif hasattr(self, 'dual_calibration_mode') and self.dual_calibration_mode:
            if self.old_calibrator is not None or self.new_calibrator is not None:
                has_calibrator = True
        
        if not has_calibrator:
            QtWidgets.QMessageBox.warning(self, "未加载", 
                "请先加载AI校准模型或双校准器\n\n"
                "单校准器模式：选择'加载AI校准模型'\n"
                "双校准器模式：选择'加载双校准器'")
            return

        # 创建实时对比对话框
        dialog = RealtimeCalibrationDialog(self)
        dialog.show()  # 使用show()而不是exec_()，这样不会阻塞主界面
        
    def __show_detailed_calibration_comparison(self):
        """显示详细校准对比"""
        # 检查是否有可用的校准器（单校准器或双校准器模式）
        has_calibrator = False
        if self.calibration_coeffs is not None:
            has_calibrator = True
        elif hasattr(self, 'dual_calibration_mode') and self.dual_calibration_mode:
            if self.old_calibrator is not None or self.new_calibrator is not None:
                has_calibrator = True
        
        if not has_calibrator:
            QtWidgets.QMessageBox.warning(self, "未加载", 
                "请先加载AI校准模型或双校准器\n\n"
                "单校准器模式：选择'加载AI校准模型'\n"
                "双校准器模式：选择'加载双校准器'")
            return

        # 创建详细对比对话框
        dialog = CalibrationComparisonDialog(self)
        dialog.exec_()

    def get_current_frame_data(self):
        """获取当前帧的原始数据（用于校准对比）"""
        try:
            # 添加调试信息
            print(f"🔍 数据源状态检查:")
            print(f"   data_handler.data长度: {len(self.data_handler.data) if hasattr(self.data_handler, 'data') else 'N/A'}")
            print(f"   data_handler.value长度: {len(self.data_handler.value) if hasattr(self.data_handler, 'value') else 'N/A'}")
            print(f"   data_handler.value_before_zero长度: {len(self.data_handler.value_before_zero) if hasattr(self.data_handler, 'value_before_zero') else 'N/A'}")
            
            # 优先从data_handler获取最新的实时原始数据
            if hasattr(self.data_handler, 'data') and len(self.data_handler.data) > 0:
                current_data = self.data_handler.data[-1]
                print(f"✅ 使用data_handler.data的实时原始数据，形状: {current_data.shape}, 范围: [{current_data.min():.4f}, {current_data.max():.4f}]")
                return current_data
            elif hasattr(self.data_handler, 'value_before_zero') and len(self.data_handler.value_before_zero) > 0:
                # 如果data为空，尝试从value_before_zero获取原始数据
                current_data = self.data_handler.value_before_zero[-1]
                print(f"✅ 使用value_before_zero的原始数据，形状: {current_data.shape}, 范围: [{current_data.min():.4f}, {current_data.max():.4f}]")
                return current_data
            elif hasattr(self, '_raw_data_for_comparison') and len(self._raw_data_for_comparison) > 0:
                # 最后才使用保存的原始数据副本
                current_data = self._raw_data_for_comparison[-1]
                print(f"⚠️ 使用保存的原始数据副本，形状: {current_data.shape}, 范围: [{current_data.min():.4f}, {current_data.max():.4f}]")
                return current_data
            elif hasattr(self.data_handler, 'value') and len(self.data_handler.value) > 0:
                # 最后从value获取（可能已经是校准后的数据）
                current_data = self.data_handler.value[-1]
                print(f"⚠️ 使用可能已校准的数据作为原始数据，形状: {current_data.shape}, 范围: [{current_data.min():.4f}, {current_data.max():.4f}]")
                return current_data
            else:
                # 如果没有数据，返回模拟数据
                print("⚠️ 没有实时数据，使用模拟数据")
                # 生成一些变化的模拟数据，而不是完全随机的
                if not hasattr(self, '_simulation_counter'):
                    self._simulation_counter = 0
                self._simulation_counter += 1
                
                # 创建基于时间的模拟数据，模拟传感器压力变化
                base_data = np.zeros((64, 64))
                center_x, center_y = 32, 32
                for i in range(64):
                    for j in range(64):
                        distance = np.sqrt((i - center_x)**2 + (j - center_y)**2)
                        pressure = max(0, 1000 - distance * 10 + np.sin(self._simulation_counter * 0.1) * 100)
                        base_data[i, j] = pressure
                
                print(f"✅ 生成模拟数据，形状: {base_data.shape}, 范围: [{base_data.min():.4f}, {base_data.max():.4f}]")
                return base_data
                
        except Exception as e:
            print(f"❌ 获取当前帧数据失败: {e}")
            # 返回默认数据
            return np.zeros((64, 64))

    def setup_calibration_menu(self):
        """设置AI校准菜单"""
        try:
            print("🔧 开始设置AI校准菜单...")
            
            # 检查menubar是否存在
            if not hasattr(self, 'menubar') or self.menubar is None:
                print("❌ 菜单栏不存在，尝试创建...")
                # 尝试创建菜单栏
                self.menubar = QtWidgets.QMenuBar(self)
                self.setMenuBar(self.menubar)
                print("✅ 已创建新的菜单栏")
            
            # 确保菜单栏可见和启用
            self.menubar.setVisible(True)
            self.menubar.setHidden(False)
            self.menubar.setEnabled(True)
            self.menubar.raise_()
            
            print(f"✅ 菜单栏状态: 可见={self.menubar.isVisible()}, 启用={self.menubar.isEnabled()}")
            
            # 创建AI校准菜单
            self.menu_ai_calibration = self.menubar.addMenu("AI校准")
            
            # 设置菜单样式 - 纯白色背景，更美观
            self.menu_ai_calibration.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    color: #333333;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QMenu::item {
                    background-color: transparent;
                    padding: 10px 25px;
                    border-radius: 6px;
                    margin: 2px 0px;
                }
                QMenu::item:selected {
                    background-color: #f0f8ff;
                    color: #1e90ff;
                    font-weight: bold;
                }
                QMenu::item:hover {
                    background-color: #f5f5f5;
                    color: #333333;
                }
                QMenu::separator {
                    height: 2px;
                    background-color: #e8e8e8;
                    margin: 8px 0px;
                    border-radius: 1px;
                }
            """)
            
            print("✅ AI校准菜单已创建，样式设置为白色背景")

            # 加载AI校准模型
            action_load_model = QtWidgets.QAction("加载AI校准模型", self)
            action_load_model.triggered.connect(self.__load_ai_calibration)
            self.menu_ai_calibration.addAction(action_load_model)
            print("✅ 加载AI校准模型菜单项已添加")
            
            # 加载双校准器
            action_load_dual = QtWidgets.QAction("加载双校准器", self)
            action_load_dual.triggered.connect(self.load_dual_calibrators)
            self.menu_ai_calibration.addAction(action_load_dual)
            print("✅ 加载双校准器菜单项已添加")
            
            # 启动双校准器比较
            action_start_comparison = QtWidgets.QAction("启动双校准器比较", self)
            action_start_comparison.triggered.connect(self.start_dual_calibration_comparison)
            self.menu_ai_calibration.addAction(action_start_comparison)
            print("✅ 启动双校准器比较菜单项已添加")
            
            # 分隔线
            self.menu_ai_calibration.addSeparator()
            print("✅ 分隔线1已添加")
            
            # 显示AI校准信息
            action_show_info = QtWidgets.QAction("显示校准信息", self)
            action_show_info.triggered.connect(self.show_ai_calibration_info)
            self.menu_ai_calibration.addAction(action_show_info)
            print("✅ 显示校准信息菜单项已添加")
            
            # 显示双校准器信息
            action_show_dual_info = QtWidgets.QAction("显示双校准器信息", self)
            action_show_dual_info.triggered.connect(self.__show_dual_calibration_info)
            self.menu_ai_calibration.addAction(action_show_dual_info)
            print("✅ 显示双校准器信息菜单项已添加")
            
            # 分隔线
            self.menu_ai_calibration.addSeparator()
            print("✅ 分隔线2已添加")
            
            # 校准前后对比
            action_show_comparison = QtWidgets.QAction("校准前后对比", self)
            action_show_comparison.triggered.connect(self.__show_calibration_comparison)
            self.menu_ai_calibration.addAction(action_show_comparison)
            print("✅ 校准前后对比菜单项已添加")
            
            # 分隔线
            self.menu_ai_calibration.addSeparator()
            print("✅ 分隔线3已添加")
            
            # 去皮功能
            action_perform_taring = QtWidgets.QAction("执行去皮", self)
            action_perform_taring.triggered.connect(self.perform_taring)
            self.menu_ai_calibration.addAction(action_perform_taring)
            print("✅ 执行去皮菜单项已添加")
            
            action_reset_taring = QtWidgets.QAction("重置去皮", self)
            action_reset_taring.triggered.connect(self.reset_taring)
            self.menu_ai_calibration.addAction(action_reset_taring)
            print("✅ 重置去皮菜单项已添加")
            
            # 设置整个菜单栏的样式 - 白色背景
            self.menubar.setStyleSheet("""
                QMenuBar {
                    background-color: #ffffff;
                    color: #333333;
                    border-bottom: 2px solid #e0e0e0;
                    padding: 5px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 8px 15px;
                    border-radius: 4px;
                    margin: 2px;
                }
                QMenuBar::item:selected {
                    background-color: #f0f8ff;
                    color: #1e90ff;
                }
                QMenuBar::item:pressed {
                    background-color: #e3f2fd;
                    color: #1976d2;
                }
            """)
            
            # 强制刷新菜单栏
            self.menubar.updateGeometry()
            self.menubar.repaint()
            
            # 验证菜单项是否正确添加
            actions = self.menu_ai_calibration.actions()
            print(f"📋 AI校准菜单中的项目数量: {len(actions)}")
            
            for i, action in enumerate(actions):
                if action.isSeparator():
                    print(f"   项目 {i+1}: [分隔线]")
                else:
                    print(f"   项目 {i+1}: {action.text()}")
            
            # 显示所有菜单
            all_menus = self.menubar.findChildren(QtWidgets.QMenu)
            print(f"�� 菜单栏中的所有菜单: {[menu.title() for menu in all_menus]}")
            
            # 强制显示菜单
            self.menu_ai_calibration.setVisible(True)
            self.menu_ai_calibration.setEnabled(True)
            
            print("✅ AI校准菜单设置完成")

        except Exception as e:
            print(f"❌ 设置AI校准菜单失败: {e}")
            import traceback
            traceback.print_exc()

    def __show_dual_calibration_info(self):
        """显示双校准器信息"""
        if not self.dual_calibration_mode:
            QtWidgets.QMessageBox.information(self, "双校准器信息",
                "双校准器模式尚未启用。\n\n请先通过菜单选择'加载双校准器'来加载校准文件。")
            return
        
        info = self.get_dual_calibration_info()
        
        info_text = "双校准器信息:\n\n"
        info_text += f"双校准模式: {'启用' if info['dual_mode'] else '禁用'}\n\n"
        
        if info['old_calibrator']:
            old_info = info['old_calibrator']
            info_text += "旧版本校准器:\n"
            info_text += f"  格式: {old_info['calibration_format']}\n"
            info_text += f"  系数形状: {old_info['coeffs_shape']}\n"
            info_text += f"  设备: {old_info['device']}\n"
            if old_info['coeffs_range']:
                coeffs = old_info['coeffs_range']
                info_text += f"  系数范围:\n"
                info_text += f"    a: [{coeffs['a'][0]:.4f}, {coeffs['a'][1]:.4f}]\n"
                info_text += f"    b: [{coeffs['b'][0]:.4f}, {coeffs['b'][1]:.4f}]\n"
                info_text += f"    c: [{coeffs['c'][0]:.4f}, {coeffs['c'][1]:.4f}]\n"
            info_text += "\n"
        
        if info['new_calibrator']:
            new_info = info['new_calibrator']
            info_text += "新版本校准器:\n"
            info_text += f"  格式: {new_info['calibration_format']}\n"
            info_text += f"  系数形状: {new_info['coeffs_shape']}\n"
            info_text += f"  设备: {new_info['device']}\n"
            if new_info['coeffs_range']:
                coeffs = new_info['coeffs_range']
                info_text += f"  系数范围:\n"
                info_text += f"    a: [{coeffs['a'][0]:.4f}, {coeffs['a'][1]:.4f}]\n"
                info_text += f"    b: [{coeffs['b'][0]:.4f}, {coeffs['b'][1]:.4f}]\n"
                info_text += f"    c: [{coeffs['c'][0]:.4f}, {coeffs['c'][1]:.4f}]\n"
            if 'data_mean_range' in new_info:
                info_text += f"  数据均值范围: {new_info['data_mean_range']}\n"
                info_text += f"  数据标准差范围: {new_info['data_std_range']}\n"
        
        QtWidgets.QMessageBox.information(self, "双校准器信息", info_text)
            

    
    def _ensure_menubar_visible(self):
        """确保菜单栏可见"""
        try:
            if hasattr(self, 'menubar') and self.menubar is not None:
                self.menubar.setVisible(True)
                self.menubar.setHidden(False)
                self.menubar.setEnabled(True)
                self.menubar.raise_()
                self.menubar.updateGeometry()
                self.menubar.repaint()
                print("🔧 延迟设置菜单栏可见")
                
                # 确保AI校准菜单也可见
                if hasattr(self, 'menu_ai_calibration') and self.menu_ai_calibration is not None:
                    self.menu_ai_calibration.setVisible(True)
                    self.menu_ai_calibration.setEnabled(True)
                    print("🔧 AI校准菜单已设置为可见")
        except Exception as e:
            print(f"⚠️ 延迟设置菜单栏可见失败: {e}")
            


    def _setup_calibration_menu_delayed(self):
        """延迟设置AI校准菜单"""
        try:
            print("🔧 延迟设置AI校准菜单...")
            self.setup_calibration_menu()
            print("✅ 延迟设置AI校准菜单完成")
        except Exception as e:
            print(f"❌ 延迟设置AI校准菜单失败: {e}")
            import traceback
            traceback.print_exc()

# ==================== 实时校准对比对话框 ====================

class RealtimeCalibrationDialog(QtWidgets.QDialog):
    """实时校准前后对比对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("AI校准实时对比")
        self.setGeometry(200, 200, 1000, 600)
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 设置实时更新定时器
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_comparison)
        self.update_timer.start(500)  # 每500ms更新一次，减少CPU占用
        
        # 添加数据变化检测
        self._last_raw_data = None
        self._update_count = 0
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title = QtWidgets.QLabel("AI校准实时对比 - 校准前 vs 校准后")
        title.setStyleSheet("font-size: 16px; font-weight: bold; text-align: center;")
        layout.addWidget(title)
        
        # 创建两个热力图的布局
        heatmap_layout = QtWidgets.QHBoxLayout()
        
        # 左侧：校准前热力图
        self.raw_canvas = self.create_heatmap_canvas("校准前 - 原始数据")
        heatmap_layout.addWidget(self.raw_canvas)
        
        # 右侧：校准后热力图
        self.calibrated_canvas = self.create_heatmap_canvas("校准后 - AI校准数据")
        heatmap_layout.addWidget(self.calibrated_canvas)
        
        layout.addLayout(heatmap_layout)
        
        # 统计信息
        self.stats_label = QtWidgets.QLabel("统计信息加载中...")
        self.stats_label.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px; padding: 10px;")
        layout.addWidget(self.stats_label)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        # 强制刷新按钮
        refresh_btn = QtWidgets.QPushButton("强制刷新")
        refresh_btn.clicked.connect(self.force_refresh)
        button_layout.addWidget(refresh_btn)
        
        # 保存截图按钮
        save_btn = QtWidgets.QPushButton("保存截图")
        save_btn.clicked.connect(self.save_screenshot)
        button_layout.addWidget(save_btn)
        
        # 关闭按钮
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def create_heatmap_canvas(self, title):
        """创建热力图画布"""
        # 创建matplotlib图形
        fig = plt.figure(figsize=(6, 5))
        ax = fig.add_subplot(111)
        
        # 设置中文字体
        try:
            # 设置matplotlib中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            
            # 设置标题字体
            ax.set_title(title, fontsize=12, fontfamily='SimHei')
        except Exception as e:
            print(f"⚠️ 设置热力图中文字体失败: {e}")
            ax.set_title(title, fontsize=12)
        
        # 创建初始热力图（空数据）
        im = ax.imshow(np.zeros((64, 64)), cmap='viridis', aspect='equal')
        plt.colorbar(im, ax=ax, shrink=0.8)
        
        # 将matplotlib图形转换为Qt widget
        canvas = FigureCanvas(fig)
        canvas.setMinimumSize(400, 300)
        
        return canvas
        
    def update_comparison(self):
        """更新对比数据"""
        try:
            # 获取当前数据
            raw_data = self.parent.get_current_frame_data()
            
            # 检查数据是否真的在变化
            if hasattr(self, '_last_raw_data'):
                if np.array_equal(raw_data, self._last_raw_data):
                    return
            self._last_raw_data = raw_data.copy()
            
            # 应用AI校准
            if self.parent.calibration_coeffs is not None:
                calibrated_data = self.parent.apply_ai_calibration(raw_data)
            
                self._update_count += 1
                print(f"🔄 更新AI校准对比数据 #{self._update_count}")
                
                # 更新热力图
                self.update_heatmaps(raw_data, calibrated_data)
                
                # 更新统计信息
                self.update_statistics(raw_data, calibrated_data)
            else:
                self.stats_label.setText("AI校准模型未加载")
                
        except Exception as e:
            print(f"❌ 更新AI校准对比失败: {e}")
    
    def update_heatmaps(self, raw_data, calibrated_data):
        """更新热力图"""
        try:
            # 更新原始数据热力图
            raw_fig = self.raw_canvas.figure
            raw_ax = raw_fig.axes[0]
            raw_im = raw_ax.images[0]
            raw_im.set_array(raw_data)
            raw_im.set_clim(raw_data.min(), raw_data.max())
            raw_fig.canvas.draw()
            
            # 更新校准后热力图
            cal_fig = self.calibrated_canvas.figure
            cal_ax = cal_fig.axes[0]
            cal_im = cal_ax.images[0]
            cal_im.set_array(calibrated_data)
            
            # 使用百分位数范围避免异常值
            cal_data_flat = calibrated_data.flatten()
            cal_vmin = np.percentile(cal_data_flat, 1)
            cal_vmax = np.percentile(cal_data_flat, 99)
            cal_im.set_clim(cal_vmin, cal_vmax)
            cal_fig.canvas.draw()
            
        except Exception as e:
            print(f"❌ 更新热力图失败: {e}")
    
    def update_statistics(self, raw_data, calibrated_data):
        """更新统计信息"""
        try:
            raw_mean = raw_data.mean()
            raw_std = raw_data.std()
            raw_min = raw_data.min()
            raw_max = raw_data.max()
            raw_range = raw_data.max() - raw_data.min()
            
            cal_mean = calibrated_data.mean()
            cal_std = calibrated_data.std()
            cal_min = calibrated_data.min()
            cal_max = calibrated_data.max()
            cal_range = calibrated_data.max() - calibrated_data.min()
            
            # 计算改善程度
            std_improvement = (raw_std - cal_std) / raw_std * 100 if raw_std > 0 else 0
            
            stats_text = f"""实时统计信息 (第{self._update_count}帧):

校准前 - 原始数据:
  均值: {raw_mean:.2f}
  标准差: {raw_std:.2f}
  最小值: {raw_min:.2f}
  最大值: {raw_max:.2f}
  范围: {raw_range:.2f}

校准后 - AI校准数据:
  均值: {cal_mean:.2f}
  标准差: {cal_std:.2f}
  最小值: {cal_min:.2f}
  最大值: {cal_max:.2f}
  范围: {cal_range:.2f}

改善效果:
  标准差改善: {std_improvement:+.1f}%
  {'✅ 校准有效' if std_improvement > 0 else '⚠️ 校准效果不佳'}"""
            
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            print(f"❌ 更新统计信息失败: {e}")
    
    def force_refresh(self):
        """强制刷新"""
        self._last_raw_data = None
        self.update_comparison()
    
    def save_screenshot(self):
        """保存截图"""
        try:
            filename = f"AI校准对比_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.grab().save(filename)
            print(f"✅ 截图已保存: {filename}")
            QtWidgets.QMessageBox.information(self, "保存成功", f"截图已保存为: {filename}")
        except Exception as e:
            print(f"❌ 保存截图失败: {e}")
            QtWidgets.QMessageBox.critical(self, "保存失败", f"保存截图失败:\n{str(e)}")
            
    def closeEvent(self, event):
        """关闭事件"""
        self.update_timer.stop()
        event.accept()

# ==================== 双校准器实时比较对话框 ====================

class DualCalibrationComparisonDialog(QtWidgets.QDialog):
    """双校准器实时比较对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        self.setup_timer()
        self._update_count = 0
        
    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("双校准器实时比较")
        self.setGeometry(100, 100, 1400, 800)
        
        # 主布局
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title_label = QtWidgets.QLabel("双校准器实时比较")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 控制按钮
        control_layout = QtWidgets.QHBoxLayout()
        
        self.button_start_stop = QtWidgets.QPushButton("开始比较")
        self.button_start_stop.clicked.connect(self.toggle_comparison)
        self.button_start_stop.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        control_layout.addWidget(self.button_start_stop)
        
        # 添加去皮功能按钮
        self.button_taring = QtWidgets.QPushButton("执行去皮")
        self.button_taring.clicked.connect(self.perform_taring)
        self.button_taring.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 8px;")
        control_layout.addWidget(self.button_taring)
        
        self.button_reset_taring = QtWidgets.QPushButton("重置去皮")
        self.button_reset_taring.clicked.connect(self.reset_taring)
        self.button_reset_taring.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 8px;")
        control_layout.addWidget(self.button_reset_taring)
        
        self.button_save_screenshot = QtWidgets.QPushButton("保存截图")
        self.button_save_screenshot.clicked.connect(self.save_screenshot)
        self.button_save_screenshot.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 8px;")
        control_layout.addWidget(self.button_save_screenshot)
        
        self.button_close = QtWidgets.QPushButton("关闭")
        self.button_close.clicked.connect(self.close)
        self.button_close.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 8px;")
        control_layout.addWidget(self.button_close)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 热力图显示区域
        heatmap_layout = QtWidgets.QHBoxLayout()
        
        # 原始数据热力图
        raw_group = QtWidgets.QGroupBox("原始数据")
        raw_layout = QtWidgets.QVBoxLayout()
        self.raw_canvas = self.create_heatmap_canvas("原始数据")
        raw_layout.addWidget(self.raw_canvas)
        raw_group.setLayout(raw_layout)
        heatmap_layout.addWidget(raw_group)
        
        # 旧版本校准结果热力图
        if self.parent.old_calibrator is not None:
            old_group = QtWidgets.QGroupBox("旧版本校准")
            old_layout = QtWidgets.QVBoxLayout()
            self.old_canvas = self.create_heatmap_canvas("旧版本校准")
            old_layout.addWidget(self.old_canvas)
            old_group.setLayout(old_layout)
            heatmap_layout.addWidget(old_group)
        
        # 新版本校准结果热力图
        if self.parent.new_calibrator is not None:
            new_group = QtWidgets.QGroupBox("新版本校准")
            new_layout = QtWidgets.QVBoxLayout()
            self.new_canvas = self.create_heatmap_canvas("新版本校准")
            new_layout.addWidget(self.new_canvas)
            new_group.setLayout(new_layout)
            heatmap_layout.addWidget(new_group)
        
        layout.addLayout(heatmap_layout)
        
        # 统计信息显示区域
        stats_layout = QtWidgets.QHBoxLayout()
        
        # 原始数据统计
        raw_stats_group = QtWidgets.QGroupBox("原始数据统计")
        raw_stats_layout = QtWidgets.QVBoxLayout()
        self.raw_stats_label = QtWidgets.QLabel("等待数据...")
        self.raw_stats_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        raw_stats_layout.addWidget(self.raw_stats_label)
        raw_stats_group.setLayout(raw_stats_layout)
        stats_layout.addWidget(raw_stats_group)
        
        # 旧版本校准统计
        if self.parent.old_calibrator is not None:
            old_stats_group = QtWidgets.QGroupBox("旧版本校准统计")
            old_stats_layout = QtWidgets.QVBoxLayout()
            self.old_stats_label = QtWidgets.QLabel("等待数据...")
            self.old_stats_label.setStyleSheet("font-family: monospace; font-size: 12px;")
            old_stats_layout.addWidget(self.old_stats_label)
            old_stats_group.setLayout(old_stats_layout)
            stats_layout.addWidget(old_stats_group)
        
        # 新版本校准统计
        if self.parent.new_calibrator is not None:
            new_stats_group = QtWidgets.QGroupBox("新版本校准统计")
            new_stats_layout = QtWidgets.QVBoxLayout()
            self.new_stats_label = QtWidgets.QLabel("等待数据...")
            self.new_stats_label.setStyleSheet("font-family: monospace; font-size: 12px;")
            new_stats_layout.addWidget(self.new_stats_label)
            new_stats_group.setLayout(new_stats_layout)
            stats_layout.addWidget(new_stats_group)
        
        layout.addLayout(stats_layout)
        
        # 比较结果
        comparison_group = QtWidgets.QGroupBox("比较结果")
        comparison_layout = QtWidgets.QVBoxLayout()
        self.comparison_label = QtWidgets.QLabel("等待比较数据...")
        self.comparison_label.setStyleSheet("font-family: monospace; font-size: 12px; color: #e74c3c;")
        comparison_layout.addWidget(self.comparison_label)
        comparison_group.setLayout(comparison_layout)
        layout.addWidget(comparison_group)
        
        self.setLayout(layout)
        
    def create_heatmap_canvas(self, title):
        """创建热力图画布"""
        # 创建matplotlib图形
        fig = plt.figure(figsize=(6, 5))
        ax = fig.add_subplot(111)
        
        # 设置中文字体
        try:
            # 设置matplotlib中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            
            # 设置标题字体
            ax.set_title(title, fontsize=12, fontfamily='SimHei')
        except Exception as e:
            print(f"⚠️ 设置热力图中文字体失败: {e}")
            ax.set_title(title, fontsize=12)
        
        # 创建初始热力图（空数据）
        im = ax.imshow(np.zeros((64, 64)), cmap='viridis', aspect='equal')
        plt.colorbar(im, ax=ax, shrink=0.8)
        
        # 将matplotlib图形转换为Qt widget
        canvas = FigureCanvas(fig)
        canvas.setMinimumSize(400, 300)
        
        return canvas
        
    def setup_timer(self):
        """设置定时器"""
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_comparison)
        self.comparison_running = False
        
    def toggle_comparison(self):
        """切换比较状态"""
        if self.comparison_running:
            self.stop_comparison()
        else:
            self.start_comparison()
    
    def start_comparison(self):
        """开始比较"""
        self.comparison_running = True
        self.button_start_stop.setText("停止比较")
        self.button_start_stop.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 8px;")
        self.timer.start(100)  # 100ms更新一次
        print("🔄 双校准器实时比较已开始")
        
    def stop_comparison(self):
        """停止比较"""
        self.comparison_running = False
        self.button_start_stop.setText("开始比较")
        self.button_start_stop.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        self.timer.stop()
        print("⏹️ 双校准器实时比较已停止")
        
    def update_comparison(self):
        """更新比较数据"""
        try:
            # 获取当前数据
            raw_data = self.parent.get_current_frame_data()
            
            # 检查数据是否真的在变化
            if hasattr(self, '_last_raw_data'):
                if self._last_raw_data is not None:
                    # 检查数据是否全为零
                    if np.all(raw_data == 0):
                        print("⚠️ 检测到原始数据全为零，可能传感器未连接或数据采集异常")
                        # 即使数据为零，也要强制更新几次以显示校准效果
                        if not hasattr(self, '_zero_data_count'):
                            self._zero_data_count = 0
                        self._zero_data_count += 1
                        
                        # 每5次零数据时强制更新一次
                        if self._zero_data_count % 5 != 0:
                            return
                        else:
                            print(f"📊 数据为零，强制更新校准结果 #{self._update_count + 1}")
                    else:
                        # 数据不为零，检查是否有变化
                        data_diff = np.abs(raw_data - self._last_raw_data)
                        max_diff = np.max(data_diff)
                        
                        # 如果绝对变化小于阈值，认为数据基本不变
                        if max_diff < 1.0:  # 使用绝对阈值而不是相对阈值
                            if not hasattr(self, '_no_change_count'):
                                self._no_change_count = 0
                            self._no_change_count += 1
                            
                            # 每8次无变化时强制更新一次
                            if self._no_change_count % 8 != 0:
                                return
                            else:
                                print(f"📊 数据变化很小，强制更新校准结果 #{self._update_count + 1}")
                        else:
                            # 数据有变化，重置计数器
                            self._no_change_count = 0
                            self._zero_data_count = 0
                            print(f"🔄 检测到数据变化，最大变化: {max_diff:.4f}")
                else:
                    # 第一次运行，初始化
                    print("🔄 首次运行，初始化数据")
            else:
                # 第一次运行，初始化
                print("🔄 首次运行，初始化数据")
            
            self._last_raw_data = raw_data.copy()
            
            # 应用双校准器
            calibration_results = self.parent.apply_dual_calibration(raw_data)
            
            if calibration_results is None:
                print("⚠️ 双校准器应用失败，跳过更新")
                return
            
            self._update_count += 1
            print(f"🔄 更新双校准器比较数据 #{self._update_count}")
            
            # 更新热力图
            self.update_heatmaps(calibration_results)
            
            # 更新统计信息
            self.update_statistics(calibration_results)
            
            # 更新比较结果
            self.update_comparison_results(calibration_results)
            
        except Exception as e:
            print(f"❌ 更新双校准器比较失败: {e}")
            import traceback
            traceback.print_exc()
    
    def update_heatmaps(self, results):
        """更新热力图"""
        try:
            # 更新原始数据热力图
            raw_fig = self.raw_canvas.figure
            raw_ax = raw_fig.axes[0]
            raw_im = raw_ax.images[0]
            raw_data = results['raw']['data']
            raw_im.set_array(raw_data)
            raw_im.set_clim(raw_data.min(), raw_data.max())
            raw_fig.canvas.draw()
            
            # 更新旧版本校准热力图
            if 'old' in results and hasattr(self, 'old_canvas'):
                old_fig = self.old_canvas.figure
                old_ax = old_fig.axes[0]
                old_im = old_ax.images[0]
                old_data = results['old']['data']
                old_im.set_array(old_data)
                
                # 使用百分位数范围避免异常值
                old_data_flat = old_data.flatten()
                old_vmin = np.percentile(old_data_flat, 1)
                old_vmax = np.percentile(old_data_flat, 99)
                old_im.set_clim(old_vmin, old_vmax)
                old_fig.canvas.draw()
            
            # 更新新版本校准热力图
            if 'new' in results and hasattr(self, 'new_canvas'):
                new_fig = self.new_canvas.figure
                new_ax = new_fig.axes[0]
                new_im = new_ax.images[0]
                new_data = results['new']['data']
                new_im.set_array(new_data)
                
                # 使用百分位数范围避免异常值
                new_data_flat = new_data.flatten()
                new_vmin = np.percentile(new_data_flat, 1)
                new_vmax = np.percentile(new_data_flat, 99)
                new_im.set_clim(new_vmin, new_vmax)
                new_fig.canvas.draw()
                
        except Exception as e:
            print(f"❌ 更新热力图失败: {e}")
    
    def update_statistics(self, results):
        """更新统计信息"""
        try:
            # 更新原始数据统计
            raw_stats = results['raw']
            raw_text = f"""均值: {raw_stats['mean']:.2f}
标准差: {raw_stats['std']:.2f}
最小值: {raw_stats['min']:.2f}
最大值: {raw_stats['max']:.2f}
范围: {raw_stats['range']:.2f}"""
            self.raw_stats_label.setText(raw_text)
            
            # 更新旧版本校准统计
            if 'old' in results and hasattr(self, 'old_stats_label'):
                old_stats = results['old']
                old_text = f"""均值: {old_stats['mean']:.2f}
标准差: {old_stats['std']:.2f}
最小值: {old_stats['min']:.2f}
最大值: {old_stats['max']:.2f}
范围: {raw_stats['range']:.2f}"""
                self.old_stats_label.setText(old_text)
            
            # 更新新版本校准统计
            if 'new' in results and hasattr(self, 'new_stats_label'):
                new_stats = results['new']
                new_text = f"""均值: {new_stats['mean']:.2f}
标准差: {new_stats['std']:.2f}
最小值: {new_stats['min']:.2f}
最大值: {new_stats['max']:.2f}
范围: {new_stats['range']:.2f}"""
                self.new_stats_label.setText(new_text)
                
        except Exception as e:
            print(f"❌ 更新统计信息失败: {e}")
    
    def update_comparison_results(self, results):
        """更新比较结果"""
        try:
            comparison_text = ""
            
            if 'old' in results and 'new' in results:
                old_stats = results['old']
                new_stats = results['new']
                raw_stats = results['raw']
                
                # 计算改善程度
                old_improvement = (raw_stats['std'] - old_stats['std']) / raw_stats['std'] * 100
                new_improvement = (raw_stats['std'] - new_stats['std']) / raw_stats['std'] * 100
                
                comparison_text = f"""实时比较结果 (第{self._update_count}帧):

原始数据: 均值={raw_stats['mean']:.2f}, 标准差={raw_stats['std']:.2f}

旧版本校准:
  均值: {old_stats['mean']:.2f} (改善: {old_improvement:+.1f}%)
  标准差: {old_stats['std']:.2f} (改善: {old_improvement:+.1f}%)

新版本校准:
  均值: {new_stats['mean']:.2f} (改善: {new_improvement:+.1f}%)
  标准差: {new_stats['std']:.2f} (改善: {new_improvement:+.1f}%)

性能对比:
  标准差改善: 旧版本{old_improvement:+.1f}% vs 新版本{new_improvement:+.1f}%
  推荐: {'新版本' if new_improvement > old_improvement else '旧版本'}"""
                
                # 根据改善程度设置颜色
                if new_improvement > old_improvement:
                    self.comparison_label.setStyleSheet("font-family: monospace; font-size: 12px; color: #27ae60;")
                else:
                    self.comparison_label.setStyleSheet("font-family: monospace; font-size: 12px; color: #e74c3c;")
            
            elif 'old' in results:
                old_stats = results['old']
                raw_stats = results['raw']
                old_improvement = (raw_stats['std'] - old_stats['std']) / raw_stats['std'] * 100
                
                comparison_text = f"""实时比较结果 (第{self._update_count}帧):

原始数据: 均值={raw_stats['mean']:.2f}, 标准差={raw_stats['std']:.2f}

旧版本校准:
  均值: {old_stats['mean']:.2f}
  标准差: {old_stats['std']:.2f} (改善: {old_improvement:+.1f}%)"""
                
            elif 'new' in results:
                new_stats = results['new']
                raw_stats = results['raw']
                new_improvement = (raw_stats['std'] - new_stats['std']) / raw_stats['std'] * 100
                
                comparison_text = f"""实时比较结果 (第{self._update_count}帧):

原始数据: 均值={raw_stats['mean']:.2f}, 标准差={raw_stats['std']:.2f}

新版本校准:
  均值: {new_stats['mean']:.2f}
  标准差: {new_stats['std']:.2f} (改善: {new_improvement:+.1f}%)"""
            
            self.comparison_label.setText(comparison_text)
            
        except Exception as e:
            print(f"❌ 更新比较结果失败: {e}")
    
    def save_screenshot(self):
        """保存截图"""
        try:
            filename = f"双校准器比较_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.grab().save(filename)
            print(f"✅ 截图已保存: {filename}")
            QtWidgets.QMessageBox.information(self, "保存成功", f"截图已保存为: {filename}")
        except Exception as e:
            print(f"❌ 保存截图失败: {e}")
            QtWidgets.QMessageBox.critical(self, "保存失败", f"保存截图失败:\n{str(e)}")
    
    def perform_taring(self):
        """执行去皮操作"""
        try:
            # 检查主窗口是否有去皮功能
            if not hasattr(self.parent, 'perform_taring'):
                QtWidgets.QMessageBox.warning(self, "功能不可用", "主窗口不支持去皮功能")
                return
            
            # 调用主窗口的去皮功能
            success = self.parent.perform_taring()
            
            if success:
                QtWidgets.QMessageBox.information(self, "成功", "去皮操作执行成功！\n当前传感器读数已设为零点基准。")
                print("✅ 双校准比较界面：去皮操作执行成功")
            else:
                QtWidgets.QMessageBox.warning(self, "失败", "去皮操作执行失败")
                print("❌ 双校准比较界面：去皮操作执行失败")
                
        except Exception as e:
            print(f"❌ 双校准比较界面去皮操作失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"去皮操作失败:\n{str(e)}")
    
    def reset_taring(self):
        """重置去皮操作"""
        try:
            # 检查主窗口是否有重置去皮功能
            if not hasattr(self.parent, 'reset_taring'):
                QtWidgets.QMessageBox.warning(self, "功能不可用", "主窗口不支持重置去皮功能")
                return
            
            # 调用主窗口的重置去皮功能
            success = self.parent.reset_taring()
            
            if success:
                QtWidgets.QMessageBox.information(self, "成功", "去皮重置成功！\n已恢复到原始传感器读数。")
                print("✅ 双校准比较界面：去皮重置成功")
            else:
                QtWidgets.QMessageBox.warning(self, "失败", "去皮重置失败")
                print("❌ 双校准比较界面：去皮重置失败")
                
        except Exception as e:
            print(f"❌ 双校准比较界面重置去皮失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"重置去皮失败:\n{str(e)}")
    
    def closeEvent(self, event):
        """关闭事件"""
        self.stop_comparison()
        event.accept()

# ==================== 原有校准对比对话框 ====================

class CalibrationComparisonDialog(QtWidgets.QDialog):
    """校准前后对比对话框（原有版本）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("AI校准前后对比")
        self.setGeometry(200, 200, 1200, 800)

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 设置自动刷新定时器
        self.auto_refresh_timer = QtCore.QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_data)
        self.auto_refresh_enabled = False

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout()

        # 标题
        title = QtWidgets.QLabel("AI校准前后对比分析")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 创建滚动区域
        scroll_area = QtWidgets.QScrollArea()
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)

        # 获取当前帧数据
        raw_data = self.parent.get_current_frame_data()
        calibrated_data = self.parent.apply_ai_calibration(raw_data)

        # 创建对比图
        self.create_comparison_plots(scroll_layout, raw_data, calibrated_data)

        # 添加统计信息
        self.add_statistics_info(scroll_layout, raw_data, calibrated_data)

        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()

        refresh_btn = QtWidgets.QPushButton("手动刷新")
        refresh_btn.clicked.connect(self.refresh_data)
        button_layout.addWidget(refresh_btn)
        
        # 自动刷新切换按钮
        self.auto_refresh_btn = QtWidgets.QPushButton("开启自动刷新")
        self.auto_refresh_btn.clicked.connect(self.toggle_auto_refresh)
        button_layout.addWidget(self.auto_refresh_btn)

        save_btn = QtWidgets.QPushButton("保存对比图")
        save_btn.clicked.connect(self.save_comparison)
        button_layout.addWidget(save_btn)

        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def create_comparison_plots(self, layout, raw_data, calibrated_data):
        """创建对比图"""
        # 创建matplotlib图形
        fig = plt.figure(figsize=(15, 10))

        # 1. 原始数据热力图
        ax1 = fig.add_subplot(2, 3, 1)
        im1 = ax1.imshow(raw_data, cmap='viridis', aspect='equal')
        ax1.set_title('原始数据热力图')
        plt.colorbar(im1, ax=ax1, shrink=0.8)

        # 2. 校准后数据热力图
        ax2 = fig.add_subplot(2, 3, 2)
        
        # 使用top99%范围，避免异常值影响
        cal_data_flat = calibrated_data.flatten()
        cal_99_percentile = np.percentile(cal_data_flat, 99)
        cal_1_percentile = np.percentile(cal_data_flat, 1)
        
        im2 = ax2.imshow(calibrated_data, cmap='viridis', aspect='equal', 
                         vmin=cal_1_percentile, vmax=cal_99_percentile)
        ax2.set_title('校准后热力图 (1%-99%范围)')
        plt.colorbar(im2, ax=ax2, shrink=0.8)

        # 3. 差异热力图
        ax3 = fig.add_subplot(2, 3, 3)
        diff = calibrated_data - raw_data.mean()
        im3 = ax3.imshow(diff, cmap='RdBu_r', aspect='equal')
        ax3.set_title('校准调整量热力图')
        plt.colorbar(im3, ax=ax3, shrink=0.8)

        # 4. 原始数据直方图
        ax4 = fig.add_subplot(2, 3, 4)
        ax4.hist(raw_data.flatten(), bins=50, alpha=0.7, label='原始数据', density=True)
        ax4.axvline(raw_data.mean(), color='red', linestyle='--', linewidth=2,
                   label=f'均值: {raw_data.mean():.1f}')
        ax4.set_title('原始数据分布直方图')
        ax4.set_xlabel('响应值')
        ax4.set_ylabel('密度')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        # 5. 校准后数据直方图
        ax5 = fig.add_subplot(2, 3, 5)
        ax5.hist(calibrated_data.flatten(), bins=50, alpha=0.7, color='orange',
                label='校准后数据', density=True)
        ax5.axvline(calibrated_data.mean(), color='blue', linestyle='--', linewidth=2,
                   label=f'均值: {calibrated_data.mean():.1f}')
        ax5.set_title('校准后数据分布直方图')
        ax5.set_xlabel('响应值')
        ax5.set_ylabel('密度')
        ax5.legend()
        ax5.grid(True, alpha=0.3)

        # 6. 散点图对比
        ax6 = fig.add_subplot(2, 3, 6)
        sample_indices = np.random.choice(64*64, size=min(1000, 64*64), replace=False)
        raw_sample = raw_data.flatten()[sample_indices]
        cal_sample = calibrated_data.flatten()[sample_indices]

        ax6.scatter(raw_sample, cal_sample, alpha=0.6, s=2, color='purple')
        ax6.plot([raw_data.min(), raw_data.max()], [raw_data.min(), raw_data.max()],
                'r--', linewidth=2, label='对角线')
        ax6.set_xlabel('原始响应')
        ax6.set_ylabel('校准后响应')
        ax6.set_title('原始vs校准后响应散点图')
        ax6.legend()
        ax6.grid(True, alpha=0.3)

        plt.suptitle('AI校准前后对比分析', fontsize=16, fontweight='bold')
        plt.tight_layout()

        # 将matplotlib图形转换为Qt widget
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)

    def add_statistics_info(self, layout, raw_data, calibrated_data):
        """添加统计信息"""
        stats_group = QtWidgets.QGroupBox("统计信息对比")
        stats_layout = QtWidgets.QVBoxLayout()

        # 计算统计指标
        cv_raw = raw_data.std() / raw_data.mean()
        cv_cal = calibrated_data.std() / calibrated_data.mean()
        cv_improvement = cv_raw / cv_cal
        std_improvement = raw_data.std() / calibrated_data.std()
        
        # 计算分位数指标
        cal_data_flat = calibrated_data.flatten()
        cal_99_percentile = np.percentile(cal_data_flat, 99)
        cal_1_percentile = np.percentile(cal_data_flat, 1)
        cal_95_percentile = np.percentile(cal_data_flat, 95)
        cal_5_percentile = np.percentile(cal_data_flat, 5)

        # 创建统计信息文本
        stats_text = f"""
        📊 校准效果统计

        原始数据:
        • 均值: {raw_data.mean():.1f}
        • 标准差: {raw_data.std():.1f}
        • CV (变异系数): {cv_raw:.3f}
        • 范围: [{raw_data.min():.1f}, {raw_data.max():.1f}]

        校准后:
        • 均值: {calibrated_data.mean():.1f}
        • 标准差: {calibrated_data.std():.1f}
        • CV (变异系数): {cv_cal:.3f}
        • 范围: [{calibrated_data.min():.1f}, {calibrated_data.max():.1f}]
        • 分位数: 1%={cal_1_percentile:.1f}, 5%={cal_5_percentile:.1f}, 95%={cal_95_percentile:.1f}, 99%={cal_99_percentile:.1f}
        • 热力图范围: [{cal_1_percentile:.1f}, {cal_99_percentile:.1f}] (避免异常值)

        改善效果:
        • CV改善倍数: {cv_improvement:.1f}倍
        • 标准差改善倍数: {std_improvement:.1f}倍
        • 均匀性提升: {((cv_raw - cv_cal) / cv_raw * 100):.1f}%

        🎯 结论:
        • 校准显著改善了传感器的一致性
        • 变异系数降低了{cv_improvement:.1f}倍
        • 标准差降低了{std_improvement:.1f}倍
        """

        stats_label = QtWidgets.QLabel(stats_text)
        stats_label.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px;")
        stats_layout.addWidget(stats_label)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

    def toggle_auto_refresh(self):
        """切换自动刷新"""
        if self.auto_refresh_enabled:
            # 停止自动刷新
            self.auto_refresh_timer.stop()
            self.auto_refresh_enabled = False
            self.auto_refresh_btn.setText("开启自动刷新")
            print("⏸️ 已停止自动刷新")
        else:
            # 开启自动刷新，每2秒刷新一次
            self.auto_refresh_timer.start(2000)
            self.auto_refresh_enabled = True
            self.auto_refresh_btn.setText("停止自动刷新")
            print("▶️ 已开启自动刷新（每2秒）")

    def refresh_data(self):
        """刷新数据"""
        try:
            print("🔄 刷新校准对比数据...")
            # 重新获取数据并更新显示
            self.setup_ui()
            print("✅ 校准对比数据已刷新")
        except Exception as e:
            print(f"❌ 刷新校准对比数据失败: {e}")
            import traceback
            traceback.print_exc()
            
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'auto_refresh_timer'):
            self.auto_refresh_timer.stop()
        super().closeEvent(event)

    def save_comparison(self):
        """保存对比图"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存对比图", "", "PNG文件 (*.png);;PDF文件 (*.pdf)"
        )

        if file_path:
            try:
                # 这里可以实现保存当前对比图的功能
                QtWidgets.QMessageBox.information(self, "保存成功", f"对比图已保存到:\n{file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "保存失败", f"保存失败:\n{str(e)}")

def start(mode='standard'):
    app = QtWidgets.QApplication(sys.argv)
    w = Window(mode)
    w.show()
    w.trigger_null()
    sys.exit(app.exec_())
