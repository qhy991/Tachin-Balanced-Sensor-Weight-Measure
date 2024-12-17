from abstract_sensor_driver import AbstractSensorDriver
import numpy as np
# 需安装pyusb
from config import config_array
import copy
from large.usb_backend import UsbBackend


class UsbSensorDriver(AbstractSensorDriver):
    # 传感器驱动

    SENSOR_SHAPE = (64, 64)  # 形状
    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数。与采集卡有关

    def __init__(self):
        super(UsbSensorDriver, self).__init__()
        self.sensor_backend = UsbBackend(16)  # 后端自带缓存，一定范围内不丢数据

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


