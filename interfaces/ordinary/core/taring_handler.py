"""
去皮处理模块

负责处理去皮功能，包括执行去皮和重置去皮
"""

import numpy as np
from PyQt5 import QtWidgets


class TaringHandler:
    """去皮处理器"""
    
    def __init__(self, parent_window, calibration_manager):
        self.parent = parent_window
        self.calibration_manager = calibration_manager
    
    def perform_taring(self):
        """执行去皮操作 - 在无按压状态下校准零点（逐点去皮）"""
        try:
            # 🔧 修复：更新校准器检查逻辑，支持新版本校准器
            has_calibrator = False
            calibrator_info = ""
            
            # 检查新版本校准器
            if hasattr(self.calibration_manager, 'new_calibrator') and self.calibration_manager.new_calibrator is not None:
                has_calibrator = True
                calibrator_info = "新版本校准器"
                print("🔧 检测到新版本校准器")
            
            # 检查旧版本校准器（向后兼容）
            elif self.calibration_manager.calibration_coeffs is not None:
                has_calibrator = True
                calibrator_info = "旧版本校准器"
                print("🔧 检测到旧版本校准器")
            
            # 检查双校准器模式（向后兼容）
            elif hasattr(self.calibration_manager, 'dual_calibration_mode') and self.calibration_manager.dual_calibration_mode:
                if self.calibration_manager.old_calibrator is not None or self.calibration_manager.new_calibrator is not None:
                    has_calibrator = True
                    calibrator_info = "双校准器模式"
                    print("🔧 检测到双校准器模式")
            
            if not has_calibrator:
                QtWidgets.QMessageBox.warning(self.parent, "去皮失败", 
                    "请先加载AI校准模型或双校准器\n\n"
                    "单校准器模式：选择'加载AI校准模型'\n"
                    "双校准器模式：选择'加载双校准器'")
                return False
            
            print(f"✅ 校准器检查通过，使用: {calibrator_info}")
            
            # 获取当前帧数据作为零点基准
            current_data = self._get_current_frame_data()
            if current_data is None:
                QtWidgets.QMessageBox.warning(self.parent, "去皮失败", "无法获取当前传感器数据")
                return False
            
            # 🆕 修改：直接保存原始数据的零点偏移，不进行校准
            # 这样零点校正就在原始数据层面进行，更符合物理意义
            self.calibration_manager.zero_offset_matrix = current_data.copy()
            self.calibration_manager.taring_enabled = True
            
            # 计算统计信息用于显示
            baseline_mean = float(current_data.mean())
            baseline_std = float(current_data.std())
            baseline_min = float(current_data.min())
            baseline_max = float(current_data.max())
            
            print(f"✅ 原始数据零点校正基准设置完成！")
            print(f"   原始数据均值: {baseline_mean:.2f}")
            print(f"   原始数据范围: [{baseline_min:.2f}, {baseline_max:.2f}]")
            print(f"   现在所有原始数据将减去此基准矩阵")
            print(f"   实现真正的\"无压力时处处为零\"效果")
            
            # 🆕 修复：去除冗余的成功弹窗，只保留控制台输出
            # QtWidgets.QMessageBox.information(self.parent, "零点校正成功", 
            #     f"原始数据零点校正基准设置完成！\n\n"
            #     f"基准矩阵统计:\n"
            #     f"  均值: {baseline_mean:.2f}\n"
            #     f"  标准差: {baseline_std:.2f}\n"
            #     f"  最小值: {baseline_min:.2f}\n"
            #     f"  最大值: {baseline_max:.2f}\n\n"
            #     f"现在所有原始数据将减去此基准矩阵，\n"
            #     f"然后在零点校正后的原始数据上进行AI校准。")
            
            return True
            
        except Exception as e:
            print(f"❌ 零点校正操作失败: {e}")
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(self.parent, "零点校正失败", f"零点校正操作失败:\n{str(e)}")
            return False
    
    def reset_taring(self):
        """重置去皮功能"""
        self.calibration_manager.zero_offset = None  # 保持向后兼容
        if hasattr(self.calibration_manager, 'zero_offset_matrix'):
            self.calibration_manager.zero_offset_matrix = None
        self.calibration_manager.taring_enabled = False
        print("🔧 逐点去皮功能已重置")
        # 🆕 修复：去除冗余的重置弹窗，只保留控制台输出
        # QtWidgets.QMessageBox.information(self.parent, "去皮重置", "逐点去皮功能已重置，校准结果将不再减去基准矩阵。")
        return True
    
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
