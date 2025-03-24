from scipy import signal
import numpy as np


# lfilter_zi


# 添加一个装饰器。如果filter输入的x不是一个numpy.ndarray，进行某种处理
def check_input(func):
    def wrapper(self, x):
        if not isinstance(x, np.ndarray):
            x.full_data = func(self, x.full_data)
            return x
        else:
            return func(self, x)
    return wrapper


class Filter:

    def __init__(self, sensor_class, *args, **kwargs):
        if isinstance(sensor_class, dict):
            self.SENSOR_SHAPE = sensor_class['SENSOR_SHAPE']
            self.DATA_TYPE = sensor_class['DATA_TYPE']
        else:
            self.SENSOR_SHAPE = sensor_class.SENSOR_SHAPE
            self.DATA_TYPE = sensor_class.DATA_TYPE

    @check_input
    def filter(self, x):
        return x

    def __mul__(self, other):
        return _CombinedFilter({'SENSOR_SHAPE': self.SENSOR_SHAPE, 'DATA_TYPE': self.DATA_TYPE},
                               self, other)


class _CombinedFilter(Filter):
    def __init__(self, sensor_class, this, other, *args, **kwargs):
        super().__init__(sensor_class, *args, **kwargs)
        self.filter1 = this
        self.filter2 = other

    @check_input
    def filter(self, x):
        return self.filter2.filter(self.filter1.filter(x))


class RCFilter(Filter):
    def __init__(self, sensor_shape, alpha=0.75, *args, **kwargs):
        super(RCFilter, self).__init__(sensor_shape)
        self.alpha = alpha
        self.y = 0

    @check_input
    def filter(self, x):
        self.y = self.alpha * x + (1 - self.alpha) * self.y
        # 看看阶数
        return self.y


class RCFilterOneSide(Filter):
    def __init__(self, sensor_class, alpha=0.75, *args, **kwargs):
        super(RCFilterOneSide, self).__init__(sensor_class)
        self.alpha = alpha
        self.y = np.zeros(self.SENSOR_SHAPE, dtype=self.DATA_TYPE)
        self.last_x = np.zeros(self.SENSOR_SHAPE, dtype=self.DATA_TYPE)

    @check_input
    def filter(self, x):
        y_up = (1 - self.alpha) * x + self.alpha * self.y
        y_down = (1 + self.alpha) * x + (- self.alpha) * self.y
        channels_down = np.where(x < self.last_x, 1., 0.)
        self.last_x = x.copy()
        self.y = y_down * channels_down + y_up * (1. - channels_down)
        return self.y


class RCFilterLimited(Filter):
    def __init__(self, sensor_class, alpha=0.25, lim=0.25, *args, **kwargs):
        super(RCFilterLimited, self).__init__(sensor_class)
        self.alpha = alpha
        self.lim = lim
        self.y = 0

    @check_input
    def filter(self, x):
        self.y = self.alpha * x + (1. - self.alpha) * self.y
        # 看看阶数
        return x - self.y


# ButterworthFilter
class ButterworthFilter(Filter):
    def __init__(self, sensor_class, cutoff, fs, order, *args, **kwargs):
        super(ButterworthFilter, self).__init__(sensor_class)
        self.b, self.a = signal.butter(order, cutoff / (fs / 2), btype='lowpass', analog=False)
        self.zi = [[signal.lfilter_zi(self.b, self.a) for _ in range(self.SENSOR_SHAPE[1])]
                   for _ in range(self.SENSOR_SHAPE[0])]

    @check_input
    def filter(self, x):
        filtered = np.ndarray(self.SENSOR_SHAPE, dtype=self.DATA_TYPE)
        for i in range(self.SENSOR_SHAPE[0]):
            for j in range(self.SENSOR_SHAPE[1]):
                filtered[i, j], self.zi[i][j] = signal.lfilter(self.b, self.a, [x[i, j]], zi=self.zi[i][j])
        return filtered


class MedianFilter(Filter):
    def __init__(self, sensor_class, order):
        super(MedianFilter, self).__init__(sensor_class)
        self.passed_values = np.zeros((order + 1, self.SENSOR_SHAPE[0], self.SENSOR_SHAPE[1]),
                                      dtype=self.DATA_TYPE)

    @check_input
    def filter(self, x):
        self.passed_values = np.roll(self.passed_values, 1, axis=0)
        self.passed_values[0, ...] = x
        return np.median(self.passed_values, axis=0)


class MeanFilter(Filter):
    def __init__(self, sensor_class, order):
        super(MeanFilter, self).__init__(sensor_class)
        self.passed_values = np.zeros((order + 1, self.SENSOR_SHAPE[0], self.SENSOR_SHAPE[1]),
                                      dtype=self.DATA_TYPE)

    @check_input
    def filter(self, x):
        self.passed_values = np.roll(self.passed_values, 1, axis=0)
        self.passed_values[0, ...] = x
        return np.mean(self.passed_values, axis=0)


