#!/usr/bin/env python3
"""
测试菜单栏状态和AI校准菜单创建
"""

import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
parent_root = os.path.dirname(project_root)
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)

def test_menubar_status():
    """测试菜单栏状态"""
    print("🔍 测试菜单栏状态...")
    
    try:
        from PyQt5 import QtWidgets
        from sensor_driver.interfaces.ordinary.user_interface import Window
        
        # 创建应用
        app = QtWidgets.QApplication(sys.argv)
        
        # 创建窗口
        print("📱 创建窗口...")
        window = Window(mode='standard')
        
        # 检查菜单栏
        print("\n🔍 检查菜单栏...")
        if hasattr(window, 'menubar'):
            print(f"✅ menubar属性存在: {window.menubar}")
            
            if window.menubar is not None:
                print(f"✅ menubar不为None")
                
                # 检查菜单栏类型
                print(f"📋 menubar类型: {type(window.menubar)}")
                
                # 获取所有菜单
                menus = window.menubar.findChildren(QtWidgets.QMenu)
                print(f"📋 找到菜单数量: {len(menus)}")
                
                if menus:
                    print(f"📋 菜单标题:")
                    for i, menu in enumerate(menus):
                        print(f"   {i+1}. '{menu.title()}' (类型: {type(menu)})")
                        
                        # 检查菜单项
                        actions = menu.actions()
                        if actions:
                            print(f"      菜单项:")
                            for action in actions:
                                print(f"        • '{action.text()}'")
                        else:
                            print(f"      无菜单项")
                else:
                    print(f"❌ 未找到任何菜单")
                    
                # 检查菜单栏是否可见
                print(f"👁️ 菜单栏可见性: {window.menubar.isVisible()}")
                print(f"👁️ 菜单栏启用状态: {window.menubar.isEnabled()}")
                
            else:
                print(f"❌ menubar为None")
        else:
            print(f"❌ menubar属性不存在")
            
        # 检查是否有setup_calibration_menu方法
        print(f"\n🔍 检查setup_calibration_menu方法...")
        if hasattr(window, 'setup_calibration_menu'):
            print(f"✅ setup_calibration_menu方法存在")
            
            # 尝试手动调用
            print(f"🔧 手动调用setup_calibration_menu...")
            try:
                window.setup_calibration_menu()
                print(f"✅ 手动调用成功")
                
                # 再次检查菜单
                menus_after = window.menubar.findChildren(QtWidgets.QMenu)
                print(f"📋 调用后菜单数量: {len(menus_after)}")
                
                if menus_after:
                    print(f"📋 调用后菜单标题:")
                    for i, menu in enumerate(menus_after):
                        print(f"   {i+1}. '{menu.title()}'")
                        
                        # 检查菜单项
                        actions = menu.actions()
                        if actions:
                            print(f"      菜单项:")
                            for action in actions:
                                print(f"        • '{action.text()}'")
                        else:
                            print(f"      无菜单项")
                            
            except Exception as e:
                print(f"❌ 手动调用失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"❌ setup_calibration_menu方法不存在")
            
        # 显示窗口
        print(f"\n🖥️ 显示窗口...")
        window.show()
        
        # 等待一段时间
        print(f"⏰ 等待5秒...")
        import time
        time.sleep(5)
        
        # 关闭
        window.close()
        app.quit()
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_menubar_status()

