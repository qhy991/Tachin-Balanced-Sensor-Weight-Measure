from backends.abstract_sensor_driver import AbstractSensorDriver
import json
from backends.serial_backend import SerialBackend
import os


class SerialSensorDriver(AbstractSensorDriver):
    # 传感器驱动

    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数。与采集卡有关

    def __init__(self, sensor_shape, config_array):
        super(SerialSensorDriver, self).__init__()
        self.SENSOR_SHAPE = sensor_shape
        self.sensor_backend = SerialBackend(config_array)  # 后端自带缓存，一定范围内不丢数据

    @property
    def connected(self):
        return self.sensor_backend.active

    def connect(self, port):
        try:
            port = str(port)
            assert port.startswith("COM")
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


class Serial16SensorDriver(SerialSensorDriver):

    SENSOR_SHAPE = (16, 16)

    def __init__(self):
        config_array = json.load(open(os.path.dirname(__file__) + '/config_array_16.json', 'rt'))
        super(Serial16SensorDriver, self).__init__(self.SENSOR_SHAPE, config_array)



