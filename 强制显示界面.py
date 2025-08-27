#!/usr/bin/env python3
"""
强制显示界面，确保界面能够正确显示
"""

import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
parent_root = os.path.dirname(project_root)
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)

def force_show_interface():
    """强制显示界面"""
    print("🔍 强制显示界面...")
    
    try:
        from PyQt5 import QtWidgets, QtCore
        from sensor_driver.interfaces.ordinary.user_interface import Window
        
        # 创建应用
        app = QtWidgets.QApplication(sys.argv)
        
        # 创建窗口
        print("📱 创建窗口...")
        window = Window(mode='standard')
        
        # 强制设置窗口属性
        window.setWindowState(QtCore.Qt.WindowActive)  # 激活窗口
        window.raise_()  # 提升到最前
        window.activateWindow()  # 激活窗口
        
        # 显示窗口
        print("🖥️ 显示窗口...")
        window.show()
        
        # 强制刷新
        window.repaint()
        app.processEvents()
        
        # 再次确保窗口可见
        window.setVisible(True)
        window.showNormal()  # 显示为正常大小
        
        print("✅ 界面已强制显示")
        print("📋 窗口状态:")
        print(f"   • 可见性: {window.isVisible()}")
        print(f"   • 窗口状态: {window.windowState()}")
        print(f"   • 几何信息: {window.geometry()}")
        print(f"   • 是否最小化: {window.isMinimized()}")
        print(f"   • 是否最大化: {window.isMaximized()}")
        
        # 检查菜单栏
        if hasattr(window, 'menubar') and window.menubar is not None:
            print(f"📋 菜单栏状态:")
            print(f"   • 可见性: {window.menubar.isVisible()}")
            print(f"   • 隐藏状态: {window.menubar.isHidden()}")
            
            # 强制显示菜单栏
            window.menubar.setVisible(True)
            window.menubar.setHidden(False)
            window.menubar.raise_()
            print("🔧 菜单栏已强制显示")
        
        # 检查AI校准按钮
        if hasattr(window, 'button_ai_calibration'):
            print(f"🔘 AI校准按钮状态:")
            print(f"   • 可见性: {window.button_ai_calibration.isVisible()}")
            print(f"   • 几何信息: {window.button_ai_calibration.geometry()}")
        
        print("\n🎯 界面现在应该可见了！")
        print("如果仍然看不到界面，请检查:")
        print("1. 界面是否被其他窗口遮挡")
        print("2. 任务栏是否有界面图标")
        print("3. 按Alt+Tab切换窗口")
        
        # 进入事件循环
        print("\n⏰ 进入事件循环...")
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"❌ 强制显示界面失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    force_show_interface()

