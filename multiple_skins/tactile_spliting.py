import copy

import numpy as np
import os
MAX_LEN = 64
MIN_LEN = 32

DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


class SplitDataDict:
    # dict-like的数据结构。其内核仍是整片的64*64数据，但在读取时会即时处理
    # 注意，使用apply_filter_for_each对各分片应用滤波器时，处理机制会较为特殊

    def __init__(self, full_data, range_mapping: dict):
        self.full_data = full_data  # 全阵列
        self.range_mapping = range_mapping
        self.unit_filter_objs = []

    # 重载四则运算

    def __add__(self, other):
        return SplitDataDict(self.full_data + other, self.range_mapping)

    def __sub__(self, other):
        return SplitDataDict(self.full_data - other, self.range_mapping)

    def __mul__(self, other):
        return SplitDataDict(self.full_data * other, self.range_mapping)

    def __truediv__(self, other):
        return SplitDataDict(self.full_data / other, self.range_mapping)

    def astype(self, dtype):
        return SplitDataDict(self.full_data.astype(dtype), self.range_mapping)

    @property
    def shape(self):
        return self.full_data.shape

    def __array__(self):
        return self.full_data

    def apply_filter(self, filter_obj: callable, **kwargs):
        self.full_data = filter_obj(self.full_data, **kwargs)

    def apply_filter_for_each(self, filters_obj: dict, **kwargs):
        self.unit_filter_objs.append(filters_obj, **kwargs)

    def __getitem__(self, idx):
        if idx in self.range_mapping.keys():
            info = self.range_mapping[idx]
            slicing = info[0]
            x_invert = info[1]
            y_invert = info[2]
            xy_swap = info[3]
            scale = info[4]
            power = info[5]
            data_this = ((np.maximum(self.full_data[slicing], 0.)) ** power) * scale

            if x_invert:
                data_this = data_this[::-1, :]
            if y_invert:
                data_this = data_this[:, ::-1]
            if xy_swap:
                data_this = data_this.T

            for filter_obj in self.unit_filter_objs:
                data_this = filter_obj[idx](data_this)
            return data_this
        else:
            raise KeyError(str(idx))

    def __setitem__(self, idx, data_this):
        if idx in self.range_mapping.keys():
            info = self.range_mapping[idx]
            slicing = info[0]
            x_invert = info[1]
            y_invert = info[2]
            xy_swap = info[3]
            scale = info[4]
            power = info[5]

            if xy_swap:
                data_this = data_this.T
            if x_invert:
                data_this = data_this[::-1, :]
            if y_invert:
                data_this = data_this[:, ::-1]

            self.full_data[slicing] = (data_this ** (power ** -1)) / scale

        else:
            raise KeyError(str(idx))

    def keys(self):
        return self.range_mapping.keys()

    def values(self):
        for k in self.keys():
            yield self[k]

    def items(self):
        for k in self.keys():
            yield k, self[k]

    def copy(self):
        ret = SplitDataDict(copy.deepcopy(self.full_data), self.range_mapping)
        ret.unit_filter_objs = copy.deepcopy(self.unit_filter_objs)
        return ret

    def __bool__(self):
        return True

    def __copy__(self):
        return self.copy()

    # 重载所有大小对比符号
    def __lt__(self, other):
        return self.full_data < other

    def __le__(self, other):
        return self.full_data <= other

    def __eq__(self, other):
        return self.full_data == other

    def __ne__(self, other):
        return self.full_data != other

    def __gt__(self, other):
        return self.full_data > other

    def __ge__(self, other):
        return self.full_data >= other


def get_split_driver_class(base_driver_class, config_mapping):

    class TactileDriverWithPreprocessing(base_driver_class):

        range_mapping = {int(k):
                             [(slice(v[0], v[0] + v[5]),
                               slice(v[1], v[1] + v[6])),
                              bool(v[2]), bool(v[3]), bool(v[4]),
                              float(v[7]),
                              float(v[8])]
                         for k, v in config_mapping['range_mapping'].items()}

        def __init__(self):
            super().__init__()

        def get_zeros(self, idx):
            # 直接返回全零的分片
            if idx in self.range_mapping.keys():
                info = self.range_mapping[idx]
                slicing = info[0]
                xy_swap = info[3]
                data_this = np.zeros((slicing[0].stop - slicing[0].start,
                                      slicing[1].stop - slicing[1].start))
                if xy_swap:
                    data_this = data_this.T
                return data_this
            else:
                raise KeyError(str(idx))

        def connect(self, port=None):
            flag = super().connect(port)
            return flag

        def disconnect(self):
            return super().disconnect()

        def get(self):
            data_fingers, t_last = None, None
            while True:
                data, t = super().get()
                if data is not None:
                    data_fingers = SplitDataDict(data, self.range_mapping)
                    t_last = t
                else:
                    break
            # 总是只返回最新的，但所有数据都必须过一遍预处理器
            return data_fingers, t_last

    return TactileDriverWithPreprocessing
