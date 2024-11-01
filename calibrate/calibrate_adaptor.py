# algorithm_class 是 sensor_calibrate.py 中 Algorithm 的子类
import numpy as np
from calibrate.sensor_calibrate import Algorithm, ManualDirectionLinearAlgorithm, ManualInterpolationAlgorithm
eps = 1e-12

#
# def average_2x2_blocks(arr):
#     # 获取输入数组的形状
#     h, w = arr.shape
#
#     # 确保数组的形状是 2 的倍数
#     assert h % 2 == 0 and w % 2 == 0, "Array dimensions must be multiples of 2"
#
#     # 计算每个 2x2 小格的平均值
#     result = np.mean(arr.reshape(h // 2, 2, w // 2, 2), axis=(1, 3), keepdims=True)
#     result = np.repeat(np.repeat(result, 2, axis=1), 2, axis=3)
#
#     return result


class CalibrateAdaptor:

    def __init__(self, sensor_class, algorithm_class):
        sensor_shape = sensor_class.SENSOR_SHAPE
        self.algorithm_class = algorithm_class
        self.algorithm = algorithm_class(sensor_class, None)
        self.__sensor_shape = sensor_shape

    def load(self, path):
        content = ''.join(open(path, 'rt').readlines())
        assert self.algorithm.load(content)

    def transform_frame(self, voltage_frame):
        # 将一帧从原始数据变为标定结果
        # 原始数据为量化电压
        assert voltage_frame.shape == self.__sensor_shape
        force_frame = self.algorithm.transform_streaming(voltage_frame)
        # force_frame = average_2x2_blocks(force_frame)
        return force_frame

    def __bool__(self):
        return self.algorithm_class.IS_NOT_IDLE

