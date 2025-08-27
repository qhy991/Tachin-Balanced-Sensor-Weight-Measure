#!/usr/bin/env python3
"""
启动AI校准界面
运行带有AI校准功能的传感器数据采集界面
"""

import sys
import os
from pathlib import Path

def main():
    """
    主函数：启动AI校准界面
    """

    print("🎯 启动AI校准界面")
    print("=" * 50)

    # 检查必要的文件是否存在
    required_files = [
        'calibration_coeffs.pt',
        'interfaces/ordinary/user_interface_with_ai_calibration.py'
    ]

    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)

    if missing_files:
        print("❌ 缺少必要文件：")
        for file in missing_files:
            print(f"  • {file}")

        print("\\n📝 请先确保：")
        print("1. 运行校准训练脚本生成 calibration_coeffs.pt")
        print("2. 确保文件路径正确")

        # 提供解决方案
        if 'calibration_coeffs.pt' in missing_files:
            print("\\n🔧 解决方案：")
            print("运行以下命令训练校准模型：")
            print("python calibrate-0821.py")

        return

    # 检查PyTorch是否安装
    try:
        import torch
        print(f"✅ PyTorch版本: {torch.__version__}")

        # 检查CUDA可用性
        if torch.cuda.is_available():
            print(f"✅ CUDA可用: {torch.cuda.get_device_name(0)}")
        else:
            print("⚠️ CUDA不可用，将使用CPU")

    except ImportError:
        print("❌ 未安装PyTorch")
        print("\\n🔧 安装PyTorch：")
        print("pip install torch")
        return

    # 检查matplotlib是否安装
    try:
        import matplotlib
        print(f"✅ Matplotlib版本: {matplotlib.__version__}")
    except ImportError:
        print("❌ 未安装Matplotlib")
        print("\\n🔧 安装Matplotlib：")
        print("pip install matplotlib")
        return

    # 检查PyQt5是否安装
    try:
        from PyQt5 import QtWidgets
        print("✅ PyQt5已安装")
    except ImportError:
        print("❌ 未安装PyQt5")
        print("\\n🔧 安装PyQt5：")
        print("pip install PyQt5")
        return

    print("\\n🚀 启动AI校准界面...")

    try:
        # 导入并启动AI校准界面
        sys.path.append(str(Path(__file__).parent))
        from interfaces.ordinary.user_interface_with_ai_calibration import start

        # 启动界面
        start('standard')

    except Exception as e:
        print(f"❌ 启动失败: {e}")

        # 提供详细的错误诊断
        print("\\n🔍 错误诊断：")

        # 检查Python路径
        print(f"Python路径: {sys.executable}")
        print(f"当前工作目录: {os.getcwd()}")

        # 检查导入路径
        print(f"Python路径包含: {sys.path}")

        # 检查文件权限
        calib_file = Path('calibration_coeffs.pt')
        if calib_file.exists():
            print(f"校准文件权限: {oct(calib_file.stat().st_mode)[-3:]}")

        print("\\n💡 可能的解决方案：")
        print("1. 确保所有依赖都已安装")
        print("2. 检查文件权限")
        print("3. 尝试以管理员身份运行")
        print("4. 检查Python环境是否正确")

if __name__ == '__main__':
    main()
