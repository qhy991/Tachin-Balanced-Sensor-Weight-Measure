import numpy as np

# 添加一个装饰器。如果filter输入的x不是一个numpy.ndarray，进行某种处理
def check_input(func):
    def wrapper(self, x):
        if not isinstance(x, np.ndarray):  # 适用SplitDict
            x = x.copy()
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
        self.order = 0

    @property
    def sensor_class(self):
        return {'SENSOR_SHAPE': self.SENSOR_SHAPE, 'DATA_TYPE': self.DATA_TYPE}

    @check_input
    def filter(self, x):
        return x

    def reset(self):
        pass

    def __mul__(self, other):
        if isinstance(other, Filter):
            return _CombinedFilter({'SENSOR_SHAPE': self.SENSOR_SHAPE, 'DATA_TYPE': self.DATA_TYPE},
                                   self, other)
        elif isinstance(float(other), float):
            return _ResizedFilter({'SENSOR_SHAPE': self.SENSOR_SHAPE, 'DATA_TYPE': self.DATA_TYPE},
                                  self, other)
        else:
            raise TypeError("不支持的操作数类型")

class _CombinedFilter(Filter):
    def __init__(self, sensor_class, this, other, *args, **kwargs):
        super().__init__(sensor_class, *args, **kwargs)
        self.filter1 = this
        self.filter2 = other

    @check_input
    def filter(self, x):
        return self.filter2.filter(self.filter1.filter(x))

class _ResizedFilter(Filter):
    def __init__(self, sensor_class, this, rate, *args, **kwargs):
        super().__init__(sensor_class, *args, **kwargs)
        self.this = this
        self.rate = rate

    @check_input
    def filter(self, x):
        return self.rate * self.this.filter(x) + (1 - self.rate) * x


class RCFilter(Filter):
    def __init__(self, sensor_class, alpha=0.75, *args, **kwargs):
        super(RCFilter, self).__init__(sensor_class)
        self.alpha = alpha
        self.y = 0

    @check_input
    def filter(self, x):
        self.y = self.alpha * x + (1 - self.alpha) * self.y
        return self.y


class RCFilterHP(Filter):
    def __init__(self, sensor_class, alpha=0.75, limit=None, *args, **kwargs):
        super(RCFilterHP, self).__init__(sensor_class)
        self.alpha = alpha
        self.y_low = 0  # 存储低通滤波状态
        assert limit is None or limit > 0
        self.limit = limit  # 可选的限制值

    @check_input
    def filter(self, x):
        y_low = self.alpha * x + (1 - self.alpha) * self.y_low
        self.y_low = (np.clip(y_low, self.y_low - self.limit, self.y_low + self.limit)) if self.limit is not None else y_low
        # 高通 = 原始信号 - 低通成分
        y_high = x - self.y_low
        return y_high

    def reset(self):
        super().reset()
        self.y_low = 0

# 未测试
class BandPassFilter:
    def __init__(self, sensor_class, low_cutoff, high_cutoff, *args, **kwargs):
        """
        带通滤波器
        :param sensor_class: 传感器的形状和数据类型
        :param low_cutoff: 高通滤波器的截止频率（时间步数）
        :param high_cutoff: 低通滤波器的截止频率（时间步数）
        """
        self.sensor_class = sensor_class
        self.low_filter = RCFilterHP(sensor_class, alpha=1 - 1 / low_cutoff)
        self.high_filter = RCFilter(sensor_class, alpha=1 - 1 / high_cutoff)

    def filter(self, x):
        """
        对输入数据进行带通滤波
        :param x: 输入数据
        :return: 滤波后的数据
        """
        high_passed = self.low_filter.filter(x)
        band_passed = self.high_filter.filter(high_passed)
        return band_passed

    def reset(self):
        """
        重置滤波器状态
        """
        self.low_filter.reset()
        self.high_filter.reset()

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


