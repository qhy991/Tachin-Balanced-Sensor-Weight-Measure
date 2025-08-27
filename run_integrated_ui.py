#!/usr/bin/env python3
"""
启动集成了真正传感器驱动的AI校准传感器系统UI

这个脚本启动新的集成版本，包含真正的传感器驱动和AI校准功能。
现在使用与run_original_way.py相同的启动方式，确保数据更新正常。
也可以选择启动改进的自定义UI版本。
"""

import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
parent_root = os.path.dirname(project_root)  # 上一级目录

# 添加父目录到sys.path，这样就可以找到sensor_driver包
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)

def check_current_directory():
    """检查当前运行目录"""
    current_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"📁 当前工作目录: {current_dir}")
    print(f"📁 脚本所在目录: {script_dir}")
    
    if current_dir != script_dir:
        print("⚠️  警告：当前工作目录与脚本目录不一致！")
        print("   这可能导致模块导入失败。")
        print("   建议切换到脚本所在目录运行：")
        print(f"   cd {script_dir}")
        print("   或者使用绝对路径运行：")
        print(f"   python {os.path.join(script_dir, 'run_integrated_ui.py')}")
        print()
        return False
    else:
        print("✅ 当前工作目录正确")
        return True

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

def start_original_reliable_ui():
    """启动原始可靠的UI"""
    try:
        from sensor_driver.interfaces.ordinary.user_interface import start
        start(mode='standard')
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        raise

def start_custom_improved_ui():
    """启动改进的自定义UI"""
    try:
        # 导入改进版的自定义UI
        from src.ui.improved_main_window import main as run_improved_ui
        run_improved_ui()
    except ImportError as e:
        print(f"⚠️ 改进版UI不可用: {e}")
        print("   回退到原始可靠版本...")
        start_original_reliable_ui()
    except Exception as e:
        print(f"\n❌ 启动改进版UI失败: {e}")
        print("   回退到原始可靠版本...")
        start_original_reliable_ui()

def choose_ui_mode():
    """选择UI模式"""
    print("\n🎯 请选择UI模式:")
    print("   1. 原始可靠模式 (推荐) - 使用验证过的原始界面")
    print("   2. 改进自定义模式 - 使用改进的自定义界面")
    print("   3. 自动选择 - 自动选择最佳模式")
    
    # 自动选择模式1，不等待用户输入
    print("\n⚡ 自动选择原始可靠模式（推荐）")
    return "original"

def main():
    """主函数"""
    print("🚀 启动集成了真正传感器驱动的AI校准传感器系统UI")
    print("=" * 60)

    # 检查当前目录
    if not check_current_directory():
        print("\n❌ 目录检查失败，请切换到正确的目录后重试")
        print("   或者使用以下命令运行：")
        print(f"   cd {os.path.dirname(os.path.abspath(__file__))}")
        print("   python run_integrated_ui.py")
        sys.exit(1)

    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请安装缺少的包")
        sys.exit(1)

    # 检查校准模型
    model_available = check_calibration_model()

    # 选择UI模式
    ui_mode = choose_ui_mode()

    print(f"\n🎯 启动配置:")
    print(f"   项目目录: {project_root}")
    print(f"   AI校准模型: {'可用' if model_available else '不可用'}")
    print(f"   UI模式: {ui_mode}")
    print(f"   UI模块: sensor_driver.interfaces.ordinary.user_interface (使用原始可靠方式)")

    # 启动界面
    print(f"\n🚀 启动集成版传感器界面...")
    print(f"   功能包括:")
    print(f"   • 真正的传感器驱动集成")
    print(f"   • 实时传感器数据采集")
    print(f"   • AI校准功能集成")
    print(f"   • 去皮校正功能")
    print(f"   • 现代化UI界面")
    print(f"   • 实时数据可视化")

    try:
        if ui_mode == "original":
            print(f"\n🚀 启动原始可靠模式...")
            print("   注意：使用与原始版本相同的启动方式，确保数据更新正常")
            start_original_reliable_ui()
            
        elif ui_mode == "custom":
            print(f"\n🚀 启动改进自定义模式...")
            print("   注意：使用改进的自定义界面，提供更多功能")
            start_custom_improved_ui()
            
        elif ui_mode == "auto":
            print(f"\n🚀 自动选择最佳模式...")
            # 优先尝试原始可靠模式
            try:
                print("   尝试原始可靠模式...")
                start_original_reliable_ui()
            except:
                print("   原始模式失败，尝试自定义模式...")
                start_custom_improved_ui()

        print("   功能包括：")
        print("   • USB传感器连接（支持端口号选择）")
        print("   • AI校准模型加载和应用")
        print("   • 双校准器支持")
        print("   • 去皮校正功能")
        print("   • 实时热力图显示")
        print("   • 数据统计和分析")

    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("请检查以下可能的问题:")
        print("1. 确保所有依赖都已正确安装")
        print("2. 检查传感器驱动是否可用")
        print("3. 确认配置文件正确")
        print("4. 确保在正确的目录下运行脚本")
        print("5. 检查sensor_driver.interfaces.ordinary.user_interface模块是否正确导入")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
