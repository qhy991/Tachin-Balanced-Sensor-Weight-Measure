程序包含3类采集卡的通讯实现：
* ls为能斯达采集卡
* small为自研8\*8采集卡（串口）
* large为自研64\*64采集卡（USB）

interface_large_sensor是程序入口
由于large和small两个系列比较接近，且之前有段时间常用large，所以没有分别做入口（都叫large），需要在ordinary\\data_handler.py中切换。此外，因为长期用large调试，一些新加的功能（如滤波器等）在适配small时有一点bug，需要在修改代码时留意