class MedianFilter(Filter):
    def __init__(self, sensor_class, order):
        super(MedianFilter, self).__init__(sensor_class)
        self.passed_values = np.zeros((order + 1, self.SENSOR_SHAPE[0], self.SENSOR_SHAPE[1]),
                                      dtype=self.DATA_TYPE)
        self.order = order

    @check_input
    def filter(self, x):
        self.passed_values = np.roll(self.passed_values, 1, axis=0)
        self.passed_values[0, ...] = x
        return np.median(self.passed_values, axis=0)


class MaximumFilter(Filter):
    def __init__(self, sensor_class, order):
        super(MaximumFilter, self).__init__(sensor_class)
        self.passed_values = np.zeros((order + 1, self.SENSOR_SHAPE[0], self.SENSOR_SHAPE[1]),
                                      dtype=self.DATA_TYPE)

    @check_input
    def filter(self, x):
        self.passed_values = np.roll(self.passed_values, 1, axis=0)
        self.passed_values[0, ...] = x
        return np.max(self.passed_values, axis=0)


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
        x_original = x
        for _ in range(self.iteration_count):
            # mean = np.mean(x * self.size)
            by_row = np.sum(x, axis=1, keepdims=True)
            by_col = np.sum(x, axis=0, keepdims=True)
            by_row_weighted = np.sum(x * by_col, axis=1, keepdims=True) / np.sum(by_col, axis=1, keepdims=True)
            by_col_weighted = np.sum(x * by_row, axis=0, keepdims=True) / np.sum(by_row, axis=0, keepdims=True)
            # crossed = by_row_weighted ** -1 + by_col_weighted ** -1 + mean ** -1
            crossed = by_row_weighted ** -1 + by_col_weighted ** -1
            x = np.maximum(x - crossed ** -1 * self.weight, 1.)
        assert np.all(x * self.length_modification <= x_original)
        return x * self.length_modification

class ExtensionFilter(Filter):

    def __init__(self, sensor_class, weight_row, weight_col, iteration_count):
        super().__init__(sensor_class)
        self.weight_row = weight_row
        self.weight_col = weight_col
        assert weight_row + weight_col < 1.
        self.iteration_count = iteration_count

    @check_input
    def filter(self, x):
        x_original = x
        x = np.maximum(x, 0)
        for _ in range(self.iteration_count):
            by_row = np.sum(x, axis=1, keepdims=True) / self.SENSOR_SHAPE[1]
            by_col = np.sum(x, axis=0, keepdims=True) / self.SENSOR_SHAPE[0]
            x = np.maximum(x - by_row * self.weight_row - by_col * self.weight_col, 0)
        return x


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

class FactorFilter(Filter):

    def __init__(self, sensor_class, dim, rate, reverse):
        super(FactorFilter, self).__init__(sensor_class)
        self.dim = dim
        self.rate = rate
        self.reverse = reverse

class OverallFocusFilter(Filter):

    def __init__(self, sensor_class, power):
        super(OverallFocusFilter, self).__init__(sensor_class)
        self.power = power

    @check_input
    def filter(self, x):
        x = np.maximum(x, 0.)
        original_sum = np.sum(x)
        target_sum = np.sum(x ** self.power) ** (self.power ** -1)
        if original_sum == 0:
            return x
        else:
            return x * (target_sum / original_sum)


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
        '单向抵消-轻': lambda: ExtensionFilter(sensor_class, 0.1, 0.1, 5),
        '单向抵消-中': lambda: ExtensionFilter(sensor_class, 0.2, 0.2, 10),
        '单向抵消-重': lambda: ExtensionFilter(sensor_class, 0.3, 0.3, 20),
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
    f = RCFilterOneSide(sensor_class={"SENSOR_SHAPE": (1, 1), "DATA_TYPE": float}, alpha=0.)
    for v in arr:
        vv = f.filter(np.array([[v]]))
        print(v, vv, f.y)
