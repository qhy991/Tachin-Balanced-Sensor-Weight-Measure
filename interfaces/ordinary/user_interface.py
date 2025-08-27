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

# 导入拆分的模块
from .ai_calibration import AICalibrationAdapter, AICalibrationManager
from .core import TaringHandler, CalibrationHandler
from .dialogs import RealtimeCalibrationDialog
#
AVAILABLE_FILTER_NAMES = ['无', '中值-0.2s', '中值-1s', '均值-0.2s', '均值-1s', '单向抵消-轻', '单向抵消-中', '单向抵消-重']


# AICalibrationAdapter类已移动到 .ai_calibration.adapter 模块


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

        # 初始化拆分的模块
        self.calibration_manager = AICalibrationManager(self)
        self.taring_handler = TaringHandler(self, self.calibration_manager)
        self.calibration_handler = CalibrationHandler(self, self.calibration_manager)
        
        # 向后兼容的校准相关变量
        self.calibration_coeffs = None
        self.device = torch.device("cpu")
        self.dual_calibration_mode = False
        self.old_calibrator = None
        self.new_calibrator = None
        self.comparison_dialog = None
        self.zero_offset = None
        self.taring_enabled = False

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
        
        # 延迟设置新版本校准系统菜单（确保窗口完全显示后）
        self.setup_calibration_menu()

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

        # 新版本校准系统功能现在通过菜单栏的"新版本校准系统"菜单访问，界面更加整洁
        print("🔧 新版本校准系统功能已集成到菜单栏，无需额外按钮")
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

            # 如果有新版本校准模型，对最新数据应用新版本校准
            if self.calibration_coeffs is not None and len(self.data_handler.value) > 0:
                latest_raw_data = self.data_handler.value[-1]

                # 保存原始数据副本（用于对比）
                if not hasattr(self, '_raw_data_for_comparison'):
                    self._raw_data_for_comparison = []
                
                # 保持最近10帧的原始数据
                self._raw_data_for_comparison.append(latest_raw_data.copy())
                if len(self._raw_data_for_comparison) > 10:
                    self._raw_data_for_comparison.pop(0)

                # 应用新版本校准
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
            calibration_status.append('新版本校准')

        if calibration_status:
            ret += f' | 校准: {", ".join(calibration_status)}'

        return ret

    # ==================== 新版本校准功能 ====================
    
    def __load_ai_calibration(self):
        """加载新版本校准模型"""
        try:
            # 尝试从当前目录加载
            current_dir = os.getcwd()
            coeffs_path = os.path.join(current_dir, 'calibration_coeffs.pt')

            if not os.path.exists(coeffs_path):
                # 如果不存在，尝试从其他可能路径加载
                possible_paths = [
                    'calibration_coeffs.pt',
                    '../calibration_coeffs.pt',
                    '../../calibration_coeffs.pt',
                    'data-0815/../calibration_coeffs.pt'
                ]

                for path in possible_paths:
                    if os.path.exists(path):
                        coeffs_path = path
                        break

            if os.path.exists(coeffs_path):
                self.calibration_coeffs = torch.load(coeffs_path).to(self.device)
                print(f"✅ 新版本校准模型加载成功: {coeffs_path}")
                print(f"   模型形状: {self.calibration_coeffs.shape}")

                # 显示成功消息
                QtWidgets.QMessageBox.information(self, "成功",
                    f"新版本校准模型已加载!\n路径: {coeffs_path}\n形状: {self.calibration_coeffs.shape}")

            else:
                QtWidgets.QMessageBox.warning(self, "文件未找到",
                    f"未找到校准文件: calibration_coeffs.pt\n请先运行校准训练脚本。")
                return False

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "加载失败", f"加载新版本校准模型失败:\n{str(e)}")
            return False

        return True

    def apply_ai_calibration(self, raw_data_64x64):
        """应用新版本校准到64x64原始数据"""
        if self.calibration_coeffs is None:
            return raw_data_64x64

        try:
            # 将数据转换为tensor
            raw_tensor = torch.from_numpy(raw_data_64x64).float().to(self.device)

            # 展平数据
            raw_flat = raw_tensor.view(-1)

            # 应用校准函数：y = a*x² + b*x + c
            x = raw_flat
            a = self.calibration_coeffs[:, 0]
            b = self.calibration_coeffs[:, 1]
            c = self.calibration_coeffs[:, 2]

            calibrated_flat = a * x**2 + b * x + c

            # 恢复形状
            calibrated_tensor = calibrated_flat.view(64, 64)
            calibrated_data = calibrated_tensor.cpu().numpy()

            # 添加数据范围限制，避免校准后数据过于极端
            raw_range = raw_data_64x64.max() - raw_data_64x64.min()
            if raw_range > 0:
                # 限制校准后数据的范围不超过原始数据的5倍
                max_allowed_range = raw_range * 5
                calibrated_range = calibrated_data.max() - calibrated_data.min()
                
                if calibrated_range > max_allowed_range:
                    print(f"⚠️ 校准后数据范围过大: {calibrated_range:.1f} > {max_allowed_range:.1f}")
                    print(f"   原始范围: {raw_range:.1f}, 校准后范围: {calibrated_range:.1f}")
                    print(f"   将限制校准后数据范围")
                    
                    # 显示校准系数信息（调试用）
                    coeffs_cpu = self.calibration_coeffs.cpu()
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

            return calibrated_data

        except Exception as e:
            print(f"❌ 应用新版本校准失败: {e}")
            return raw_data_64x64

    def show_ai_calibration_info(self):
        """显示新版本校准信息"""
        try:
            if self.calibration_coeffs is None:
                QtWidgets.QMessageBox.information(self, "信息", "未加载新版本校准模型")
                return

            # 获取模型信息
            model_shape = self.calibration_coeffs.shape
            device_info = str(self.device)

            info_text = f"新版本校准模型信息:\n\n"
            info_text += f"模型形状: {model_shape}\n"
            info_text += f"设备: {device_info}\n"
            info_text += f"数据类型: {self.calibration_coeffs.dtype}\n"
            info_text += f"模型大小: {self.calibration_coeffs.numel()} 参数\n"

            # 显示校准系数统计
            coeffs_cpu = self.calibration_coeffs.cpu()
            info_text += f"\n校准系数统计:\n"
            info_text += f"a系数范围: [{coeffs_cpu[:, 0].min():.4f}, {coeffs_cpu[:, 0].max():.4f}]\n"
            info_text += f"b系数范围: [{coeffs_cpu[:, 1].min():.4f}, {coeffs_cpu[:, 1].max():.4f}]\n"
            info_text += f"c系数范围: [{coeffs_cpu[:, 2].min():.4f}, {coeffs_cpu[:, 2].max():.4f}]\n"

            QtWidgets.QMessageBox.information(self, "新版本校准模型信息", info_text)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"显示新版本校准信息失败:\n{str(e)}")

    def __show_calibration_comparison(self):
        """显示校准前后对比"""
        try:
            if self.calibration_coeffs is None:
                QtWidgets.QMessageBox.warning(self, "警告", "请先加载新版本校准模型")
                return

            # 这里可以添加校准前后对比的逻辑
            QtWidgets.QMessageBox.information(self, "信息", "校准前后对比功能开发中...")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"显示校准对比失败:\n{str(e)}")

    def perform_taring(self):
        """执行去皮校准"""
        try:
            # 这里可以添加去皮校准的逻辑
            QtWidgets.QMessageBox.information(self, "信息", "去皮校准功能开发中...")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"执行去皮校准失败:\n{str(e)}")

    def reset_taring(self):
        """重置去皮校准"""
        try:
            # 这里可以添加重置去皮校准的逻辑
            QtWidgets.QMessageBox.information(self, "信息", "重置去皮校准功能开发中...")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"重置去皮校准失败:\n{str(e)}")

    # ==================== 双校准器比较功能 ====================
    
    def load_dual_calibrators(self):
        """同时加载新旧两种校准器 - 已委托给calibration_handler"""
        return self.calibration_handler.load_dual_calibrators()
    
    def start_dual_calibration_comparison(self):
        """启动双校准器实时比较 - 已委托给calibration_handler"""
        return self.calibration_handler.start_dual_calibration_comparison()
    
    def apply_dual_calibration(self, raw_data_64x64):
        """应用双校准器校准并返回比较结果 - 已委托给calibration_manager"""
        return self.calibration_manager.apply_dual_calibration(raw_data_64x64)
    
    def get_dual_calibration_info(self):
        """获取双校准器信息 - 已委托给calibration_manager"""
        return self.calibration_manager.get_dual_calibration_info()
    
    def perform_taring(self):
        """执行去皮操作 - 在无按压状态下校准零点（逐点去皮） - 已委托给taring_handler"""
        return self.taring_handler.perform_taring()
    
    def reset_taring(self):
        """重置去皮功能 - 已委托给taring_handler"""
        return self.taring_handler.reset_taring()
    
    def apply_taring_correction(self, calibrated_data):
        """应用去皮校正（逐点去皮） - 已委托给taring_handler"""
        return self.taring_handler.apply_taring_correction(calibrated_data)

    def __show_calibration_comparison(self):
        """显示校准前后对比 - 已委托给calibration_handler"""
        return self.calibration_handler.show_calibration_comparison()
        
    def __show_detailed_calibration_comparison(self):
        """显示详细校准对比 - 已委托给calibration_handler"""
        return self.calibration_handler.show_detailed_calibration_comparison()

    def get_current_frame_data(self):
        """获取当前帧的原始数据（用于校准对比） - 已委托给calibration_handler"""
        return self.calibration_handler.get_current_frame_data()

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
            
            # 创建新版本校准系统菜单
            self.menu_ai_calibration = self.menubar.addMenu("新版本校准系统")
            
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
            
            print("✅ 新版本校准系统菜单已创建，样式设置为白色背景")

            # 加载双校准器
            action_load_dual = QtWidgets.QAction("📥 载入双校准器", self)
            action_load_dual.triggered.connect(self.load_dual_calibrators)
            self.menu_ai_calibration.addAction(action_load_dual)
            print("✅ 载入双校准器菜单项已添加")
            
            # 启动双校准器比较
            action_start_comparison = QtWidgets.QAction("🚀 启动实时监控", self)
            action_start_comparison.triggered.connect(self.start_dual_calibration_comparison)
            self.menu_ai_calibration.addAction(action_start_comparison)
            print("✅ 启动实时监控菜单项已添加")
            
            # 分隔线
            self.menu_ai_calibration.addSeparator()
            print("✅ 分隔线1已添加")
            
            # 显示AI校准信息
            action_show_info = QtWidgets.QAction("📊 显示校准信息", self)
            action_show_info.triggered.connect(self.show_ai_calibration_info)
            self.menu_ai_calibration.addAction(action_show_info)
            print("✅ 显示校准信息菜单项已添加")
            
            # 显示双校准器信息
            action_show_dual_info = QtWidgets.QAction("📋 显示系统状态", self)
            action_show_dual_info.triggered.connect(self.__show_dual_calibration_info)
            self.menu_ai_calibration.addAction(action_show_dual_info)
            print("✅ 显示系统状态菜单项已添加")
            
            # 分隔线
            self.menu_ai_calibration.addSeparator()
            print("✅ 分隔线2已添加")
            
            # 校准前后对比
            action_show_comparison = QtWidgets.QAction("📈 校准效果对比", self)
            action_show_comparison.triggered.connect(self.__show_calibration_comparison)
            self.menu_ai_calibration.addAction(action_show_comparison)
            print("✅ 校准效果对比菜单项已添加")
            
            # 分隔线
            self.menu_ai_calibration.addSeparator()
            print("✅ 分隔线3已添加")
            
            # 去皮功能
            action_perform_taring = QtWidgets.QAction("⚖️ 执行去皮校准", self)
            action_perform_taring.triggered.connect(self.perform_taring)
            self.menu_ai_calibration.addAction(action_perform_taring)
            print("✅ 执行去皮校准菜单项已添加")
            
            action_reset_taring = QtWidgets.QAction("🔄 重置去皮校准", self)
            action_reset_taring.triggered.connect(self.reset_taring)
            self.menu_ai_calibration.addAction(action_reset_taring)
            
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
            print(f"📋 新版本校准系统菜单中的项目数量: {len(actions)}")
            
            for i, action in enumerate(actions):
                if action.isSeparator():
                    print(f"   项目 {i+1}: [分隔线]")
                else:
                    print(f"   项目 {i+1}: {action.text()}")
            
            # 显示所有菜单
            all_menus = self.menubar.findChildren(QtWidgets.QMenu)
            print(f"📋 菜单栏中的所有菜单: {[menu.title() for menu in all_menus]}")
            
            # 强制显示菜单
            if hasattr(self, 'menu_ai_calibration') and self.menu_ai_calibration is not None:
                self.menu_ai_calibration.setVisible(True)
                self.menu_ai_calibration.setEnabled(True)
                print("✅ 新版本校准系统菜单已启用并可见")
            else:
                print("⚠️ 新版本校准系统菜单未找到")
            
            print("✅ 新版本校准系统菜单设置完成")

        except Exception as e:
            print(f"❌ 设置新版本校准系统菜单失败: {e}")
            import traceback
            traceback.print_exc()

    def __show_dual_calibration_info(self):
        """显示双校准器信息 - 已委托给calibration_handler"""
        return self.calibration_handler.show_dual_calibration_info()
            

    
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
                
                # 确保新版本校准系统菜单也可见
                if hasattr(self, 'menu_ai_calibration') and self.menu_ai_calibration is not None:
                    self.menu_ai_calibration.setVisible(True)
                    self.menu_ai_calibration.setEnabled(True)
                    print("✅ 新版本校准系统菜单已设置为可见")
        except Exception as e:
            print(f"⚠️ 延迟设置菜单栏可见失败: {e}")
            


    def _setup_calibration_menu_delayed(self):
        """延迟设置新版本校准系统菜单"""
        try:
            print("🔧 延迟设置新版本校准系统菜单...")
            self.setup_calibration_menu()
            print("✅ 延迟设置新版本校准系统菜单完成")
        except Exception as e:
            print(f"❌ 延迟设置新版本校准系统菜单失败: {e}")
            import traceback
            traceback.print_exc()

# ==================== 实时校准对比对话框 ====================
# 已迁移到 .dialogs.realtime_calibration_dialog 模块

def start(mode='standard'):
    app = QtWidgets.QApplication(sys.argv)
    w = Window(mode)
    w.show()
    w.trigger_null()
    sys.exit(app.exec_())
