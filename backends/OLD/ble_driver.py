from backends.abstract_sensor_driver import AbstractSensorDriver
from backends.ble_backend import BLEBackend
import os


class UsbSensorDriver(AbstractSensorDriver):
    # 传感器驱动

    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数。与采集卡有关

    def __init__(self, sensor_shape, config_array):
        super(UsbSensorDriver, self).__init__()
        self.SENSOR_SHAPE = sensor_shape
        self.sensor_backend = BLEBackend(config_array)  # 后端自带缓存，一定范围内不丢数据

    @property
    def connected(self):
        return self.sensor_backend.active

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


