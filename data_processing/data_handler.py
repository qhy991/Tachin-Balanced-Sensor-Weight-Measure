"""数据处理中心"""

import os
import warnings
from collections import deque
import numpy as np
import atexit
import data_processing.preprocessing as preprocessing
from data_processing.interpolation import Interpolation
import json
import sqlite3
from data_processing.convert_data import convert_db_to_csv
from config import config

import threading

# 引入calibrate_adaptor
from data_processing.calibrate_adaptor import CalibrateAdaptor
from data_processing.sensor_calibrate import Algorithm, ManualDirectionLinearAlgorithm

VALUE_DTYPE = float


class DataHandler:

    ZERO_LEN_REQUIRE = 32
    MAX_IN = 16

    def __init__(self, template_sensor_driver, max_len=64, curve_on=True):
        self.max_len = max_len
        self.driver = template_sensor_driver()  # 传感器驱动
        # 滤波器
        self.filter_time = preprocessing.Filter(template_sensor_driver)  # 当前的时间滤波。可被设置
        self.filter_frame = preprocessing.Filter(template_sensor_driver)  # 当前的空间滤波。可被设置
        self.filters_for_each = None
        self.filter_after_zero = preprocessing.Filter(template_sensor_driver)
        self.preset_filters = preprocessing.build_preset_filters(template_sensor_driver)  # 下拉菜单里可设置的滤波器
        self.interpolation = Interpolation(1, 0., template_sensor_driver.SENSOR_SHAPE)  # 插值。可被设置
        self.curve_on = curve_on
        #
        # region_count为0表示为单片；否则为分片
        if template_sensor_driver.__name__ == 'TactileDriverWithPreprocessing':
            self.region_count = template_sensor_driver.range_mapping.__len__()
        else:
            self.region_count = 0
        # 分片模式下，数据的处理方式会有区别
        self.calibration_adaptor: CalibrateAdaptor = CalibrateAdaptor(self.driver, Algorithm)  # 标定器
        self.using_calibration = False
        # 数据容器
        self.begin_time = None
        self.data = deque(maxlen=self.max_len)  # 直接从SensorDriver获得的数据
        self.filtered_data = deque(maxlen=self.max_len)  # 直接从SensorDriver获得的数据
        self.value_before_zero = deque(maxlen=self.max_len)
        self.value = deque(maxlen=self.max_len)  # 经过所有处理，但未通过interpolation，也未做对数尺度变换。对自研卡，未开启标定时，是电阻(kΩ)的倒数
        self.time = deque(maxlen=self.max_len)  # 从connect后首个采集点开始到现在的时间
        self.time_ms = deque(maxlen=self.max_len)  # ms上的整型。通讯专用
        self.zero = np.zeros(template_sensor_driver.SENSOR_SHAPE, dtype=template_sensor_driver.DATA_TYPE)  # 零点
        self.value_zero = np.zeros(template_sensor_driver.SENSOR_SHAPE, dtype=template_sensor_driver.DATA_TYPE)
        self.value_mid = deque(maxlen=self.max_len)  # 中值
        self.maximum = deque(maxlen=self.max_len)  # 峰值
        self.summed = deque(maxlen=self.max_len)  # 总值
        self.tracing = deque(maxlen=self.max_len)  # 追踪点
        self.t_tracing = deque(maxlen=self.max_len)  # 追踪点的时间。由于更新追踪点时会清空，故单独记录
        self.tracing_point = (0, 0)  # 当前的追踪点
        self.lock = threading.Lock()
        self.zero_set = False
        # 保存
        self.output_file = None
        self.cursor = None
        self.path_db = None
        # 退出时断开
        atexit.register(self.disconnect)
        #
        self.dump_interval = config.get("dump_interval", 5.) * 0.001
        self.next_dump = 0.

    # 保存功能
    def link_output_file(self, path):
        # 采集到文件时，打开文件
        try:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            self.output_file = sqlite3.connect(path)
            self.path_db = path
            self.cursor = self.output_file.cursor()
            if self.region_count == 0:  # 无分区
                command = 'create table data (time float, time_after_begin float, '\
                          + ', '.join([f'data_row_{i} text'
                                      for i in range(self.driver.SENSOR_SHAPE[0])
                                      ])\
                          + ')'
            else:
                # SplitDataDict 模式
                command = 'create table data (time float, time_after_begin float, ' \
                          + ', '.join([f'data_region_{i}_row_{j} text'
                                       for i in range(self.region_count)
                                       for j in range(self.driver.SENSOR_SHAPE[0])
                                       ]) \
                          + ')'
            self.cursor.execute(command)

        except PermissionError as e:
            raise Exception('文件无法写入。可能正被占用')
        except Exception as e:
            raise Exception('文件无法写入')

    def write_to_file(self, time_now, time_after_begin, data):
        if self.output_file is not None:
            if time_after_begin - self.next_dump > 2 * self.dump_interval:
                self.next_dump = 0.
            if self.next_dump == 0.:
                self.next_dump = time_after_begin
            if time_after_begin >= self.next_dump:
                if self.region_count == 0:
                    command = f'insert into data values ({time_now}, {time_after_begin}, ' \
                              + ', '.join(['\"' + json.dumps(_.tolist()) + '\"' for _ in data]) + ')'
                else:
                    # SplitDataDict 模式
                    data_list = sum([['\"' + json.dumps(_.tolist()) + '\"' for _ in data[k]] for k in data.keys()], [])
                    command = f'insert into data values ({time_now}, {time_after_begin}, ' \
                              + ', '.join(data_list) + ')'
                self.cursor.execute(command)
                self.commit_file()
                self.next_dump = self.next_dump + self.dump_interval

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

    # 保存功能结束

    def clear(self):
        self.lock.acquire()
        self.data.clear()
        self.filtered_data.clear()
        self.value_before_zero.clear()
        self.value.clear()
        self.time.clear()
        self.time_ms.clear()
        self.value_mid.clear()
        self.maximum.clear()
        self.summed.clear()
        self.tracing.clear()
        self.t_tracing.clear()
        self.lock.release()

    @property
    def smoothed_value(self):
        warnings.warn("OBSOLETE API: smoothed_value")
        return self.value

    def connect(self, port):
        self.begin_time = None
        flag = self.driver.connect(port)  # 会因import的驱动类型而改变
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
                # 原始数据
                # 滤波数据
                _ = self.filter_time.filter(self.filter_frame.filter(data))
                if self.filters_for_each is not None:
                    for k in self.filters_for_each:
                        _[k] = self.filters_for_each[k].filter(_[k])

                value = self.calibration_adaptor.transform_frame(_.astype(float) * self.driver.SCALE)
                value = self.interpolation.smooth(value)
                # 换算值
                value_before_zero = value
                value = self.filter_after_zero.filter(value - self.zero)
                # 时间
                if self.begin_time is None:
                    self.begin_time = time_now
                time_after_begin = time_now - self.begin_time
                self.lock.acquire()
                self.data.append(data)
                # self.filtered_data.append(data_f)
                self.value_before_zero.append(value_before_zero)
                self.value.append(value)
                self.time.append(time_after_begin)
                if self.curve_on:
                    self.t_tracing.append(time_after_begin)
                    self.time_ms.append(np.array([(time_after_begin * 1e3) % 10000], dtype='>i2'))  # ms
                    self.value_mid.append(np.median(value))
                    self.maximum.append(np.max(value))
                    self.summed.append(np.sum(value))
                    self.tracing.append(np.mean(np.asarray(value)[
                                                   self.tracing_point[0] * self.interpolation.interp
                                                   : (self.tracing_point[0] + 1) * self.interpolation.interp,
                                                   self.tracing_point[1] * self.interpolation.interp
                                                   : (self.tracing_point[1] + 1) * self.interpolation.interp]))
                self.lock.release()
                #

                self.write_to_file(time_now, time_after_begin, data)
            else:
                break
        # print(f"取得数据{self.MAX_IN - count_in}条")

    def set_zero(self):
        # 置零
        if self.value_before_zero.__len__() >= self.ZERO_LEN_REQUIRE + self.filter_time.order * 2:
            self.zero_set = True
            self.zero = np.mean(np.maximum(np.asarray(self.value_before_zero)[-self.ZERO_LEN_REQUIRE:, ...], 0), axis=0)
            self.clear()
            return True
        else:
            # print('数据不足，无法置零')
            return False

    def abandon_zero(self):
        # 解除置零
        self.zero = np.zeros([_ * self.interpolation.interp for _ in self.driver.SENSOR_SHAPE],
                             dtype=self.driver.DATA_TYPE)
        self.zero_set = False

    def set_filter(self, filter_name_frame, filter_name_time):
        try:
            self.filter_frame = self.preset_filters[filter_name_frame]()
            self.filter_time = self.preset_filters[filter_name_time]()
            self.abandon_zero()
            self.clear()
        except KeyError:
            raise Exception('指定的滤波器不存在')

    def set_tracing(self, i, j):
        # 鼠标选点时，设置追踪点
        if 0 <= i < self.driver.SENSOR_SHAPE[0] and 0 <= j < self.driver.SENSOR_SHAPE[1]:
            self.tracing_point = (i, j)
            self.t_tracing.clear()
            self.tracing.clear()

    def set_interpolation_and_blur(self, interpolate, blur):
        assert interpolate == int(interpolate)
        assert 1 <= interpolate <= 8
        assert blur == float(blur)
        assert 0. <= blur <= 8.
        self.interpolation = Interpolation(interpolate, blur, self.driver.SENSOR_SHAPE)
        self.abandon_zero()
        self.clear()

    def set_calibrator(self, path, forced_to_use_clb=False):
        try:
            self.calibration_adaptor = CalibrateAdaptor(self.driver, ManualDirectionLinearAlgorithm)
            self.calibration_adaptor.load(path, forced_to_use_clb)
            self.abandon_zero()
            self.clear()
            self.using_calibration = True
            return True
        except Exception as e:
            self.abandon_calibrator()
            raise e

    def abandon_calibrator(self):
        self.calibration_adaptor = CalibrateAdaptor(self.driver, Algorithm)
        self.abandon_zero()
        self.clear()
        self.using_calibration = False
