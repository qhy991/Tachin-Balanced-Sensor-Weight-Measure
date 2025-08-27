#!/usr/bin/env python3
"""
去皮功能管理类

负责去皮和重置去皮功能
"""

from PyQt5 import QtWidgets
import traceback


class TaringManager:
    """去皮功能管理器"""
    
    def __init__(self, parent):
        self.parent = parent
    
    def perform_taring(self):
        """执行去皮操作"""
        try:
            # 检查主窗口是否有真正的去皮功能
            # 避免递归调用，检查是否有taring_handler或其他去皮实现
            if hasattr(self.parent, 'taring_handler'):
                # 使用taring_handler
                success = self.parent.taring_handler.perform_taring()
            elif hasattr(self.parent, 'calibration_handler') and hasattr(self.parent.calibration_handler, 'taring_handler'):
                # 通过calibration_handler访问taring_handler
                success = self.parent.calibration_handler.taring_handler.perform_taring()
            elif hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'taring_handler'):
                # 通过父窗口访问taring_handler
                success = self.parent.parent.taring_handler.perform_taring()
            elif hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'perform_taring'):
                # 通过父窗口访问去皮功能（但要避免递归）
                if hasattr(self.parent.parent, '_taring_in_progress'):
                    # 防止递归调用
                    QtWidgets.QMessageBox.warning(None, "错误", "去皮操作正在进行中，请勿重复操作")
                    return False
                
                # 标记去皮操作开始
                self.parent.parent._taring_in_progress = True
                try:
                    success = self.parent.parent.perform_taring()
                finally:
                    # 标记去皮操作结束
                    self.parent.parent._taring_in_progress = False
            else:
                QtWidgets.QMessageBox.warning(None, "功能不可用", "主窗口不支持去皮功能")
                return False
            
            if success:
                QtWidgets.QMessageBox.information(None, "成功", "去皮操作执行成功！\n当前传感器读数已设为零点基准。")
                print("✅ 双校准比较界面：去皮操作执行成功")
                return True
            else:
                QtWidgets.QMessageBox.warning(None, "失败", "去皮操作执行失败")
                print("❌ 双校准比较界面：去皮操作执行失败")
                return False
                
        except Exception as e:
            print(f"❌ 双校准比较界面去皮操作失败: {e}")
            QtWidgets.QMessageBox.critical(None, "错误", f"去皮操作失败:\n{str(e)}")
            return False
    
    def reset_taring(self):
        """重置去皮操作"""
        try:
            # 检查主窗口是否有真正的重置去皮功能
            # 避免递归调用，检查是否有taring_handler或其他去皮实现
            if hasattr(self.parent, 'taring_handler'):
                # 使用taring_handler
                success = self.parent.taring_handler.reset_taring()
            elif hasattr(self.parent, 'calibration_handler') and hasattr(self.parent.calibration_handler, 'taring_handler'):
                # 通过calibration_handler访问taring_handler
                success = self.parent.calibration_handler.taring_handler.reset_taring()
            elif hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'taring_handler'):
                # 通过父窗口访问taring_handler
                success = self.parent.parent.taring_handler.reset_taring()
            elif hasattr(self.parent, 'parent') and hasattr(self.parent.parent, 'reset_taring'):
                # 通过父窗口访问重置去皮功能（但要避免递归）
                if hasattr(self.parent.parent, '_reset_taring_in_progress'):
                    # 防止递归调用
                    QtWidgets.QMessageBox.warning(None, "错误", "重置去皮操作正在进行中，请勿重复操作")
                    return False
                
                # 标记重置去皮操作开始
                self.parent.parent._reset_taring_in_progress = True
                try:
                    success = self.parent.parent.reset_taring()
                finally:
                    # 标记重置去皮操作结束
                    self.parent.parent._reset_taring_in_progress = False
            else:
                QtWidgets.QMessageBox.warning(None, "功能不可用", "主窗口不支持重置去皮功能")
                return False
            
            if success:
                QtWidgets.QMessageBox.information(None, "成功", "去皮重置成功！\n已恢复到原始传感器读数。")
                print("✅ 双校准比较界面：去皮重置成功")
                return True
            else:
                QtWidgets.QMessageBox.warning(None, "失败", "去皮重置失败")
                print("❌ 双校准比较界面：去皮重置失败")
                return False
                
        except Exception as e:
            print(f"❌ 双校准比较界面重置去皮失败: {e}")
            QtWidgets.QMessageBox.critical(None, "错误", f"重置去皮失败:\n{str(e)}")
            return False
