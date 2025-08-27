#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查校准文件内容
"""

import os
import json
import numpy as np

def check_json_calibration():
    """检查JSON校准文件"""
    json_path = "calibration_data/position_calibration_data.json"
    if os.path.exists(json_path):
        print(f"✅ 找到JSON校准文件: {json_path}")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"📄 JSON文件内容:")
            print(f"   - 描述: {data.get('metadata', {}).get('description', 'N/A')}")
            print(f"   - 版本: {data.get('metadata', {}).get('version', 'N/A')}")
            print(f"   - 位置数量: {len(data.get('positions', {}))}")
            
            # 显示中心位置的校准参数
            center = data.get('positions', {}).get('center', {})
            if center:
                cal = center.get('calibration', {})
                print(f"   - 中心位置校准:")
                print(f"     * 斜率: {cal.get('slope', 'N/A')}")
                print(f"     * 截距: {cal.get('intercept', 'N/A')}")
                print(f"     * R²: {cal.get('r_squared', 'N/A')}")
        except Exception as e:
            print(f"❌ 读取JSON文件失败: {e}")
    else:
        print(f"❌ 未找到JSON校准文件: {json_path}")

def check_numpy_calibration():
    """检查NumPy校准文件"""
    npy_path = "calibration_data/校正数据-200帧.npy"
    if os.path.exists(npy_path):
        print(f"✅ 找到NumPy校准文件: {npy_path}")
        try:
            data = np.load(npy_path, allow_pickle=True)
            print(f"📄 NumPy文件内容:")
            print(f"   - 数据类型: {type(data)}")
            print(f"   - 数据形状: {data.shape if hasattr(data, 'shape') else '无形状'}")
            
            if hasattr(data, '__len__') and len(data) > 0:
                print(f"   - 数据长度: {len(data)}")
                if hasattr(data[0], 'shape'):
                    print(f"   - 第一个元素形状: {data[0].shape}")
                else:
                    print(f"   - 第一个元素类型: {type(data[0])}")
                    print(f"   - 第一个元素内容: {data[0]}")
        except Exception as e:
            print(f"❌ 读取NumPy文件失败: {e}")
    else:
        print(f"❌ 未找到NumPy校准文件: {npy_path}")

def test_balance_calibration_adapter():
    """测试BalanceSensorCalibrationAdapter"""
    try:
        from data_processing.data_handler import BalanceSensorCalibrationAdapter
        adapter = BalanceSensorCalibrationAdapter()
        
        print(f"🔧 测试BalanceSensorCalibrationAdapter:")
        
        # 测试JSON文件
        json_path = "calibration_data/position_calibration_data.json"
        if os.path.exists(json_path):
            print(f"   - 测试加载JSON文件...")
            success = adapter.load_calibration(json_path)
            if success:
                info = adapter.get_info()
                print(f"   ✅ JSON文件加载成功")
                print(f"     * 系数: {info.get('coefficient', 'N/A')}")
                print(f"     * 偏置: {info.get('bias', 'N/A')}")
            else:
                print(f"   ❌ JSON文件加载失败")
        
        # 测试NumPy文件
        npy_path = "calibration_data/校正数据-200帧.npy"
        if os.path.exists(npy_path):
            print(f"   - 测试加载NumPy文件...")
            success = adapter.load_calibration(npy_path)
            if success:
                info = adapter.get_info()
                print(f"   ✅ NumPy文件加载成功")
                print(f"     * 系数: {info.get('coefficient', 'N/A')}")
                print(f"     * 偏置: {info.get('bias', 'N/A')}")
            else:
                print(f"   ❌ NumPy文件加载失败")
                
    except ImportError as e:
        print(f"❌ 无法导入BalanceSensorCalibrationAdapter: {e}")
    except Exception as e:
        print(f"❌ 测试BalanceSensorCalibrationAdapter失败: {e}")

if __name__ == "__main__":
    print("🔍 检查校准文件...")
    print("=" * 50)
    
    check_json_calibration()
    print()
    
    check_numpy_calibration()
    print()
    
    test_balance_calibration_adapter()
    print()
    
    print("=" * 50)
    print("检查完成") 