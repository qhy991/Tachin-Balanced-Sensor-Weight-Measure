"""数据处理中心"""
"""支持多采集卡、标定"""

import warnings
import os
import threading
from collections import deque
import numpy as np
import atexit

import data_handler.preprocessing as preprocessing
from data_handler.interpolation import Interpolation

import json
import sqlite3
from data_handler.convert_data import convert_db_to_csv_multiple_old as convert_db_to_csv_multiple

from config import config_multiple
tracing_list = config_multiple['tracing_list']

# 引入calibrate_adaptor
from calibrate.calibrate_adaptor import CalibrateAdaptor, \
    Algorithm, ManualDirectionLinearAlgorithm

VALUE_DTYPE = '>f2'

SAVE_INTERVAL = 0.08


class DataHandler:

    ZERO_LEN_REQUIRE = 16
    MAX_IN = 16
    DOWNSAMPLE = 2

    def __init__(self, template_sensor_driver, ports, max_len=1024):
        self.max_len = max_len
        self.template_sensor_driver = template_sensor_driver
        self.drivers = [template_sensor_driver() for _ in ports]  # 传感器驱动
        self.ports = ports
        self.lock = threading.Lock()
        # 滤波器
        # self.middle_filter = preprocessing.MedianFilter(sensor_class={'SENSOR_SHAPE':
        #                                                                   [_ // self.DOWNSAMPLE for _ in
        #                                                                    self.template_sensor_driver.SENSOR_SHAPE],
        #                                                               'DATA_TYPE': VALUE_DTYPE},
        #                                                 order=4)
        self.middle_filters = [preprocessing.MedianFilter(sensor_class={'SENSOR_SHAPE':
                                                                          [_ for _ in
                                                                           self.template_sensor_driver.SENSOR_SHAPE],
                                                                      'DATA_TYPE': VALUE_DTYPE},
                                                          order=9) for _ in self.drivers]
        # self.rc_filters = [preprocessing.RCFilterOneSide(sensor_class={'SENSOR_SHAPE':
        #                                                                   [_ for _ in
        #                                                                    self.template_sensor_driver.SENSOR_SHAPE],
        #                                                               'DATA_TYPE': VALUE_DTYPE},
        #                                                     alpha=0.25) for _ in self.drivers]
        self.interpolation = Interpolation(1, 1.,
                                           [_ // self.DOWNSAMPLE for _ in template_sensor_driver.SENSOR_SHAPE])  # 插值
        self.calibration_adaptor: CalibrateAdaptor = CalibrateAdaptor(template_sensor_driver, Algorithm)
        # 数据容器
        self.begin_time = None
        self.zeros = [np.zeros([_ // self.DOWNSAMPLE for _ in template_sensor_driver.SENSOR_SHAPE], dtype=VALUE_DTYPE)
                      for _ in self.drivers]

        self.values = [deque(maxlen=self.max_len) for _ in self.drivers]  # 未降采样。用于置零
        self.values_smoothed = [deque(maxlen=self.max_len) for _ in self.drivers]  # 未降采样，模糊。用于显示
        self.tracing_t = [deque(maxlen=self.max_len) for _ in tracing_list]  # 追踪时间
        self.tracing_points = [deque(maxlen=self.max_len) for _ in tracing_list]  # 追踪点
        # 降采样的数据没有时序存储，只将最新的一帧存入硬盘
        # 保存
        self.output_file = None
        self.cursor = None
        self.path_db = None
        self.times_last_save = [0. for _ in self.drivers]
        # 退出时断开
        atexit.register(self.disconnect)

    # 保存机能

    def link_output_file(self, path):
        # 采集到文件时，打开文件
        try:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            self.output_file = sqlite3.connect(path)
            self.path_db = path
            # self.cursor = self.output_file.cursor()
            # command = 'create table data (time float, time_after_begin float, i_driver, '
            # command += ', '.join([f'data_tracing_{i} float' for i in
            #                       range(tracing_list.__len__())])  # 保存追踪点
            # command += ')'
            # self.cursor.execute(command)
            self.cursor = self.output_file.cursor()
            command = 'create table data (time float, time_after_begin float, i_driver integer, '
            command += ', '.join([f'data_row_{i} text' for i in
                                  range(self.template_sensor_driver.SENSOR_SHAPE[0] // self.DOWNSAMPLE)])
            command += ')'
            self.cursor.execute(command)

        except PermissionError as e:
            print(e)
            raise Exception('文件无法写入。可能正被占用')
        except Exception as e:
            print(e)
            raise Exception('文件无法写入')

    def write_to_file(self, time_now, time_after_begin, data, i_driver):
        if self.output_file is not None:
            # command = f'insert into data values ({time_now}, {time_after_begin}, {i_driver}, '
            # command += ', '.join([str(_)
            #                       for _ in data]) + ')'
            # self.cursor.execute(command)
            command = f'insert into data values ({time_now}, {time_after_begin}, {i_driver}, '
            command += ', '.join(['\"' + (json.dumps(data[_].tolist())) + '\"'
                                  for _ in range(self.template_sensor_driver.SENSOR_SHAPE[0] // self.DOWNSAMPLE)]) + ')'
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
            convert_db_to_csv_multiple(self.path_db)
            self.path_db = None

    # 保存机能结束

    def clear(self):
        for value in self.values:
            value.clear()
        for value in self.values_smoothed:
            value.clear()
        for value in self.tracing_points:
            value.clear()
        for value in self.tracing_t:
            value.clear()
        self.abandon_zero()

    def connect(self, _=None):
        self.begin_time = None
        self.times_last_save = [0. for _ in self.drivers]
        connected = []
        for driver, port in zip(self.drivers, self.ports):
            flag = driver.connect(port)
            if flag:
                connected.append(driver)
            else:
                for driver_connected in connected:
                    driver_connected.disconnect()
                return False
        return True

    def disconnect(self):
        self.close_output_file()
        self.clear()
        for driver in self.drivers:
            driver.disconnect()
        return True

    def trigger(self):
        # 循环触发
        at_least_one_saved = False
        for i_driver, driver in enumerate(self.drivers):
            count_in = self.MAX_IN
            while count_in:  # 循环清除直到最后一个数据
                count_in -= 1
                data, time_now = driver.get()
                if data is not None:
                    value = self.middle_filters[i_driver].filter(
                        self.calibration_adaptor.transform_frame(data * driver.SCALE))
                    value = self.interpolation.smooth(value)
                    # 按照DOWNSAMPLE的尺寸，进行降采样
                    value_ds = value.reshape((value.shape[0] // self.DOWNSAMPLE, self.DOWNSAMPLE,
                                              value.shape[1] // self.DOWNSAMPLE, self.DOWNSAMPLE))\
                        .sum(axis=(1, 3))
                    value_smoothed = value_ds - self.zeros[i_driver]
                    self.values[i_driver].append(value_ds)
                    self.values_smoothed[i_driver].append(value_smoothed)

                    tracing_point_row = [0 for _ in tracing_list]
                    for i_point, tracing_point in enumerate(tracing_list):
                        i_driver_, i_row, i_col = tuple(tracing_point)
                        if i_driver_ == i_driver:
                            tracing_point_row[i_point] = value_smoothed[i_row, i_col]
                            self.lock.acquire()
                            self.tracing_points[i_point].append(value_smoothed[i_row, i_col])
                            self.tracing_t[i_point].append((time_now - self.begin_time)\
                                if self.begin_time is not None else 0)
                            self.lock.release()
                            assert len(self.tracing_points[i_point]) == len(self.tracing_t[i_point])
                    if self.begin_time is None:
                        self.begin_time = time_now
                    time_after_begin = time_now - self.begin_time
                    if time_after_begin - self.times_last_save[i_driver] > SAVE_INTERVAL:
                        self.times_last_save[i_driver] = time_after_begin
                        self.write_to_file(time_now, time_after_begin, value_smoothed, i_driver)
                        at_least_one_saved = True
        if at_least_one_saved:
            self.commit_file()

    def set_zero(self):
        # 置零
        if all([value.__len__() >= self.ZERO_LEN_REQUIRE for value in self.values]):
            for i_d, (zero, value) in enumerate(zip(self.zeros, self.values)):
                self.zeros[i_d][...] = np.mean(np.asarray(value)[-self.ZERO_LEN_REQUIRE:, ...], axis=0)
        else:
            warnings.warn('点数不够，无法置零')

    def abandon_zero(self):
        # 解除置零
        for i_driver, zero in enumerate(self.zeros):
            self.zeros[i_driver][...] = 0.

    def set_interpolation_and_blur(self, interpolate, blur):
        assert interpolate == int(interpolate)
        assert 1 <= interpolate <= 8
        assert blur == float(blur)
        assert 0. <= blur <= 2.
        self.interpolation = Interpolation(interpolate, blur, self.drivers[0].SENSOR_SHAPE)
        pass

    def set_calibrator(self, path):
        try:
            self.calibration_adaptor = CalibrateAdaptor(self.template_sensor_driver, ManualDirectionLinearAlgorithm)
            self.calibration_adaptor.load(path)
            self.abandon_zero()
            return True
        except Exception as e:
            self.abandon_calibrator()
            raise e

    def abandon_calibrator(self):
        self.calibration_adaptor = CalibrateAdaptor(self.template_sensor_driver, Algorithm)


if __name__ == "__main__":
    from backends.sensor_driver import UsbSensorDriver
    dh = DataHandler(UsbSensorDriver, [0, 3])
    dh.connect()
    while True:
        dh.trigger()
        print(dh.values[0].__len__())
        print(dh.values[1].__len__())
