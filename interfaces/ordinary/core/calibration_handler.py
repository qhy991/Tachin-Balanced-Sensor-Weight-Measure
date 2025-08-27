"""
校准处理模块

负责处理校准相关的功能，包括校准信息显示、双校准器比较等
"""

import os
import numpy as np
from PyQt5 import QtWidgets
from ..ai_calibration.adapter import AICalibrationAdapter


class CalibrationHandler:
    """校准处理器"""
    
    def __init__(self, parent_window, calibration_manager):
        self.parent = parent_window
        self.calibration_manager = calibration_manager
    
    def setup_calibration_menu(self):
        """设置AI校准菜单"""
        try:
            print("🔧 开始设置AI校准菜单...")
            
            # 检查menubar是否存在
            if not hasattr(self.parent, 'menubar') or self.parent.menubar is None:
                print("❌ 菜单栏不存在，尝试创建...")
                # 尝试创建菜单栏
                self.parent.menubar = QtWidgets.QMenuBar(self.parent)
                self.parent.setMenuBar(self.parent.menubar)
                print("✅ 已创建新的菜单栏")
            
            # 确保菜单栏可见和启用
            self.parent.menubar.setVisible(True)
            self.parent.menubar.setHidden(False)
            self.parent.menubar.setEnabled(True)
            self.parent.menubar.raise_()
            
            print(f"✅ 菜单栏状态: 可见={self.parent.menubar.isVisible()}, 启用={self.parent.menubar.isEnabled()}")
            
            # 创建AI校准菜单
            self.parent.menu_ai_calibration = self.parent.menubar.addMenu("AI校准")
            
            # 设置菜单样式 - 纯白色背景，更美观
            self.parent.menu_ai_calibration.setStyleSheet("""
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
            action_load_model = QtWidgets.QAction("加载AI校准模型", self.parent)
            action_load_model.triggered.connect(self.parent._load_ai_calibration)
            self.parent.menu_ai_calibration.addAction(action_load_model)
            print("✅ 加载AI校准模型菜单项已添加")
            
            # 🆕 修改：加载新版本校准器
            action_load_new = QtWidgets.QAction("加载新版本校准器", self.parent)
            action_load_new.triggered.connect(self.load_new_calibrator)
            self.parent.menu_ai_calibration.addAction(action_load_new)
            print("✅ 加载新版本校准器菜单项已添加")
            
            # 🆕 修改：显示新版本校准器信息
            action_show_new_info = QtWidgets.QAction("显示新版本校准器信息", self.parent)
            action_show_new_info.triggered.connect(self._show_new_calibrator_info)
            self.parent.menu_ai_calibration.addAction(action_show_new_info)
            print("✅ 显示新版本校准器信息菜单项已添加")
            
            # 分隔线
            self.parent.menu_ai_calibration.addSeparator()
            print("✅ 分隔线2已添加")
            
            # 🆕 修改：新版本校准器实时监控
            action_show_monitoring = QtWidgets.QAction("新版本校准器实时监控", self.parent)
            action_show_monitoring.triggered.connect(self.start_new_calibration_monitoring)
            self.parent.menu_ai_calibration.addAction(action_show_monitoring)
            print("✅ 新版本校准器实时监控菜单项已添加")
            
            # 分隔线
            self.parent.menu_ai_calibration.addSeparator()
            print("✅ 分隔线3已添加")
            
            # 去皮功能
            action_perform_taring = QtWidgets.QAction("执行去皮", self.parent)
            action_perform_taring.triggered.connect(self.parent.perform_taring)
            self.parent.menu_ai_calibration.addAction(action_perform_taring)
            print("✅ 执行去皮菜单项已添加")
            
            action_reset_taring = QtWidgets.QAction("重置去皮", self.parent)
            action_reset_taring.triggered.connect(self.parent.reset_taring)
            self.parent.menu_ai_calibration.addAction(action_reset_taring)
            print("✅ 重置去皮菜单项已添加")
            
            # 设置整个菜单栏的样式 - 白色背景
            self.parent.menubar.setStyleSheet("""
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
            self.parent.menubar.updateGeometry()
            self.parent.menubar.repaint()
            
            # 验证菜单项是否正确添加
            actions = self.parent.menu_ai_calibration.actions()
            print(f"📋 AI校准菜单中的项目数量: {len(actions)}")
            
            for i, action in enumerate(actions):
                if action.isSeparator():
                    print(f"   项目 {i+1}: [分隔线]")
                else:
                    print(f"   项目 {i+1}: {action.text()}")
            
            # 显示所有菜单
            all_menus = self.parent.menubar.findChildren(QtWidgets.QMenu)
            print(f"📋 菜单栏中的所有菜单: {[menu.title() for menu in all_menus]}")
            
            # 强制显示菜单
            self.parent.menu_ai_calibration.setVisible(True)
            self.parent.menu_ai_calibration.setEnabled(True)
            
            print("✅ AI校准菜单设置完成")

        except Exception as e:
            print(f"❌ 设置AI校准菜单失败: {e}")
            import traceback
            traceback.print_exc()
    
    def show_ai_calibration_info(self):
        """显示AI校准信息"""
        try:
            if self.calibration_manager.calibration_coeffs is None:
                QtWidgets.QMessageBox.information(self.parent, "AI校准信息", 
                    "当前未加载AI校准模型。\n\n请先选择'加载AI校准模型'来加载校准文件。")
                return
            
            # 获取校准信息
            info = self.calibration_manager.get_info()
            if info is None:
                QtWidgets.QMessageBox.warning(self.parent, "信息获取失败", "无法获取校准信息")
                return
            
            # 构建信息文本
            info_text = f"AI校准模型信息:\n\n"
            info_text += f"校准格式: {info['calibration_format']}\n"
            info_text += f"系数形状: {info['coeffs_shape']}\n"
            info_text += f"计算设备: {info['device']}\n\n"
            
            if info['coeffs_range']:
                coeffs = info['coeffs_range']
                info_text += f"校准系数范围:\n"
                info_text += f"  二次项(a): [{coeffs['a'][0]:.4f}, {coeffs['a'][1]:.4f}]\n"
                info_text += f"  一次项(b): [{coeffs['b'][0]:.4f}, {coeffs['b'][1]:.4f}]\n"
                info_text += f"  常数项(c): [{coeffs['c'][0]:.4f}, {coeffs['c'][1]:.4f}]\n\n"
            
            if info['calibration_format'] == 'new' and 'data_mean_range' in info:
                info_text += f"数据标准化信息:\n"
                info_text += f"  均值范围: [{info['data_mean_range'][0]:.2f}, {info['data_mean_range'][1]:.2f}]\n"
                info_text += f"  标准差范围: [{info['data_std_range'][0]:.2f}, {info['data_std_range'][1]:.2f}]\n\n"
            
            info_text += f"状态: ✅ 已加载并可用"
            
            QtWidgets.QMessageBox.information(self.parent, "AI校准信息", info_text)
            
        except Exception as e:
            print(f"❌ 显示AI校准信息失败: {e}")
            QtWidgets.QMessageBox.critical(self.parent, "错误", f"显示校准信息失败:\n{str(e)}")
            
    def load_new_calibrator(self):
        """加载新版本校准器"""
        try:
            print("🔧 开始加载新版本校准器...")
            
            # 查找新版本校准文件
            new_cal_file = None
            possible_paths = [
                'calibration_package.pt',
                '../calibration_package.pt',
                '../../calibration_package.pt'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    new_cal_file = path
                    break
            
            if not new_cal_file:
                QtWidgets.QMessageBox.warning(self.parent, "文件未找到",
                    "未找到新版本校准文件。\n请确保存在以下文件：\n• calibration_package.pt (新版本)")
                return False
            
            # 加载新版本校准器
            print(f"🔧 加载新版本校准器: {new_cal_file}")
            self.calibration_manager.new_calibrator = AICalibrationAdapter()
            if self.calibration_manager.new_calibrator.load_calibration(new_cal_file):
                print("✅ 新版本校准器加载成功")
            else:
                print("❌ 新版本校准器加载失败")
                self.calibration_manager.new_calibrator = None
                return False
            
            # 启用新版本校准模式
            self.calibration_manager.dual_calibration_mode = False
            
            # 显示加载成功信息
            new_info = self.calibration_manager.new_calibrator.get_info()
            success_text = "新版本校准器加载成功!\n\n"
            success_text += f"新版本校准器:\n"
            success_text += f"  格式: {new_info['calibration_format']}\n"
            success_text += f"  系数形状: {new_info['coeffs_shape']}\n"
            success_text += "\n现在可以使用新版本校准功能！"
            
            QtWidgets.QMessageBox.information(self.parent, "加载成功", success_text)
            print("✅ 新版本校准器加载完成")
            
            return True
            
        except Exception as e:
            print(f"❌ 加载新版本校准器失败: {e}")
            QtWidgets.QMessageBox.critical(self.parent, "加载失败", f"加载新版本校准器失败:\n{str(e)}")
            return False
            
    def start_new_calibration_monitoring(self):
        """启动新版本校准器实时监控"""
        try:
            if not hasattr(self.calibration_manager, 'new_calibrator') or self.calibration_manager.new_calibrator is None:
                QtWidgets.QMessageBox.warning(self.parent, "功能不可用", 
                    "请先加载新版本校准器！\n\n选择'加载新版本校准器'来启用此功能。")
                return False
            
            # 启动新版本校准器实时监控对话框
            from ..dialogs.dual_calibration_comparison_dialog import DualCalibrationComparisonDialog
            dialog = DualCalibrationComparisonDialog(self.parent)
            dialog.exec_()
            
            return True
            
        except Exception as e:
            print(f"❌ 启动新版本校准器监控失败: {e}")
            QtWidgets.QMessageBox.critical(self.parent, "错误", f"启动新版本校准器监控失败:\n{str(e)}")
            return False
    
    def _show_calibration_comparison(self, comparison_results):
        """显示校准对比结果"""
        try:
            # 构建对比信息文本
            info_text = "双校准器实时对比结果:\n\n"
            
            # 原始数据信息
            if 'raw' in comparison_results:
                raw = comparison_results['raw']
                info_text += f"原始数据:\n"
                info_text += f"  均值: {raw['mean']:.2f}\n"
                info_text += f"  标准差: {raw['std']:.2f}\n"
                info_text += f"  范围: [{raw['min']:.2f}, {raw['max']:.2f}]\n"
                info_text += f"  数据范围: {raw['range']:.2f}\n\n"
            
            # 旧版本校准器结果
            if 'old' in comparison_results:
                old = comparison_results['old']
                info_text += f"旧版本校准器:\n"
                info_text += f"  均值: {old['mean']:.2f}\n"
                info_text += f"  标准差: {old['std']:.2f}\n"
                info_text += f"  范围: [{old['min']:.2f}, {old['max']:.2f}]\n"
                info_text += f"  数据范围: {old['range']:.2f}\n\n"
            
            # 新版本校准器结果
            if 'new' in comparison_results:
                new = comparison_results['new']
                info_text += f"新版本校准器:\n"
                info_text += f"  均值: {new['mean']:.2f}\n"
                info_text += f"  标准差: {new['std']:.2f}\n"
                info_text += f"  范围: [{new['min']:.2f}, {new['max']:.2f}]\n"
                info_text += f"  数据范围: {new['range']:.2f}\n\n"
            
            # 去皮状态
            if hasattr(self.calibration_manager, 'taring_enabled') and self.calibration_manager.taring_enabled:
                info_text += "去皮状态: ✅ 已启用（逐点去皮）\n"
            else:
                info_text += "去皮状态: ❌ 未启用\n"
            
            QtWidgets.QMessageBox.information(self.parent, "双校准器对比结果", info_text)
            
        except Exception as e:
            print(f"❌ 显示校准对比失败: {e}")
            QtWidgets.QMessageBox.critical(self.parent, "错误", f"显示校准对比失败:\n{str(e)}")
    
    def get_current_frame_data(self):
        """获取当前帧的原始数据（公共接口）"""
        return self._get_current_frame_data()
    
    def _get_current_frame_data(self):
        """获取当前帧的原始数据（用于校准对比）"""
        try:
            # 添加调试信息
            print(f"🔍 数据源状态检查:")
            print(f"   data_handler.data长度: {len(self.parent.data_handler.data) if hasattr(self.parent.data_handler, 'data') else 'N/A'}")
            print(f"   data_handler.value长度: {len(self.parent.data_handler.value) if hasattr(self.parent.data_handler, 'value') else 'N/A'}")
            print(f"   data_handler.value_before_zero长度: {len(self.parent.data_handler.value_before_zero) if hasattr(self.parent.data_handler, 'value_before_zero') else 'N/A'}")
            
            # 优先从data_handler获取最新的实时原始数据
            if hasattr(self.parent.data_handler, 'data') and len(self.parent.data_handler.data) > 0:
                current_data = self.parent.data_handler.data[-1]
                print(f"✅ 使用data_handler.data的实时原始数据，形状: {current_data.shape}, 范围: [{current_data.min():.4f}, {current_data.max():.4f}]")
                return current_data
            elif hasattr(self.parent.data_handler, 'value_before_zero') and len(self.parent.data_handler.value_before_zero) > 0:
                # 如果data为空，尝试从value_before_zero获取原始数据
                current_data = self.parent.data_handler.value_before_zero[-1]
                print(f"✅ 使用value_before_zero的原始数据，形状: {current_data.shape}, 范围: [{current_data.min():.4f}, {current_data.max():.4f}]")
                return current_data
            elif hasattr(self.parent, '_raw_data_for_comparison') and len(self.parent._raw_data_for_comparison) > 0:
                # 最后才使用保存的原始数据副本
                current_data = self.parent._raw_data_for_comparison[-1]
                print(f"⚠️ 使用保存的原始数据副本，形状: {current_data.shape}, 范围: [{current_data.min():.4f}, {current_data.max():.4f}]")
                return current_data
            elif hasattr(self.parent.data_handler, 'value') and len(self.parent.data_handler.value) > 0:
                # 最后从value获取（可能已经是校准后的数据）
                current_data = self.parent.data_handler.value[-1]
                print(f"⚠️ 使用可能已校准的数据作为原始数据，形状: {current_data.shape}, 范围: [{current_data.min():.4f}, {current_data.max():.4f}]")
                return current_data
            else:
                # 如果没有数据，返回模拟数据
                print("⚠️ 没有实时数据，使用模拟数据")
                # 生成一些变化的模拟数据，而不是完全随机的
                if not hasattr(self.parent, '_simulation_counter'):
                    self.parent._simulation_counter = 0
                self.parent._simulation_counter += 1
                
                # 创建基于时间的模拟数据，模拟传感器压力变化
                base_data = np.zeros((64, 64))
                center_x, center_y = 32, 32
                for i in range(64):
                    for j in range(64):
                        distance = np.sqrt((i - center_x)**2 + (j - center_y)**2)
                        pressure = max(0, 1000 - distance * 10 + np.sin(self.parent._simulation_counter * 0.1) * 100)
                        base_data[i, j] = pressure
                
                print(f"✅ 生成模拟数据，形状: {base_data.shape}, 范围: [{base_data.min():.4f}, {base_data.max():.4f}]")
                return base_data
                
        except Exception as e:
            print(f"❌ 获取当前帧数据失败: {e}")
            # 返回默认数据
            return np.zeros((64, 64))
    
    def show_detailed_calibration_comparison(self):
        """显示详细校准对比（包含热力图）"""
        try:
            # 检查是否有可用的校准器（单校准器或双校准器模式）
            has_calibrator = False
            if self.calibration_manager.calibration_coeffs is not None:
                has_calibrator = True
            elif hasattr(self.calibration_manager, 'dual_calibration_mode') and self.calibration_manager.dual_calibration_mode:
                if self.calibration_manager.old_calibrator is not None or self.calibration_manager.new_calibrator is not None:
                    has_calibrator = True
            
            if not has_calibrator:
                QtWidgets.QMessageBox.warning(self.parent, "未加载", 
                    "请先加载AI校准模型或双校准器\n\n"
                    "单校准器模式：选择'加载AI校准模型'\n"
                    "双校准器模式：选择'加载双校准器'")
                return

            # 创建详细对比对话框
            from ..dialogs.dual_calibration_comparison_dialog import DualCalibrationComparisonDialog
            dialog = DualCalibrationComparisonDialog(self.parent)
            dialog.exec_()
            
        except Exception as e:
            print(f"❌ 显示详细校准对比失败: {e}")
            QtWidgets.QMessageBox.critical(self.parent, "错误", f"显示详细校准对比失败:\n{str(e)}")
    
    def _show_new_calibrator_info(self):
         """显示新版本校准器信息"""
         try:
             if not hasattr(self.calibration_manager, 'new_calibrator') or self.calibration_manager.new_calibrator is None:
                 QtWidgets.QMessageBox.information(self.parent, "新版本校准器信息", 
                     "当前未加载新版本校准器。\n\n请先选择'加载新版本校准器'来加载校准文件。")
                 return
             
             # 获取新版本校准器信息
             new_info = self.calibration_manager.new_calibrator.get_info()
             
             # 构建信息文本
             info_text = f"新版本校准器信息:\n\n"
             info_text += f"校准格式: {new_info['calibration_format']}\n"
             info_text += f"系数形状: {new_info['coeffs_shape']}\n"
             
             if 'coeffs_range' in new_info and new_info['coeffs_range']:
                 coeffs = new_info['coeffs_range']
                 info_text += f"\n校准系数范围:\n"
                 info_text += f"  二次项(a): [{coeffs['a'][0]:.4f}, {coeffs['a'][1]:.4f}]\n"
                 info_text += f"  一次项(b): [{coeffs['b'][0]:.4f}, {coeffs['b'][1]:.4f}]\n"
                 info_text += f"  常数项(c): [{coeffs['c'][0]:.4f}, {coeffs['c'][1]:.4f}]\n"
             
             if new_info['calibration_format'] == 'new' and 'data_mean_range' in new_info:
                 info_text += f"\n数据标准化信息:\n"
                 info_text += f"  均值范围: [{new_info['data_mean_range'][0]:.2f}, {new_info['data_mean_range'][1]:.2f}]\n"
                 info_text += f"  标准差范围: [{new_info['data_std_range'][0]:.2f}, {new_info['data_std_range'][1]:.2f}]\n"
             
             info_text += f"\n状态: ✅ 已加载并可用"
             
             QtWidgets.QMessageBox.information(self.parent, "新版本校准器信息", info_text)
             
         except Exception as e:
             print(f"❌ 显示新版本校准器信息失败: {e}")
             QtWidgets.QMessageBox.critical(self.parent, "错误", f"显示新版本校准器信息失败:\n{str(e)}")
 
    # 🆕 兼容性方法：为了保持向后兼容
    def load_dual_calibrators(self):
        """兼容性方法：加载双校准器（现在只加载新版本校准器）"""
        print("⚠️ 兼容性调用：load_dual_calibrators -> load_new_calibrator")
        return self.load_new_calibrator()
    
    def start_dual_calibration_comparison(self):
        """兼容性方法：启动双校准器比较（现在启动新版本校准器监控）"""
        print("⚠️ 兼容性调用：start_dual_calibration_comparison -> start_new_calibration_monitoring")
        return self.start_new_calibration_monitoring()

