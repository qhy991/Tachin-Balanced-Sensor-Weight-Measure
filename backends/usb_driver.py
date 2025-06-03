from backends.abstract_sensor_driver import AbstractSensorDriver
import json
from backends.usb_backend import UsbBackend
import os

class UsbSensorDriver(AbstractSensorDriver):
    # 传感器驱动

    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数。与采集卡有关

    def __init__(self, sensor_shape, config_array):
        super(UsbSensorDriver, self).__init__()
        self.SENSOR_SHAPE = sensor_shape
        self.sensor_backend = UsbBackend(config_array)  # 后端自带缓存，一定范围内不丢数据

    @property
    def connected(self):
        return self.sensor_backend.active

    def get_available_sources(self):
        # 获取可用的USB设备
        names_found = self.sensor_backend.get_available_sources()
        return names_found

    def connect(self, port):
        try:
            port = int(port)
        except ValueError:
            raise ValueError("错误的设备号格式")
        return self.sensor_backend.start(port)

    def disconnect(self):
        return self.sensor_backend.stop()

    def get(self):
        if self.sensor_backend.err_queue:
            raise self.sensor_backend.err_queue.popleft()
        data, t = self.sensor_backend.get()
        return data, t

    def get_last(self):
        if self.sensor_backend.err_queue:
            raise self.sensor_backend.err_queue.popleft()
        data, t = self.sensor_backend.get_last()
        return data, t


class LargeUsbSensorDriver(UsbSensorDriver):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        # config_array = json.load(open(os.path.dirname(__file__) + '/config_array_zv.json', 'rt'))
        config_array = json.load(open(os.path.dirname(__file__) + '/config_array_64.json', 'rt'))
        super(LargeUsbSensorDriver, self).__init__(self.SENSOR_SHAPE, config_array)


class ZWUsbSensorDriver(UsbSensorDriver):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.dirname(__file__) + '/config_array_zw.json', 'rt'))
        super(ZWUsbSensorDriver, self).__init__(self.SENSOR_SHAPE,
                                                config_array)


class ZYUsbSensorDriver(UsbSensorDriver):
    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.dirname(__file__) + '/config_array_zy.json', 'rt'))
        super(ZYUsbSensorDriver, self).__init__(self.SENSOR_SHAPE,
                                                config_array)


class ZVUsbSensorDriver(UsbSensorDriver):
    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.dirname(__file__) + '/config_array_zv.json', 'rt'))
        super(ZVUsbSensorDriver, self).__init__(self.SENSOR_SHAPE,
                                                config_array)


class GLUsbSensorDriver(UsbSensorDriver):
    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.dirname(__file__) + '/config_array_gl.json', 'rt'))
        super(GLUsbSensorDriver, self).__init__(self.SENSOR_SHAPE,
                                                config_array)



if __name__ == '__main__':
    import time
    driver = LargeUsbSensorDriver()
    driver.connect(0)
    while True:
        data, t = driver.get()
        if data is not None:
            print(data)
            print(t)
        else:
            time.sleep(0.001)

