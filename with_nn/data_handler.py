import warnings
from with_nn.nn.tactile_distribution_net.tactile_distribution_interface import TactileDistributionInterface

from large.sensor_driver import UsbSensorDriver as SensorDriver
SCALE = (32768. * 25. / 5.) ** -1

from collections import deque
import numpy as np

import data_handler.preprocessing as preprocessing
from data_handler.interpolation import Interpolation


from config import config
interpolate = int(config['interpolate'])
blur = float(config['blur'])


class DataHandler:

    MAX_LEN = 1024
    ZERO_LEN_REQUIRE = 16
    MAX_IN = 16

    def __init__(self):
        self.driver = SensorDriver()
        self.filter_time = preprocessing.Filter(SensorDriver)
        self.filter_frame = preprocessing.Filter(SensorDriver)
        self.preset_filters = preprocessing.build_preset_filters(SensorDriver)
        self.interpolation = Interpolation(interpolate, blur, SensorDriver.SENSOR_SHAPE)
        #
        self.begin_time = None
        self.data = deque(maxlen=self.MAX_LEN)
        self.value = deque(maxlen=self.MAX_LEN)
        self.smoothed_value = deque(maxlen=self.MAX_LEN)
        self.recognized = deque(maxlen=self.MAX_LEN)
        self.time = deque(maxlen=self.MAX_LEN)
        self.zero = np.zeros(SensorDriver.SENSOR_SHAPE, dtype=SensorDriver.DATA_TYPE)
        #
        self.value_mid = deque(maxlen=self.MAX_LEN)
        self.maximum = deque(maxlen=self.MAX_LEN)
        self.tracing = deque(maxlen=self.MAX_LEN)
        self.t_tracing = deque(maxlen=self.MAX_LEN)
        self.tracing_point = (0, 0)
        # 材料识别模型
        self.material_mapping = TactileDistributionInterface(use_log=False)
        for _ in range(2):
            self.material_mapping.classify_material(np.zeros(SensorDriver.SENSOR_SHAPE, dtype=SensorDriver.DATA_TYPE))
        #

    def clear(self):
        self.value.clear()
        self.time.clear()
        self.value_mid.clear()
        self.maximum.clear()
        self.tracing.clear()
        self.t_tracing.clear()
        self.recognized.clear()

    def connect(self, port):
        self.begin_time = None
        flag = self.driver.connect(port)
        return flag

    def disconnect(self):
        self.clear()
        flag = self.driver.disconnect()
        return flag

    def trigger(self):
        count_in = self.MAX_IN
        while count_in:
            count_in -= 1
            data, time_now = self.driver.get()
            if data is not None:
                data_f = self.filter_time.filter(self.filter_frame.filter(data))
                value = np.maximum(data_f - self.zero, 1e-6) * SCALE  # 0409改成电阻的倒数
                if time_now > 0:
                    if self.begin_time is None:
                        self.begin_time = time_now
                    self.data.append(data)
                    self.value.append(value)
                    self.smoothed_value.append(self.interpolation.smooth(value))
                    time_after_begin = time_now - self.begin_time
                    self.time.append(time_after_begin)
                    self.t_tracing.append(time_after_begin)
                    #
                    self.value_mid.append(np.median(value))
                    self.maximum.append(np.max(value))
                    self.tracing.append(value[self.tracing_point[0], self.tracing_point[1]])
                    #
                    self.recognized.append(self.material_mapping.classify_material_async(data))
                    # self.recognized.append(0.5)
            else:
                break

    def set_zero(self):
        if self.data.__len__() >= self.ZERO_LEN_REQUIRE:
            self.zero[...] = np.mean(np.array(self.data)[-self.ZERO_LEN_REQUIRE:], axis=0)
            self.material_mapping.set_zero(np.array(self.recognized)[-self.ZERO_LEN_REQUIRE:])
        else:
            warnings.warn('点数不够，无法置零')

    def abandon_zero(self):
        self.zero[...] = 0

    def set_filter(self, filter_name_frame, filter_name_time):
        try:
            self.filter_frame = self.preset_filters[filter_name_frame]()
            self.filter_time = self.preset_filters[filter_name_time]()
            self.clear()
        except KeyError:
            raise Exception('指定的滤波器不存在')

    def set_tracing(self, i, j):
        if 0 <= i < self.driver.SENSOR_SHAPE[0] and 0 <= j < self.driver.SENSOR_SHAPE[1]:
            self.tracing_point = (i, j)
            self.t_tracing.clear()
            self.tracing.clear()
