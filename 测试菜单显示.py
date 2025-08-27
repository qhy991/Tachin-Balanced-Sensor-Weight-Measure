#!/usr/bin/env python3
"""
测试AI校准菜单是否正确显示
"""

import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_root = os.path.dirname(project_root)
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)

def test_menu_display():
    """测试菜单显示"""
    print("🔍 测试AI校准菜单显示")

    try:
        from sensor_driver.interfaces.ordinary.user_interface import Window
        from PyQt5 import QtWidgets

        # 创建应用和窗口
        app = QtWidgets.QApplication(sys.argv)
        window = Window(mode='standard')

        # 检查菜单栏
        if hasattr(window, 'menubar') and window.menubar is not None:
            print("✅ 菜单栏存在")

            # 获取所有菜单
            menus = window.menubar.findChildren(QtWidgets.QMenu)
            menu_titles = [menu.title() for menu in menus]

            print(f"📋 菜单栏中的菜单:")
            for i, title in enumerate(menu_titles):
                print(f"   {i+1}. {title}")

            # 检查是否有AI校准菜单
            ai_calibration_menus = [title for title in menu_titles if 'AI' in title or '校准' in title]
            if ai_calibration_menus:
                print(f"\n✅ 找到AI校准菜单: {ai_calibration_menus}")
            else:
                print(f"\n❌ 未找到AI校准菜单")

            # 检查菜单项
            for menu in menus:
                if 'AI' in menu.title() or '校准' in menu.title():
                    actions = menu.actions()
                    action_titles = [action.text() for action in actions]
                    print(f"   📝 {menu.title()} 菜单项:")
                    for title in action_titles:
                        print(f"      • {title}")

        else:
            print("❌ 菜单栏不存在")

        # 运行应用一小段时间
        print("\n⏰ 界面将在3秒后自动关闭...")
        import time
        time.sleep(3)

        window.close()
        app.quit()

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_menu_display()

