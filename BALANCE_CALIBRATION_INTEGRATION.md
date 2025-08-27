# Balance-Sensor校准功能集成方案

## 概述

本文档描述了如何将balance-sensor应用的校准功能集成到传感器驱动的数据处理流程中。通过这种集成，可以在传感器驱动的底层数据处理阶段直接应用balance-sensor的校准算法，实现更高效和统一的数据处理。

## 集成架构

### 1. 系统对比

**原始传感器驱动系统**：
- 使用 `CalibrateAdaptor` 和 `Algorithm` 类进行校准
- 支持 `.clb` 和 `.csv` 格式的校准文件
- 在 `DataHandler.trigger()` 方法中应用校准

**Balance-Sensor应用系统**：
- 使用 `CalibrationDataLoader` 类加载校准数据
- 支持 JSON、NumPy、CSV 格式
- 在应用层进行校准处理

### 2. 集成方案

通过添加 `BalanceSensorCalibrationAdapter` 类，在传感器驱动的数据处理流程中集成balance-sensor的校准功能。

## 实现细节

### 1. 新增的类和方法

#### BalanceSensorCalibrationAdapter 类
```python
class BalanceSensorCalibrationAdapter:
    """适配balance-sensor校准格式的适配器"""
    
    def __init__(self):
        self.calibration_data = None
        self.calibration_map = None
        self.coefficient = 1.0
        self.bias = 0.0
        self.is_loaded = False
    
    def load_calibration(self, filepath):
        """加载balance-sensor格式的校准文件"""
        # 支持 .json, .npy, .csv 格式
    
    def apply_calibration(self, raw_data):
        """应用校准到原始数据"""
        # 1. 应用校准映射（如果存在）
        # 2. 应用线性校准：y = kx + b
```

#### DataHandler 新增方法
```python
def set_balance_calibration(self, filepath):
    """设置balance-sensor校准文件"""

def abandon_balance_calibration(self):
    """解除balance-sensor校准"""

def get_balance_calibration_info(self):
    """获取balance-sensor校准信息"""
```

### 2. 数据处理流程

修改后的 `DataHandler.trigger()` 方法：

```python
def trigger(self):
    # 1. 获取原始数据
    data, time_now = self.get_data()
    
    # 2. 应用滤波器
    _ = self.filter_time.filter(self.filter_frame.filter(data))
    
    # 3. 应用原始校准（如果启用）
    value = self.calibration_adaptor.transform_frame(_.astype(float) * self.driver.SCALE)
    
    # 4. 应用balance-sensor校准（如果启用）
    if self.using_balance_calibration:
        value = self.balance_calibration_adaptor.apply_calibration(value)
    
    # 5. 继续后续处理...
```

## 使用方法

### 1. 基本使用

```python
from data_processing.data_handler import DataHandler
from backends.usb_driver import LargeUsbSensorDriver

# 创建数据处理器
data_handler = DataHandler(LargeUsbSensorDriver)

# 加载balance-sensor校准文件
success = data_handler.set_balance_calibration("calibration.json")

# 连接传感器并开始数据采集
data_handler.connect("0")
data_handler.trigger()  # 自动应用校准
```

### 2. 运行示例程序

```bash
cd sensor_driver
python example_balance_calibration_integration.py
```

示例程序提供了完整的GUI界面，可以：
- 连接传感器
- 加载balance-sensor校准文件
- 实时查看原始数据和校准后数据的对比
- 查看校准信息

## 支持的校准文件格式

### 1. JSON格式
```json
{
    "coefficient": 1730.6905,
    "bias": 126.1741,
    "calibration_map": [[1.0, 1.1, ...], [0.9, 1.0, ...], ...],
    "description": "传感器校准数据",
    "timestamp": "2024-01-01 12:00:00"
}
```

### 2. NumPy格式
```python
# 保存为 .npy 文件
calibration_data = {
    'coefficient': 1730.6905,
    'bias': 126.1741,
    'calibration_map': np.array([[1.0, 1.1, ...], [0.9, 1.0, ...], ...]),
    'description': '传感器校准数据'
}
np.save('calibration.npy', calibration_data)
```

### 3. CSV格式
```csv
coefficient,bias
1730.6905,126.1741
```

## 优势

### 1. 统一数据处理
- 在传感器驱动的底层直接应用校准
- 避免在多个应用层重复实现校准逻辑

### 2. 提高性能
- 减少数据传输和处理开销
- 校准后的数据可以直接用于后续分析

### 3. 兼容性
- 保持与原有校准系统的兼容性
- 支持多种校准文件格式

### 4. 可扩展性
- 易于添加新的校准算法
- 支持复杂的校准映射

## 注意事项

### 1. 校准顺序
- 原始校准在balance-sensor校准之前应用
- 确保校准参数的正确性

### 2. 数据格式
- 确保校准映射的形状与传感器数据匹配
- 注意数据类型的一致性

### 3. 性能考虑
- 校准映射会增加计算开销
- 对于实时应用，建议使用简化的校准方法

## 未来扩展

### 1. 位置智能校准
- 集成balance-sensor的位置智能校准功能
- 根据传感器位置自动选择校准参数

### 2. 动态校准
- 支持运行时更新校准参数
- 实现自适应校准算法

### 3. 校准验证
- 添加校准质量评估功能
- 提供校准效果的可视化分析

## 总结

通过这种集成方案，balance-sensor的校准功能可以无缝集成到传感器驱动的数据处理流程中，实现更高效、统一的数据处理。这种方案既保持了系统的兼容性，又提供了强大的校准能力，为传感器数据的准确性和可靠性提供了有力保障。 