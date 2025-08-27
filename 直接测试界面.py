#!/usr/bin/env python3
"""
直接测试界面，看看菜单栏是否真的不可见
"""

import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
parent_root = os.path.dirname(project_root)
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)

def test_interface_directly():
    """直接测试界面"""
    print("🔍 直接测试界面...")
    
    try:
        from PyQt5 import QtWidgets
        from sensor_driver.interfaces.ordinary.user_interface import Window
        
        # 创建应用
        app = QtWidgets.QApplication(sys.argv)
        
        # 创建窗口
        print("📱 创建窗口...")
        window = Window(mode='standard')
        
        # 显示窗口
        print("🖥️ 显示窗口...")
        window.show()
        
        # 检查菜单栏状态
        print("\n🔍 检查菜单栏状态...")
        if hasattr(window, 'menubar') and window.menubar is not None:
            print(f"✅ menubar存在")
            print(f"👁️ 可见性: {window.menubar.isVisible()}")
            print(f"🔒 隐藏状态: {window.menubar.isHidden()}")
            print(f"📏 几何信息: {window.menubar.geometry()}")
            print(f"📏 窗口几何信息: {window.geometry()}")
            
            # 尝试强制显示
            print("\n🔧 尝试强制显示菜单栏...")
            window.menubar.setVisible(True)
            window.menubar.setHidden(False)
            window.menubar.raise_()
            
            # 再次检查
            print(f"👁️ 强制显示后可见性: {window.menubar.isVisible()}")
            print(f"🔒 强制显示后隐藏状态: {window.menubar.isHidden()}")
            
            # 检查菜单
            menus = window.menubar.findChildren(QtWidgets.QMenu)
            print(f"📋 菜单数量: {len(menus)}")
            for i, menu in enumerate(menus):
                print(f"   {i+1}. '{menu.title()}' - 可见: {menu.isVisible()}")
        
        print("\n⏰ 界面将保持打开状态，请检查菜单栏是否可见...")
        print("按 Ctrl+C 关闭界面")
        
        # 保持界面打开
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_interface_directly()

