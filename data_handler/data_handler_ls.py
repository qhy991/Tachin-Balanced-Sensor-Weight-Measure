import warnings
import os

from collections import deque
import numpy as np
import atexit
import shutil

import data_handler.preprocessing as preprocessing
from data_handler.interpolation import Interpolation

import json
import sqlite3

from data_handler.convert_data import convert_db_to_csv

# from small.sensor_driver import SmallSensorDriver as SensorDriver
# SCALE = (4096. * 25. / 3.3) ** -1

# from large.sensor_driver import LargeSensorDriver as SensorDriver
# SCALE = (32768. * 25. / 5.) ** -1

from ls.sensor_driver import LSSensorDriver as SensorDriver
SCALE = 1.


class DataHandler:

    MAX_LEN = 1024
    ZERO_LEN_REQUIRE = 16
    MAX_IN = 16

    def __init__(self):
        self.driver = SensorDriver()
        self.filter_time = preprocessing.Filter(SensorDriver)
        self.filter_frame = preprocessing.Filter(SensorDriver)
        self.preset_filters = preprocessing.build_preset_filters(SensorDriver)
        self.interpolation = Interpolation(1, 0., SensorDriver.SENSOR_SHAPE)  # 插值s
        #
        self.begin_time = None
        self.data = deque(maxlen=self.MAX_LEN)
        self.value = deque(maxlen=self.MAX_LEN)
        self.smoothed_value = deque(maxlen=self.MAX_LEN)
        self.time = deque(maxlen=self.MAX_LEN)
        self.zero = np.zeros(SensorDriver.SENSOR_SHAPE, dtype=SensorDriver.DATA_TYPE)
        #
        self.value_mid = deque(maxlen=self.MAX_LEN)
        self.maximum = deque(maxlen=self.MAX_LEN)
        self.tracing = deque(maxlen=self.MAX_LEN)
        self.t_tracing = deque(maxlen=self.MAX_LEN)
        self.tracing_point = (0, 0)
        #
        self.output_file = None
        self.cursor = None
        self.path_db = None
        atexit.register(self.disconnect)
        #
        try:
            shutil.rmtree('./record_data.csv')
        except:
            pass

    def link_output_file(self, path):
        try:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            self.output_file = sqlite3.connect(path)
            self.path_db = path
            self.cursor = self.output_file.cursor()
            command = 'create table data (time float, time_after_begin float, '\
                      + ', '.join([f'data_row_{i} text'
                                  for i in range(self.driver.SENSOR_SHAPE[0])
                                  ])\
                      + ')'
            self.cursor.execute(command)

        except PermissionError as e:
            print(e)
            raise Exception('文件无法写入。可能正被占用')
        except Exception as e:
            print(e)
            raise Exception('文件无法写入')

    def write_to_file(self, time_now, time_after_begin, data):
        if self.output_file is not None:
            command = f'insert into data values ({time_now}, {time_after_begin}, ' \
                      + ', '.join(['\"' + json.dumps(_.tolist()) + '\"' for _ in data]) + ')'
            self.cursor.execute(command)

    def commit_file(self):
        if self.output_file is not None:
            self.output_file.commit()

    def close_output_file(self):
        if self.output_file:
            self.commit_file()
            output_file = self.output_file
            self.output_file = None
            self.cursor = None
            output_file.close()
            convert_db_to_csv(self.path_db)
            self.path_db = None

    def clear(self):
        self.abandon_zero()
        self.value.clear()
        self.time.clear()
        self.value_mid.clear()
        self.maximum.clear()
        self.tracing.clear()
        self.t_tracing.clear()

    def connect(self, port):
        self.begin_time = None
        flag = self.driver.connect(port)
        return flag

    def disconnect(self):
        self.close_output_file()
        self.clear()
        flag = self.driver.disconnect()
        return flag

    def trigger(self):
        # 循环触发
        count_in = self.MAX_IN
        while count_in:
            count_in -= 1
            data, time_now = self.driver.get()
            if data is not None:
                data_f = self.filter_time.filter(self.filter_frame.filter(data))
                value = np.maximum(data_f - self.zero, 1) * SCALE  # 0409改成电阻的倒数
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
                    self.write_to_file(time_now, time_after_begin, data)
                # self.commit_file()
            else:
                break
        # print(f"取得数据{self.MAX_IN - count_in}条")

    def set_zero(self):
        if self.data.__len__() >= self.ZERO_LEN_REQUIRE:
            self.zero[...] = np.mean(np.array(self.data)[-self.ZERO_LEN_REQUIRE:], axis=0)
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

    def set_interpolation_and_blur(self, interpolate, blur):
        assert interpolate == int(interpolate)
        assert 1 <= interpolate <= 8
        assert blur == float(blur)
        assert 0. <= blur <= 2.
        self.interpolation = Interpolation(interpolate, blur, SensorDriver.SENSOR_SHAPE)
        pass
