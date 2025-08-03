# 维护说明

## 原理

项目为电子皮肤驱动。各模块功能按信息流向顺序如下。

backends：
- 
- backends下的\*_backend.py为硬件驱动。某些驱动涉及配置文件，如config_serial.json、config_can.json等
- decoding.py对通讯协议进行解析（不同硬件驱动的消息格式是统一的）。对通讯中的点位顺序与传感器空间顺序不一致的，可以交换，相关配置文件形如config_array_\*.json
- backends下的\*_driver.py根据应用场景选择\*\_backend和config_array\_\*.json。它们均是SensorDriver的子类
- (Optional) tactile_split.py提供一种特殊的数据格式SplitDataDict（其行为类似字典），并提供以此数据格式为输出的SensorDriver的子类，相关配置文件形如config_mapping_\*.json

最终，backends给出一个SensorDriver的子类


data_processing:
-
- data_handler.py为数据处理的枢纽。它从SensorDriver提取数据，并管理预处理、标定、特征提取、数据历史等
- filters.py提供各种滤波器
- interpolation.py提供插值方法，注意它可能改变数据的阵列规模
- calibrate_adaptor.py提供标定功能

最终，data_processing给出一个DataHandler对象

interfaces:
-
- user_interface_\*.py提供各种各样的GUI界面。针对各具体应用，存在大量硬编码，可不仔细维护
- 用QT编辑器编辑\*.ui文件，导出为layout_\*.py，再在user_interface_\*.py中导入

