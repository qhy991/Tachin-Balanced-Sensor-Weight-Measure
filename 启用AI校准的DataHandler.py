#!/usr/bin/env python3
"""
启用AI校准的DataHandler使用示例
"""

import numpy as np
import os
import sys

# 添加项目根目录到sys.path
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

    def connect(self, port):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False
        return True

    def get(self):
        """获取模拟传感器数据"""
        if not self.connected:
            return None, 0

        # 生成模拟真实传感器数据
        np.random.seed()
        base_signal = 200 + np.random.normal(0, 50, self.SENSOR_SHAPE)
        position_bias = np.arange(64).reshape(1, -1) + np.arange(64).reshape(-1, 1)
        sensor_bias = np.random.normal(0, 100, self.SENSOR_SHAPE)

        raw_data = base_signal + position_bias * 2 + sensor_bias
        raw_data = np.maximum(raw_data, 0).astype(np.uint16)

        return raw_data, 0

def demonstrate_datahandler_with_ai_calibration():
    """演示带AI校准的DataHandler使用"""
    print("🚀 DataHandler + AI校准演示")
    print("=" * 50)

    # 1. 创建数据处理器
    print("\n1. 创建数据处理器...")
    data_handler = DataHandler(MockSensorDriver)

    # 2. 连接传感器
    print("\n2. 连接传感器...")
    success = data_handler.connect("模拟端口")
    if not success:
        print("❌ 连接失败")
        return

    # 3. 启用AI校准
    print("\n3. 启用AI校准...")
    calibration_path = os.path.join(project_root, "sensor_driver", "calibration_coeffs.pt")

    if not os.path.exists(calibration_path):
        print(f"❌ 校准模型不存在: {calibration_path}")
        print("请先运行校准训练脚本生成模型文件")
        return

    success = data_handler.set_ai_calibration(calibration_path)
    if not success:
        print("❌ AI校准启用失败")
        return

    print("✅ AI校准已启用！")
    print("   现在所有传感器数据都会自动进行AI校准")

    # 4. 处理数据并显示结果
    print("\n4. 开始数据处理...")
    print("按 Ctrl+C 停止测试")

    frame_count = 0
    try:
        while frame_count < 10:  # 处理10帧数据
            # 触发数据处理（这会自动应用AI校准）
            data_handler.trigger()

            # 获取处理后的数据
            if len(data_handler.value) > 0:
                frame_count += 1
                latest_data = data_handler.value[-1]

                # 计算统计信息
                mean_val = latest_data.mean()
                std_val = latest_data.std()
                cv_val = std_val / mean_val if mean_val > 0 else 0

                print(f"   帧 {frame_count:2d}: 均值={mean_val:7.2f}, 标准差={std_val:7.2f}, CV={cv_val:.4f}")

                if frame_count % 5 == 0:
                    print(f"     └─ AI校准已应用 ✅")

    except KeyboardInterrupt:
        print("\n🛑 用户中断测试")

    # 5. 获取校准信息
    print("\n5. AI校准信息:")
    ai_info = data_handler.get_ai_calibration_info()
    if ai_info:
        print(f"   - 模型状态: {'已加载' if ai_info['is_loaded'] else '未加载'}")
        print(f"   - 模型形状: {ai_info['coeffs_shape']}")
        print(f"   - 计算设备: {ai_info['device']}")

    # 6. 禁用AI校准
    print("\n6. 禁用AI校准...")
    data_handler.abandon_ai_calibration()
    print("✅ AI校准已禁用")

    # 7. 清理
    print("\n7. 清理资源...")
    data_handler.disconnect()
    print("✅ 测试完成")

def show_integration_code():
    """显示集成代码"""
    integration_code = '''
# 在你的传感器应用中集成AI校准

import numpy as np
from sensor_driver.data_processing.data_handler import DataHandler

# 1. 创建数据处理器（使用你的传感器驱动）
data_handler = DataHandler(YourSensorDriverClass)

# 2. 连接传感器
data_handler.connect("your_port")

# 3. 启用AI校准
calibration_path = "sensor_driver/calibration_coeffs.pt"
success = data_handler.set_ai_calibration(calibration_path)

if success:
    print("✅ AI校准已启用")
    print("所有传感器数据都会自动进行AI校准")

    # 4. 在主循环中处理数据
    while True:
        # 触发数据处理（自动应用AI校准）
        data_handler.trigger()

        # 获取校准后的数据
        if len(data_handler.value) > 0:
            calibrated_data = data_handler.value[-1]

            # 使用校准后的数据进行后续处理
            # ... 你的应用逻辑 ...

else:
    print("❌ AI校准启用失败")

# 程序结束时清理资源
data_handler.disconnect()
'''

    print("\n📋 集成代码示例:")
    print("=" * 30)
    print(integration_code)

def main():
    """主函数"""
    try:
        # 运行演示
        demonstrate_datahandler_with_ai_calibration()

        # 显示集成代码
        show_integration_code()

        print("\n🎉 AI校准功能已成功集成到DataHandler中！")
        print("你现在可以在任何使用DataHandler的项目中启用AI校准功能了。")

    except Exception as e:
        print(f"\n❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

