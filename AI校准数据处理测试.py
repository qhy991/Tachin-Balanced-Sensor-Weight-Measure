#!/usr/bin/env python3
"""
AI校准数据处理集成测试
测试AI校准功能是否正确集成到传感器数据处理流程中
"""

import numpy as np
import os
import sys
import time

# 添加项目根目录到sys.path（从sensor_driver子目录运行）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sensor_driver.data_processing.data_handler import DataHandler

class MockSensorDriver:
    """模拟传感器驱动"""

    SENSOR_SHAPE = (64, 64)
    DATA_TYPE = np.uint16
    SCALE = 1.0

    def __init__(self):
        self.connected = False
        self.frame_count = 0

    def connect(self, port):
        self.connected = True
        print(f"✅ 模拟传感器已连接: {port}")
        return True

    def disconnect(self):
        self.connected = False
        print("✅ 模拟传感器已断开")
        return True

    def get(self):
        """获取模拟传感器数据"""
        if not self.connected:
            return None, time.time()

        # 生成模拟的64x64传感器数据
        self.frame_count += 1
        # 模拟不同传感器的不均匀响应
        base_signal = 1000 + np.random.normal(0, 50, self.SENSOR_SHAPE)
        # 添加传感器位置相关的偏差
        x, y = np.meshgrid(np.arange(64), np.arange(64))
        position_bias = (x + y) * 5  # 位置偏差
        sensor_bias = np.random.normal(0, 100, self.SENSOR_SHAPE)  # 传感器个体偏差

        raw_data = (base_signal + position_bias + sensor_bias).astype(np.uint16)

        # 每10帧添加一个压力变化
        if self.frame_count % 10 == 0:
            pressure_factor = 1.0 + (self.frame_count // 10) * 0.2
            raw_data = (raw_data * pressure_factor).astype(np.uint16)

        return raw_data, time.time()

def test_ai_calibration_integration():
    """测试AI校准集成"""
    print("🎯 AI校准数据处理集成测试")
    print("=" * 50)

    # 1. 创建数据处理器
    print("\n1. 创建数据处理器...")
    data_handler = DataHandler(MockSensorDriver, max_len=10)

    # 2. 连接传感器
    print("\n2. 连接模拟传感器...")
    success = data_handler.connect("模拟端口")
    if not success:
        print("❌ 连接失败")
        return

    # 3. 加载AI校准模型
    print("\n3. 加载AI校准模型...")
    calibration_path = os.path.join(project_root, "sensor_driver", "calibration_coeffs.pt")
    if not os.path.exists(calibration_path):
        print(f"⚠️ 校准文件不存在: {calibration_path}")
        print("   将使用未校准模式进行测试")
        using_ai_calibration = False
    else:
        success = data_handler.set_ai_calibration(calibration_path)
        using_ai_calibration = success

    # 4. 模拟数据采集和处理
    print("\n4. 开始数据采集和处理...")
    print(f"   AI校准状态: {'已启用' if using_ai_calibration else '未启用'}")

    # 采集20帧数据
    for i in range(20):
        # 触发数据处理
        data_handler.trigger()

        # 获取处理后的数据
        if len(data_handler.value) > 0:
            latest_data = data_handler.value[-1]
            raw_data = data_handler.data[-1] if len(data_handler.data) > 0 else None

            # 计算统计信息
            mean_value = np.mean(latest_data)
            std_value = np.std(latest_data)
            cv_value = std_value / mean_value if mean_value > 0 else 0

            print(f"   帧 {i+1:2d}: 均值={mean_value:.1f}, 标准差={std_value:.1f}, CV={cv_value:.3f}")

            # 每5帧显示一次详细信息
            if (i + 1) % 5 == 0:
                print(f"     └─ 数据形状: {latest_data.shape}")
                print(f"     └─ 数据范围: [{latest_data.min():.1f}, {latest_data.max():.1f}]")

        time.sleep(0.1)  # 模拟帧率

    # 5. 获取校准信息
    if using_ai_calibration:
        print("\n5. AI校准信息:")
        ai_info = data_handler.get_ai_calibration_info()
        if ai_info:
            print(f"   - 模型形状: {ai_info['coeffs_shape']}")
            print(f"   - 计算设备: {ai_info['device']}")
            if ai_info['coeffs_range']:
                print(f"   - 系数范围:")
                print(f"     * a (二次): [{ai_info['coeffs_range']['a'][0]:.4f}, {ai_info['coeffs_range']['a'][1]:.4f}]")
                print(f"     * b (一次): [{ai_info['coeffs_range']['b'][0]:.4f}, {ai_info['coeffs_range']['b'][1]:.4f}]")
                print(f"     * c (常数): [{ai_info['coeffs_range']['c'][0]:.4f}, {ai_info['coeffs_range']['c'][1]:.4f}]")

    # 6. 测试禁用AI校准
    if using_ai_calibration:
        print("\n6. 禁用AI校准...")
        data_handler.abandon_ai_calibration()
        print("   ✅ AI校准已禁用")

    # 7. 清理
    print("\n7. 清理资源...")
    data_handler.disconnect()
    print("   ✅ 测试完成")

def compare_raw_vs_calibrated():
    """比较原始数据和校准后数据的差异"""
    print("\n🔍 原始数据 vs 校准后数据对比测试")
    print("-" * 50)

    # 创建两个数据处理器，一个使用校准，一个不使用
    handler_raw = DataHandler(MockSensorDriver, max_len=5)
    handler_calibrated = DataHandler(MockSensorDriver, max_len=5)

    # 连接传感器
    handler_raw.connect("原始数据端口")
    handler_calibrated.connect("校准数据端口")

    # 启用AI校准
    calibration_path = os.path.join(project_root, "sensor_driver", "calibration_coeffs.pt")
    if os.path.exists(calibration_path):
        handler_calibrated.set_ai_calibration(calibration_path)

    # 采集并比较数据
    raw_stats = []
    calibrated_stats = []

    for i in range(10):
        # 触发数据处理
        handler_raw.trigger()
        handler_calibrated.trigger()

        # 同步数据（确保使用相同的基础数据）
        if len(handler_raw.value) > 0 and len(handler_calibrated.value) > 0:
            raw_data = handler_raw.value[-1]
            cal_data = handler_calibrated.value[-1]

            raw_cv = np.std(raw_data) / np.mean(raw_data)
            cal_cv = np.std(cal_data) / np.mean(cal_data)

            raw_stats.append(raw_cv)
            calibrated_stats.append(cal_cv)

            print(f"   对比 {i+1:2d}: 原始CV={raw_cv:.3f}, 校准CV={cal_cv:.3f}")

        time.sleep(0.05)

    # 计算平均改善
    if raw_stats and calibrated_stats:
        avg_raw_cv = np.mean(raw_stats)
        avg_cal_cv = np.mean(calibrated_stats)
        improvement = avg_raw_cv / avg_cal_cv if avg_cal_cv > 0 else float('inf')

        print(f"\n📊 对比结果:")
        print(f"   - 平均原始CV: {avg_raw_cv:.3f}")
        print(f"   - 平均校准CV: {avg_cal_cv:.3f}")
        print(f"   - CV改善倍数: {improvement:.1f}倍")

    # 清理
    handler_raw.disconnect()
    handler_calibrated.disconnect()

if __name__ == "__main__":
    try:
        # 运行集成测试
        test_ai_calibration_integration()

        # 运行对比测试
        compare_raw_vs_calibrated()

        print("\n🎉 所有测试完成!")

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
