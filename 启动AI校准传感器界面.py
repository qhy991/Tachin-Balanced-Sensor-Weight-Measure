#!/usr/bin/env python3
"""
启动带有AI校准功能的传感器界面
"""

import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
parent_root = os.path.dirname(project_root)  # 上一级目录

# 添加父目录到sys.path，这样就可以找到sensor_driver包
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)

def check_dependencies():
    """检查依赖项"""
    print("🔍 检查依赖项...")

    missing_deps = []

    try:
        import torch
        print(f"   ✅ PyTorch: {torch.__version__}")
    except ImportError:
        missing_deps.append("torch")

    try:
        from PyQt5 import QtWidgets
        print(f"   ✅ PyQt5: 可用")
    except ImportError:
        missing_deps.append("PyQt5")

    try:
        import numpy
        print(f"   ✅ NumPy: {numpy.__version__}")
    except ImportError:
        missing_deps.append("numpy")

    try:
        import matplotlib
        print(f"   ✅ Matplotlib: {matplotlib.__version__}")
    except ImportError:
        missing_deps.append("matplotlib")

    if missing_deps:
        print(f"   ❌ 缺少依赖: {', '.join(missing_deps)}")
        print("   请安装缺少的包:")
        for dep in missing_deps:
            if dep == "PyQt5":
                print(f"     pip install PyQt5")
            else:
                print(f"     pip install {dep}")
        return False

    return True

def check_calibration_model():
    """检查AI校准模型"""
    print("\n🔍 检查AI校准模型...")

    calibration_path = os.path.join(parent_root, "sensor_driver", "calibration_coeffs.pt")

    if os.path.exists(calibration_path):
        try:
            import torch
            model = torch.load(calibration_path)
            print(f"   ✅ 校准模型存在: {calibration_path}")
            print(f"   ✅ 模型形状: {model.shape}")
            print(f"   ✅ 传感器数量: {model.shape[0]} (64×64={64*64})")
            return True
        except Exception as e:
            print(f"   ❌ 模型文件损坏: {e}")
            return False
    else:
        print(f"   ⚠️  校准模型不存在: {calibration_path}")
        print("   AI校准功能将不可用，但界面仍可正常使用")
        print("   如需启用AI校准，请先运行校准训练脚本")
        return True  # 不阻止启动

def main():
    """主函数"""
    print("🚀 启动AI校准传感器界面")
    print("=" * 50)

    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请安装缺少的包")
        sys.exit(1)

    # 检查校准模型
    model_available = check_calibration_model()

    print(f"\n🎯 启动配置:")
    print(f"   项目目录: {project_root}")
    print(f"   AI校准模型: {'可用' if model_available else '不可用'}")
    print(f"   界面模块: sensor_driver.interfaces.ordinary.user_interface")

    # 启动界面
    print(f"\n🚀 启动传感器界面...")
    print(f"   功能包括:")
    print(f"   • 实时传感器数据采集")
    print(f"   • AI校准功能 (如模型可用)")
    print(f"   • 数据可视化")
    print(f"   • 校准前后对比")
    print(f"   • 性能监控")

    try:
        from sensor_driver.interfaces.ordinary.user_interface import start, Window
        from PyQt5 import QtWidgets

        # 创建一个测试窗口来检查菜单
        print(f"\n🔍 检查菜单显示...")
        app = QtWidgets.QApplication(sys.argv)
        window = Window(mode='standard')

        # 检查菜单栏
        if hasattr(window, 'menubar') and window.menubar is not None:
            menus = window.menubar.findChildren(QtWidgets.QMenu)
            menu_titles = [menu.title() for menu in menus]
            print(f"📋 菜单栏中的菜单: {menu_titles}")

            # 检查AI校准菜单
            ai_menus = [title for title in menu_titles if 'AI' in title or '校准' in title]
            if ai_menus:
                print(f"✅ 找到AI校准菜单: {ai_menus}")
            else:
                print(f"❌ 未找到AI校准菜单")
        else:
            print(f"❌ 菜单栏不存在")

        window.close()
        app.quit()

        print(f"\n🚀 正式启动界面...")
        start(mode='standard')

    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("请检查以下可能的问题:")
        print("1. 确保所有依赖都已正确安装")
        print("2. 检查传感器驱动是否可用")
        print("3. 确认配置文件正确")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