class CrosstalkFilter(Filter):

    def __init__(self, sensor_class, base_length, weight, iteration_count):
        super(CrosstalkFilter, self).__init__(sensor_class)
        self.base_length = base_length
        self.weight = weight
        self.iteration_count = iteration_count
        #
        xx = np.arange(sensor_class.SENSOR_SHAPE[0]).reshape((-1, 1))
        yy = np.arange(sensor_class.SENSOR_SHAPE[1]).reshape((1, -1))
        self.length_modification = (xx + yy + self.base_length) / self.base_length if self.base_length is not None \
            else np.ones(sensor_class.SENSOR_SHAPE)
        #
        self.size = np.sqrt(self.SENSOR_SHAPE[0] * self.SENSOR_SHAPE[1])

    @check_input
    def filter(self, x):
        x = np.maximum(x.astype(float), 1.)
        for _ in range(self.iteration_count):
            # mean = np.mean(x * self.size)
            by_row = np.sum(x, axis=1, keepdims=True)
            by_col = np.sum(x, axis=0, keepdims=True)
            by_row_weighted = np.sum(x * by_col, axis=1, keepdims=True) / np.sum(by_col, axis=1, keepdims=True)
            by_col_weighted = np.sum(x * by_row, axis=0, keepdims=True) / np.sum(by_row, axis=0, keepdims=True)
            # crossed = by_row_weighted ** -1 + by_col_weighted ** -1 + mean ** -1
            crossed = by_row_weighted ** -1 + by_col_weighted ** -1
            x = np.maximum(x - crossed ** -1 * self.weight, 1.)
        return x * self.length_modification


class BlurFilter(Filter):

    def __init__(self, sensor_class, kernel_size, radius):
        super(BlurFilter, self).__init__(sensor_class)
        coord = np.arange(kernel_size) - kernel_size // 2 + 0.5
        dist_sq = coord.reshape(-1, 1) ** 2 + coord.reshape(1, -1) ** 2
        kernel = np.exp(-dist_sq / radius)
        self.kernel = kernel / np.sum(kernel)

    @check_input
    def filter(self, x):
        return signal.convolve2d(x, self.kernel, mode='same')


class SideFilter(Filter):
    # 抑制边缘
    def __init__(self, sensor_class, width):
        super(SideFilter, self).__init__(sensor_class)
        self.width = width

    @check_input
    def filter(self, x):
        x = x.copy()
        # 越靠近边缘，衰减越多
        x[:self.width, :] *= np.linspace(0, 1, self.width)[:, None]
        x[-self.width:, :] *= np.linspace(1, 0, self.width)[:, None]
        x[:, :self.width] *= np.linspace(0, 1, self.width)[None, :]
        x[:, -self.width:] *= np.linspace(1, 0, self.width)[None, :]
        return x


def build_preset_filters(sensor_class):
    str_to_filter = {
        '无': lambda: Filter(sensor_class),
        'RC-轻': lambda: RCFilter(sensor_class, alpha=0.75),
        'RC-重': lambda: RCFilter(sensor_class, alpha=0.25),
        '中值-短': lambda: MedianFilter(sensor_class, order=2),
        '中值-长': lambda: MedianFilter(sensor_class, order=6),
        '中值-0.2s': lambda: MedianFilter(sensor_class, order=2),
        '中值-1s': lambda: MedianFilter(sensor_class, order=20),
        '均值-短': lambda: MeanFilter(sensor_class, order=2),
        '均值-长': lambda: MeanFilter(sensor_class, order=6),
        '均值-极长': lambda: MeanFilter(sensor_class, order=19),
        '均值-0.2s': lambda: MeanFilter(sensor_class, order=2),
        '均值-1s': lambda: MeanFilter(sensor_class, order=20),
        '并联抵消-轻': lambda: CrosstalkFilter(sensor_class, None, 0.2, 3),
        '并联抵消-中': lambda: CrosstalkFilter(sensor_class, None, 0.3, 4),
        '并联抵消-重': lambda: CrosstalkFilter(sensor_class, None, 0.4, 5),
        'None': lambda: Filter(sensor_class),
        'Median-0.2s': lambda: MedianFilter(sensor_class, order=2),
        'Median-1s': lambda: MedianFilter(sensor_class, order=20),
        'Average-0.2s': lambda: MeanFilter(sensor_class, order=2),
        'Average-1s': lambda: MeanFilter(sensor_class, order=20),
        '边缘-4': lambda: SideFilter(sensor_class, 4),
    }
    return str_to_filter


if __name__ == '__main__':
    arr = [0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0, 1, 2, 3, 4, 5]
    f = RCFilterOneSide(sensor_class={"SENSOR_SHAPE": (1, 1), "DATA_TYPE": '>f2'}, alpha=0.)
    for v in arr:
        vv = f.filter(np.array([[v]]))
        print(v, vv, f.y)
