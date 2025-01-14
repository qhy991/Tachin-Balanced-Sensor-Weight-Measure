from abstract_sensor_driver import AbstractSensorDriver
import numpy as np
# 需安装pyusb
from config import config_array
import copy
from serial_driver.serial_backend import SerialBackend


class SerialDriver(AbstractSensorDriver):
    # 传感器驱动

    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数。与采集卡有关

    def __init__(self, buffer_length, sensor_shape, bytes_per_point):
        super(AbstractSensorDriver, self).__init__()
        self.SENSOR_SHAPE = sensor_shape
        self.sensor_backend = SerialBackend(buffer_length, sensor_shape, bytes_per_point)  # 后端自带缓存，一定范围内不丢数据

    @property
    def connected(self):
        return self.sensor_backend.active

    def connect(self, port):
        try:
            port = str(port)
            if not port.startswith('COM'):
                raise ValueError()
        except ValueError:
            raise ValueError("错误的设备号格式")
        return self.sensor_backend.start(port)

    def disconnect(self):
        return self.sensor_backend.stop()

    def get(self):
        if self.sensor_backend.err_queue:
            raise self.sensor_backend.err_queue.popleft()
        if self.sensor_backend.buffer:
            self.sensor_backend.lock.acquire()
            bits_and_t = self.sensor_backend.buffer.popleft()
            bits_and_t = (copy.deepcopy(bits_and_t[0]), bits_and_t[1])
            self.sensor_backend.lock.release()
            data = ((bits_and_t[0][0].reshape(self.SENSOR_SHAPE).astype(np.int8).astype(np.int16)) * 256) \
                   + bits_and_t[0][1].reshape(self.SENSOR_SHAPE).astype(np.int16)
            t = bits_and_t[1]
            return data, t
        else:
            return None, None


class LargeSensorDriver(SerialDriver):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        super(LargeSensorDriver, self).__init__(64, self.SENSOR_SHAPE, 2)


class SerialSensorDriver16(SerialDriver):

    SENSOR_SHAPE = (16, 16)

    def __init__(self):
        super(SerialSensorDriver16, self).__init__(64, self.SENSOR_SHAPE, 2)


