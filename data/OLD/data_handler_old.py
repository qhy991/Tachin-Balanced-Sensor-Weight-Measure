"""数据处理中心"""

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

import threading

# 引入calibrate_adaptor
from calibrate.calibrate_adaptor import CalibrateAdaptor, \
    Algorithm, ManualDirectionLinearAlgorithm

VALUE_DTYPE = '>f2'


class DataHandler:

    ZERO_LEN_REQUIRE = 16
    MAX_IN = 16

    def __init__(self, template_sensor_driver, max_len=1024):
        self.max_len = max_len
        self.driver = template_sensor_driver()  # 传感器驱动
        # 滤波器
        self.filter_basic_median = preprocessing.Filter(template_sensor_driver)  # 缺省中值滤波。未启用
        self.filter_time = preprocessing.Filter(template_sensor_driver)  # 当前的时间滤波。可被设置
        self.filter_frame = preprocessing.Filter(template_sensor_driver)  # 当前的空间滤波。可被设置
        self.preset_filters = preprocessing.build_preset_filters(template_sensor_driver)  # 下拉菜单里可设置的滤波器
        self.interpolation = Interpolation(1, 0., template_sensor_driver.SENSOR_SHAPE)  # 插值。可被设置
        #
        self.single_mode = not (template_sensor_driver.__name__ == 'TactileDriverWithPreprocessing')  # 整片模式
        # 分片模式下，数据的处理方式会有区别
        self.calibration_adaptor: CalibrateAdaptor = CalibrateAdaptor(self.driver, Algorithm)  # 标定器
        # 数据容器
        self.begin_time = None
        self.data = deque(maxlen=self.max_len)  # 直接从SensorDriver获得的数据
        self.value = deque(maxlen=self.max_len)  # 经过所有处理，但未通过interpolation，也未做对数尺度变换。对自研卡，未开启标定时，是电阻(kΩ)的倒数
        self.smoothed_value = deque(maxlen=self.max_len)  # 与value相同，但经过interpolation
        self.time = deque(maxlen=self.max_len)  # 从connect后首个采集点开始到现在的时间
        self.time_ms = deque(maxlen=self.max_len)  # ms上的整型。通讯专用
        self.zero = np.zeros(template_sensor_driver.SENSOR_SHAPE, dtype=template_sensor_driver.DATA_TYPE)  # 零点
        self.value_mid = deque(maxlen=self.max_len)  # 中值
        self.maximum = deque(maxlen=self.max_len)  # 峰值
        self.tracing = deque(maxlen=self.max_len)  # 追踪点
        self.t_tracing = deque(maxlen=self.max_len)  # 追踪点的时间。由于更新追踪点时会清空，故单独记录
        self.tracing_point = (0, 0)  # 当前的追踪点
        self.lock = threading.Lock()
        # 保存
        self.output_file = None
        self.cursor = None
        self.path_db = None
        # 退出时断开
        atexit.register(self.disconnect)

    # 保存功能
    # 待优化：目前每行所有数存成json。很不优雅

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

    # 保存功能结束

    def clear(self):
        self.lock.acquire()
        self.abandon_zero()
        self.data.clear()
        self.value.clear()
        self.time.clear()
        self.time_ms.clear()
        self.value_mid.clear()
        self.maximum.clear()
        self.tracing.clear()
        self.t_tracing.clear()
        self.lock.release()

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
                data_f = self.filter_time.filter(self.filter_frame.filter(self.filter_basic_median.filter(data)))
                # data_f = data.copy()
                if self.single_mode:  # 仅常规数据使用平滑
                    smoothed_data_f = self.interpolation.smooth(data_f)
                    smoothed_zero = self.interpolation.smooth(self.zero)
                else:
                    smoothed_data_f = self.interpolation.smooth(data_f)
                    smoothed_zero = self.zero
                # value = np.maximum(data_f - self.zero, 1e-6) * SCALE  # 0409改成电阻的倒数
                # 关于用电阻倒数尺度还是对数尺度，长期以来都在变化。目前的版本是对数，发到前端的是电阻的负对数
                if self.driver.SCALE != 1.:  # SCALE非1的都是我们自己的卡
                    value = ((data_f - self.zero) * self.driver.SCALE).astype(VALUE_DTYPE)
                    smoothed_value = ((smoothed_data_f - smoothed_zero) * self.driver.SCALE).astype(VALUE_DTYPE)
                    # if not self.single_mode:
                    #     value = data_f.copy()
                    #     smoothed_value = smoothed_data_f.copy()
                else:
                    value = data_f - self.zero
                    smoothed_value = smoothed_data_f - smoothed_zero
                value = self.calibration_adaptor.transform_frame(value)
                if self.begin_time is None:
                    self.begin_time = time_now
                time_after_begin = time_now - self.begin_time
                self.lock.acquire()
                self.data.append(data)
                self.value.append(value)
                self.smoothed_value.append(smoothed_value)
                self.time.append(time_after_begin)
                self.t_tracing.append(time_after_begin)
                self.time_ms.append(np.array([time_after_begin * 1e3], dtype='>i2'))  # ms
                self.value_mid.append(np.median(smoothed_value))
                self.maximum.append(np.max(smoothed_value))
                self.tracing.append(np.mean(np.asarray(smoothed_value)[
                                               self.tracing_point[0] * self.interpolation.interp : (self.tracing_point[0] + 1) * self.interpolation.interp,
                                               self.tracing_point[1] * self.interpolation.interp : (self.tracing_point[1] + 1) * self.interpolation.interp]))
                self.lock.release()
                #

                self.write_to_file(time_now, time_after_begin, data)
                # self.commit_file()
            else:
                break
        # print(f"取得数据{self.MAX_IN - count_in}条")

    def set_zero(self):
        # 置零
        if self.data.__len__() >= self.ZERO_LEN_REQUIRE:
            self.zero[...] = np.mean(np.asarray(self.data)[-self.ZERO_LEN_REQUIRE:, ...], axis=0)
        else:
            warnings.warn('点数不够，无法置零')

    def abandon_zero(self):
        # 解除置零
        self.zero[...] = 0

    def set_filter(self, filter_name_frame, filter_name_time):
        try:
            self.filter_frame = self.preset_filters[filter_name_frame]()
            self.filter_time = self.preset_filters[filter_name_time]()
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
        assert 0. <= blur <= 4.
        self.interpolation = Interpolation(interpolate, blur, self.driver.SENSOR_SHAPE)
        pass

    def set_calibrator(self, path):
        try:
            self.calibration_adaptor = CalibrateAdaptor(self.driver, ManualDirectionLinearAlgorithm)
            self.calibration_adaptor.load(path)
            return True
        except Exception as e:
            self.abandon_calibrator()
            raise e

    def abandon_calibrator(self):
        self.calibration_adaptor = CalibrateAdaptor(self.driver, Algorithm)
