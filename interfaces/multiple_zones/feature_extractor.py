# 用于从一个子区域内提取动作识别逻辑

import numpy as np
from collections import deque
import threading
import pickle
import atexit
import os
from data_processing.preprocessing import RCFilterHP
from data_processing.preprocessing import RCFilter
from interfaces.multiple_zones.feature_extractor_model import FeatureExtractorStatistics

SCALE = 32768. * 25. / 5.

def scale_in(x):
    x = x * SCALE
    THRESHOLD = 5
    return np.log10(np.maximum(THRESHOLD, x)) - np.log10(THRESHOLD)

def scale_out(x):
    # sigmoid
    return (np.exp(x) - 1.) / (np.exp(x) + 1.)

EPS = 1e-6
SENSOR_SHAPE = (8, 8)
XX = (np.arange(SENSOR_SHAPE[0]) - (SENSOR_SHAPE[0] - 1) / 2).reshape((SENSOR_SHAPE[0], 1))
YY = (np.arange(SENSOR_SHAPE[1]) - (SENSOR_SHAPE[1] - 1) / 2).reshape((1, SENSOR_SHAPE[1]))

def fit(data):
    # 获取时间维度
    time = np.arange(data.shape[0]).reshape((-1, 1))  # 形状为 (32, 1)
    k = np.zeros(data.shape[1:])  # 初始化 k 矩阵 (8, 8)
    b = np.zeros(data.shape[1:])  # 初始化 b 矩阵 (8, 8)

    # 对每个传感器位置进行拟合
    for i in range(data.shape[1]):  # 遍历 8 行
        for j in range(data.shape[2]):  # 遍历 8 列
            # 提取该位置的时间序列数据
            y = data[:, i, j]
            # 使用最小二乘法拟合 y = k * time + b
            A = np.hstack([time, np.ones_like(time)])  # 设计矩阵
            params, _, _, _ = np.linalg.lstsq(A, y, rcond=None)  # 最小二乘拟合
            k[i, j], b[i, j] = params  # 提取拟合参数

    return k[None, :, :] * time[:, :, None] + b[None, :, :]

class FeatureExtractor:

    def __init__(self, parameters=None):

        if parameters is None:
            parameters = {}
        self.history_length = parameters.get('maximum_length', 64)
        self.window_length = parameters.get('window_length', 32)
        self.window_buffer_length = parameters.get('window_buffer_length', 4)
        self.result_length = parameters.get('result_length', 32)
        self.name = parameters.get('name')
        self.data_updated = False
        # 滤波器，自适应置零
        self.path_filter_dump = os.path.join(os.path.dirname(__file__), 'dumping', f'filter_{self.name}.pkl')
        self.filter = RCFilterHP({'SENSOR_SHAPE': SENSOR_SHAPE, 'DATA_TYPE': float}, alpha=0.001)
        self.__load_filter()
        atexit.register(self.__save_filter)
        # 直接数据，形如8*8
        self.history_storage = deque(maxlen=self.history_length)
        self.data_storage = deque(maxlen=self.window_length + self.window_buffer_length)  # 因为要提取，所以有缓冲
        self.data_storage_minor = deque(maxlen=self.window_length + self.window_buffer_length)  # 带低通
        self.__result_storage = deque(maxlen=self.result_length)
        #
        self.lock_in = threading.Lock()
        self.lock_out = threading.Lock()
        # 模型
        assert self.name in ['0', '1', '2']
        self.statistics = FeatureExtractorStatistics(name=self.name)
        #
        threading.Thread(target=self.recognize_forever, daemon=True).start()

    def stream_in(self, data):
        filtered = self.filter.filter(scale_in(data))
        self.data_storage.append(filtered)
        with self.lock_in:
            self.data_updated = True
        return filtered

    def recognize_forever(self):
        while True:
            if self.data_updated:
                with self.lock_in:
                    self.data_updated = False
                self.do_recognize()
            else:
                # 等待数据更新
                threading.Event().wait(0.001)

    def do_recognize(self):
        if not (self.data_storage.__len__() >= self.window_length
                and self.history_storage.__len__() == self.history_length):
            print(f"Not enough data to recognize: {self.data_storage.__len__()} < {self.window_length}，"
                  f"history: {self.history_storage.__len__()} < {self.history_length}")

            result = {'press': None, 'slide': None, 'pat': None}
            if self.data_storage:
                self.history_storage.append(self.data_storage[0])
        else:
            ref = np.array(self.history_storage)
            data = np.array(self.data_storage)[-self.window_length:]
            # 整体差值。因为有滤波，直接认为均值就是0
            over_mean = data.copy()
            # over_mean形如(32, 8, 8)。将其拟合为over_mean = k * np.arange(32) * b，其中k, b 为8*8矩阵
            fit_over_mean = fit(over_mean)
            one_direction = np.sum(np.maximum(np.diff(fit_over_mean, axis=0), 0.))
            # 波动性
            fluctuation = np.sum(np.std(over_mean - fit_over_mean, axis=0))
            # 计算data的重心
            strength = np.sum(np.abs(over_mean), axis=(1, 2))
            moment_x = np.sum(np.abs(over_mean) * XX[None, :, :], axis=(1, 2))
            moment_y = np.sum(np.abs(over_mean) * YY[None, :, :], axis=(1, 2))
            # 以上strength, moment_x, moment_y都是一维向量，计算重心转移指标
            center_x = moment_x / (strength + EPS)
            center_y = moment_y / (strength + EPS)
            # 计算重心转移
            summed_slide_x = 0.
            summed_slide_y = 0.
            count = 0
            for i in range(self.window_length):
                for j in range(i + 1, self.window_length):
                    x_transfer = center_x[j] - center_x[i]
                    y_transfer = center_y[j] - center_y[i]
                    strength_transfer = min([strength[j], strength[i]])
                    summed_slide_x += x_transfer * strength_transfer
                    summed_slide_y += y_transfer * strength_transfer
                    count += 1
            slide_magnitude = np.sqrt(summed_slide_x ** 2 + summed_slide_y ** 2) / count
            # 系数
            press = scale_out(one_direction)
            slide = scale_out(slide_magnitude)
            pat = scale_out(fluctuation * 4.)

            result = {
                'press': press,
                'slide': slide,
                'pat': pat
            }
            self.statistics.data_in(result)
        with self.lock_out:
            self.__result_storage.append(result)

    def get_result_storage(self):
        with self.lock_out:
            return list(self.__result_storage)

    def __load_filter(self):
        if os.path.exists(self.path_filter_dump):
            with open(self.path_filter_dump, 'rb') as f:
                self.filter.y_low = pickle.load(f)
        else:
            print(f"Filter file {self.path_filter_dump} does not exist, using default filter.")

    def __save_filter(self):
        if not os.path.exists(os.path.dirname(self.path_filter_dump)):
            os.makedirs(os.path.dirname(self.path_filter_dump))
        with open(self.path_filter_dump, 'wb') as f:
            pickle.dump(self.filter.y_low, f)
        print(f"Filter saved to {self.path_filter_dump}")


if __name__ == '__main__':
    print(scale_out(np.arange(0., 5.0, 0.1)))

