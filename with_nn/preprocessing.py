from scipy import signal
import numpy as np
# lfilter_zi


class Filter:

    def __init__(self, sensor_class, *args, **kwargs):
        self.SENSOR_SHAPE = sensor_class.SENSOR_SHAPE
        self.DATA_TYPE = sensor_class.DATA_TYPE

    def filter(self, x):
        return x


class RCFilter(Filter):
    def __init__(self, sensor_shape, alpha=0.75, *args, **kwargs):
        super(RCFilter, self).__init__(sensor_shape)
        self.alpha = alpha
        self.y = 0

    def filter(self, x):
        self.y = self.alpha * x + (1 - self.alpha) * self.y
        # 看看阶数
        return self.y


# ButterworthFilter
class ButterworthFilter(Filter):
    def __init__(self, sensor_class, cutoff, fs, order, *args, **kwargs):
        super(ButterworthFilter, self).__init__(sensor_class)
        self.b, self.a = signal.butter(order, cutoff / (fs / 2), btype='lowpass', analog=False)
        self.zi = [[signal.lfilter_zi(self.b, self.a) for _ in range(self.SENSOR_SHAPE[1])]
                   for _ in range(self.SENSOR_SHAPE[0])]

    def filter(self, x):
        filtered = np.ndarray(self.SENSOR_SHAPE, dtype=self.DATA_TYPE)
        for i in range(self.SENSOR_SHAPE[0]):
            for j in range(self.SENSOR_SHAPE[1]):
                filtered[i, j], self.zi[i][j] = signal.lfilter(self.b, self.a, [x[i, j]], zi=self.zi[i][j])
        print(np.linalg.norm(filtered - x))
        return filtered


class MedianFilter(Filter):
    def __init__(self, sensor_class, order):
        super(MedianFilter, self).__init__(sensor_class)
        self.passed_values = np.zeros((order + 1, self.SENSOR_SHAPE[0], self.SENSOR_SHAPE[1]),
                                      dtype=self.DATA_TYPE)

    def filter(self, x):
        self.passed_values = np.roll(self.passed_values, 1, axis=0)
        self.passed_values[0, ...] = x
        return np.median(self.passed_values, axis=0)


def build_preset_filters(sensor_class):

    NULL = Filter(sensor_class)
    RC_05 = RCFilter(sensor_class, alpha=0.5)
    RC_075 = RCFilter(sensor_class, alpha=0.75)
    BUTT = ButterworthFilter(sensor_class, cutoff=8, fs=20, order=5)
    MEDIAN_2 = MedianFilter(sensor_class, order=2)
    MEDIAN_4 = MedianFilter(sensor_class, order=4)
    str_to_filter = {'无': NULL,
                     'RC-heavy': RC_05,
                     'RC-light': RC_075,
                     'Butterworth': BUTT,
                     'Median-short': MEDIAN_2,
                     'Median-long': MEDIAN_4}
    str_to_filter = {k: lambda: v for k, v in str_to_filter.items()}
    return str_to_filter


class IsotropyFilter(Filter):

    def __init__(self, sensor_class, kernel_radius, kernel_scale, weight):
        super(IsotropyFilter, self).__init__(sensor_class)
        self.kernel_radius = kernel_radius
        self.kernel_scale = kernel_scale
        # 高斯核
        xx = np.arange(-kernel_radius, kernel_radius + 1, dtype=float)
        kernel_1d = np.exp(-np.abs(xx) / self.kernel_scale)
        summed = np.sum(kernel_1d)
        kernel_1d = -kernel_1d
        kernel_1d = kernel_1d / summed * weight
        kernel_1d[kernel_radius] = 0.
        kernel_1d[kernel_radius] = 1. - np.sum(kernel_1d)
        self.kernel = np.zeros((2 * kernel_radius + 1, 2 * kernel_radius + 1), dtype=float)
        self.kernel[kernel_radius, :] = kernel_1d
        self.kernel[:, kernel_radius] = kernel_1d
        print(self.kernel)


    def filter(self, x):
        return signal.convolve2d(x, self.kernel, mode='same')



