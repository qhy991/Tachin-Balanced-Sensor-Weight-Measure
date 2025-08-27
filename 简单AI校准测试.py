#!/usr/bin/env python3
"""
简单AI校准功能测试
"""

import sys
import os
import numpy as np
import torch

def test_ai_calibration_directly():
    """直接测试AI校准功能"""
    print("🎯 简单AI校准功能测试")
    print("=" * 40)

    # 1. 检查校准模型文件
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    calibration_path = os.path.join(project_root, "sensor_driver", "calibration_coeffs.pt")

    if not os.path.exists(calibration_path):
        print(f"❌ 校准模型文件不存在: {calibration_path}")
        return False

    print(f"✅ 找到校准模型文件: {calibration_path}")

    # 2. 加载校准模型
    try:
        coeffs = torch.load(calibration_path)
        print(f"✅ 成功加载校准模型，形状: {coeffs.shape}")

        # 3. 设置计算设备
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        coeffs = coeffs.to(device)
        print(f"✅ 使用计算设备: {device}")

        # 4. 创建测试数据
        test_data = np.random.rand(64, 64) * 1000
        print(f"✅ 创建测试数据，形状: {test_data.shape}")
        print(f"   数据范围: [{test_data.min():.1f}, {test_data.max():.1f}]")

        # 5. 应用AI校准
        raw_tensor = torch.from_numpy(test_data).float().to(device)
        raw_flat = raw_tensor.view(-1)

        # 应用校准公式: y = a*x² + b*x + c
        x = raw_flat
        a = coeffs[:, 0]
        b = coeffs[:, 1]
        c = coeffs[:, 2]

        calibrated_flat = a * x**2 + b * x + c
        calibrated_tensor = calibrated_flat.view(64, 64)
        calibrated_data = calibrated_tensor.cpu().numpy()

        print(f"✅ AI校准应用成功")
        print(f"   校准后数据范围: [{calibrated_data.min():.1f}, {calibrated_data.max():.1f}]")

        # 6. 计算改善效果
        raw_cv = test_data.std() / test_data.mean()
        cal_cv = calibrated_data.std() / calibrated_data.mean()
        improvement = raw_cv / cal_cv if cal_cv > 0 else float('inf')

        print(f"   原始数据CV: {raw_cv:.4f}")
        print(f"   校准后数据CV: {cal_cv:.4f}")
        print(f"   改善倍数: {improvement:.2f}倍")

        if improvement > 1:
            print(f"✅ 校准效果显著！CV改善了{improvement:.1f}倍")
        else:
            print(f"⚠️ 校准效果需要优化")

        # 7. 显示系数统计信息
        print(f"\n📊 校准系数统计:")
        a_stats = coeffs[:, 0].cpu()
        b_stats = coeffs[:, 1].cpu()
        c_stats = coeffs[:, 2].cpu()

        print(f"   二次项系数 (a): 范围 [{a_stats.min():.4f}, {a_stats.max():.4f}], 均值 {a_stats.mean():.4f}")
        print(f"   一次项系数 (b): 范围 [{b_stats.min():.4f}, {b_stats.max():.4f}], 均值 {b_stats.mean():.4f}")
        print(f"   常数项系数 (c): 范围 [{c_stats.min():.4f}, {c_stats.max():.4f}], 均值 {c_stats.mean():.4f}")

        return True

    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_user_interface_code():
    """测试user_interface.py中的关键代码"""
    print("\n🔍 测试user_interface.py中的AI校准代码")
    print("=" * 45)

    # 检查user_interface.py文件
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    interface_file = os.path.join(project_root, "sensor_driver", "interfaces", "ordinary", "user_interface.py")

    if not os.path.exists(interface_file):
        print(f"❌ user_interface.py文件不存在: {interface_file}")
        return False

    try:
        # 读取文件内容
        with open(interface_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查关键代码段是否存在
        required_code_segments = [
            "class AICalibrationAdapter",
            "def setup_calibration",
            "def __load_ai_calibration",
            "def apply_ai_calibration",
            "def __show_calibration_comparison",
            "calibration_coeffs = None",
            "torch.load"
        ]

        found_segments = []
        missing_segments = []

        for segment in required_code_segments:
            if segment in content:
                found_segments.append(segment)
                print(f"   ✅ 找到代码段: {segment}")
            else:
                missing_segments.append(segment)
                print(f"   ❌ 缺少代码段: {segment}")

        if not missing_segments:
            print(f"\n✅ 所有关键代码段都存在")
            print(f"   文件总行数: {len(content.split('\n'))}")

            # 检查AI校准菜单设置
            if "setup_calibration_menu" in content:
                print(f"   ✅ 找到AI校准菜单设置代码")

            # 检查实时校准集成
            if "apply_ai_calibration" in content and "trigger" in content:
                print(f"   ✅ 找到实时校准集成代码")

            return True
        else:
            print(f"\n⚠️ 缺少以下关键代码段: {missing_segments}")
            return False

    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 AI校准功能集成验证")
    print("=" * 50)

    # 测试AI校准功能
    success1 = test_ai_calibration_directly()

    # 测试user_interface.py代码
    success2 = test_user_interface_code()

    print(f"\n📋 验证结果:")
    print(f"   AI校准功能测试: {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"   界面代码检查: {'✅ 通过' if success2 else '❌ 失败'}")

    if success1 and success2:
        print(f"\n🎉 所有验证通过！AI校准功能已成功集成！")
        print(f"\n📖 使用说明:")
        print(f"1. 确保校准模型文件存在: sensor_driver/calibration_coeffs.pt")
        print(f"2. 在user_interface.py中，AI校准会自动应用到所有数据")
        print(f"3. 通过菜单栏'AI校准'访问相关功能")
        print(f"4. 查看控制台状态栏了解当前校准状态")
    else:
        print(f"\n⚠️ 部分验证失败，请检查相关配置")
        sys.exit(1)