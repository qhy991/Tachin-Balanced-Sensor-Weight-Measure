#!/usr/bin/env python3
"""
使用真实传感器数据测试AI校准功能
"""

import numpy as np
import pandas as pd
import os
import sys
import torch
from pathlib import Path

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sensor_driver.data_processing.data_handler import AICalibrationAdapter

def load_real_sensor_data(data_dir="data-0815", pressure=25):
    """加载真实传感器数据"""
    csv_file = os.path.join(project_root, data_dir, f"{pressure}.csv")
    if not os.path.exists(csv_file):
        print(f"文件不存在: {csv_file}")
        return None

    try:
        df = pd.read_csv(csv_file)
        sensor_cols = [col for col in df.columns if col.startswith('data_row_')]

        if not sensor_cols:
            print(f"未找到传感器数据列: {csv_file}")
            return None

        # 创建64x64数组
        raw_data = np.zeros((64, 64))
        for col in sensor_cols:
            parts = col.split('_')
            if len(parts) >= 4:
                try:
                    row = int(parts[2])
                    col_idx = int(parts[3])
                    if 0 <= row < 64 and 0 <= col_idx < 64:
                        raw_data[row, col_idx] = df[col].mean()
                except (ValueError, IndexError):
                    continue

        print(f"✅ 成功加载数据: {csv_file}")
        print(f"   数据形状: {raw_data.shape}")
        print(f"   数据范围: [{raw_data.min():.2f}, {raw_data.max():.2f}]")
        print(f"   非零值比例: {(raw_data != 0).sum() / (64*64) * 100:.1f}%")

        return raw_data

    except Exception as e:
        print(f"加载数据失败: {e}")
        return None

def test_real_data_calibration():
    """使用真实数据测试校准"""
    print("🎯 真实传感器数据AI校准测试")
    print("=" * 50)

    # 1. 加载AI校准模型
    adapter = AICalibrationAdapter()
    calibration_path = os.path.join(project_root, "sensor_driver", "calibration_coeffs.pt")

    if not os.path.exists(calibration_path):
        print(f"❌ 校准模型不存在: {calibration_path}")
        return

    success = adapter.load_calibration(calibration_path)
    if not success:
        print("❌ 加载校准模型失败")
        return

    # 2. 加载真实数据
    data_dir = "data-0815"
    test_pressures = [10, 25, 50, 100]

    results = []

    for pressure in test_pressures:
        print(f"\n📊 测试压力: {pressure}N")
        print("-" * 30)

        raw_data = load_real_sensor_data(data_dir, pressure)
        if raw_data is None:
            print(f"⚠️ 跳过压力 {pressure}N")
            continue

        # 计算原始数据统计
        raw_mean = raw_data.mean()
        raw_std = raw_data.std()
        raw_cv = raw_std / raw_mean if raw_mean > 0 else 0

        print(f"   原始数据:")
        print(f"   - 均值: {raw_mean:.2f}")
        print(f"   - 标准差: {raw_std:.2f}")
        print(f"   - CV: {raw_cv:.4f}")

        # 应用AI校准
        calibrated_data = adapter.apply_calibration(raw_data)

        # 计算校准后数据统计
        cal_mean = calibrated_data.mean()
        cal_std = calibrated_data.std()
        cal_cv = cal_std / cal_mean if cal_mean > 0 else 0

        print(f"   校准后数据:")
        print(f"   - 均值: {cal_mean:.2f}")
        print(f"   - 标准差: {cal_std:.2f}")
        print(f"   - CV: {cal_cv:.4f}")

        # 计算改善效果
        improvement = raw_cv / cal_cv if cal_cv > 0 else float('inf')
        print(f"   改善效果: {improvement:.2f}倍")

        # 保存结果
        results.append({
            'pressure': pressure,
            'raw_mean': raw_mean,
            'raw_std': raw_std,
            'raw_cv': raw_cv,
            'cal_mean': cal_mean,
            'cal_std': cal_std,
            'cal_cv': cal_cv,
            'improvement': improvement
        })

    # 3. 总结报告
    print("\n📋 测试总结")
    print("=" * 50)

    if results:
        print("压力(N)\t原始CV\t\t校准CV\t\t改善倍数")
        print("-" * 50)
        for r in results:
            print(f"{r['pressure']:6d}\t{r['raw_cv']:8.4f}\t{r['cal_cv']:8.4f}\t{r['improvement']:8.2f}")

        # 计算平均改善
        avg_improvement = np.mean([r['improvement'] for r in results if np.isfinite(r['improvement'])])
        print(f"\n平均改善效果: {avg_improvement:.2f}倍")

        if avg_improvement > 1:
            print("✅ 校准效果良好！")
        else:
            print("⚠️ 校准效果需要优化")
    else:
        print("❌ 没有有效的测试结果")

def analyze_calibration_issues():
    """分析校准问题"""
    print("\n🔍 校准问题分析")
    print("=" * 30)

    # 1. 检查校准系数
    calibration_path = os.path.join(project_root, "sensor_driver", "calibration_coeffs.pt")
    if not os.path.exists(calibration_path):
        print("❌ 校准模型不存在")
        return

    coeffs = torch.load(calibration_path)
    print(f"校准系数形状: {coeffs.shape}")
    print(f"系数范围:")
    print(f"  a (二次): [{coeffs[:, 0].min():.4f}, {coeffs[:, 0].max():.4f}]")
    print(f"  b (一次): [{coeffs[:, 1].min():.4f}, {coeffs[:, 1].max():.4f}]")
    print(f"  c (常数): [{coeffs[:, 2].min():.4f}, {coeffs[:, 2].max():.4f}]")

    # 2. 检查训练数据范围
    data_dir = os.path.join(project_root, "data-0815")
    if os.path.exists(data_dir):
        csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
        print(f"\n训练数据文件: {csv_files}")

        if csv_files:
            sample_file = os.path.join(data_dir, csv_files[0])
            try:
                df = pd.read_csv(sample_file)
                sensor_cols = [col for col in df.columns if col.startswith('data_row_')]
                if sensor_cols:
                    sample_values = []
                    for col in sensor_cols[:10]:  # 取前10个传感器列
                        values = df[col].dropna().values
                        if len(values) > 0:
                            sample_values.extend(values[:5])  # 每个列取前5个值

                    if sample_values:
                        sample_values = np.array(sample_values)
                        print(f"训练数据样本范围: [{sample_values.min():.2f}, {sample_values.max():.2f}]")
                        print(f"训练数据样本均值: {sample_values.mean():.2f}")
            except Exception as e:
                print(f"读取训练数据失败: {e}")

if __name__ == "__main__":
    try:
        # 运行真实数据测试
        test_real_data_calibration()

        # 分析校准问题
        analyze_calibration_issues()

        print("\n🎉 测试完成!")

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

