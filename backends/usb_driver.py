from backends.abstract_sensor_driver import SensorDriver
import json
from backends.usb_backend import UsbBackend
import os



def trans(frame):
    # 修正
    COEF = -0.037
    PERIOD = 8
    COL_OFFSET = -7
    ROW_OFFSET = 1
    COL_FROM = range(7, 71, PERIOD)

    for col_from in COL_FROM:
        col_to = col_from + COL_OFFSET
        for row_from in range(0, 64):
            row_to = row_from + ROW_OFFSET
            if col_to < 0 or col_to >= 64 or row_to < 0 or row_to >= 64:
                continue
            frame[row_to, col_to] += (frame[row_from, col_from] * COEF).astype(frame.dtype)
    pass


class UsbSensorDriver(SensorDriver):
    # 传感器驱动

    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数。与采集卡有关

    def __init__(self, sensor_shape, config_array):
        super(UsbSensorDriver, self).__init__()
        self.SENSOR_SHAPE = sensor_shape
        self.sensor_backend = UsbBackend(config_array)  # 后端自带缓存，一定范围内不丢数据
        self.trans = trans

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
        if data is not None:
            self.trans(data)
        return data, t

    def get_last(self):
        if self.sensor_backend.err_queue:
            raise self.sensor_backend.err_queue.popleft()
        data, t = self.sensor_backend.get_last()
        if data is not None:
            self.trans(data)
        return data, t

class UsbSensorDriverWithValidation(UsbSensorDriver):

    def __init__(self, sensor_shape, config_array):
        super(UsbSensorDriverWithValidation, self).__init__(sensor_shape, config_array)
        try:
            self.key_str = open(os.path.join(os.path.dirname(__file__), '../config_files/key.txt'), 'rt').read().strip()
        except FileNotFoundError:
            self.key_str = None

    def connect(self, port):
        flag = super(UsbSensorDriverWithValidation, self).connect(port)
        dna = self.sensor_backend.query_dna()
        if dna is not None:
            if self.key_str is None:
                raise Exception("未找到激活文件")
            else:
                self.sensor_backend.set_key(self.key_str)
        else:
            pass
        return flag


class LargeUsbSensorDriver(UsbSensorDriver):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        # config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_zv.json'), 'rt'))
        config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_64.json'), 'rt'))
        super(LargeUsbSensorDriver, self).__init__(self.SENSOR_SHAPE, config_array)

class LargeUsbSensorDriverSpecialHand(UsbSensorDriver):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_special_hand.json'), 'rt'))
        super(LargeUsbSensorDriverSpecialHand, self).__init__(self.SENSOR_SHAPE, config_array)


class LargeUsbSensorDriverYL(UsbSensorDriver):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_special_hand.json'), 'rt'))
        config_array["extra_swap"] = []
        for i_original in range(16, 32):
            for j_original in range(34, 40):
                i_destination = 31 - i_original
                j_destination = j_original - 6
                config_array["extra_swap"].append(((i_original, j_original), (i_destination, j_destination)))
        super(LargeUsbSensorDriverYL, self).__init__(self.SENSOR_SHAPE, config_array)


class ZWUsbSensorDriver(UsbSensorDriver):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_zv.json'), 'rt'))
        super(ZWUsbSensorDriver, self).__init__(self.SENSOR_SHAPE,
                                                config_array)

class ZWUsbSensorDriverWithValidation(UsbSensorDriverWithValidation):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_zv.json'), 'rt'))
        super(ZWUsbSensorDriverWithValidation, self).__init__(self.SENSOR_SHAPE,
                                                config_array)


class ZYUsbSensorDriver(UsbSensorDriver):
    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_64.json'), 'rt'))
        super(ZYUsbSensorDriver, self).__init__(self.SENSOR_SHAPE,
                                                config_array)


class ZVUsbSensorDriver(UsbSensorDriver):
    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_zv.json'), 'rt'))
        super(ZVUsbSensorDriver, self).__init__(self.SENSOR_SHAPE,
                                                config_array)


class GLUsbSensorDriver(UsbSensorDriver):
    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        config_array = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_gl.json'), 'rt'))
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

