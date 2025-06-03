from data_processing.preprocessing import Filter
import numpy as np
import os, pickle, atexit
import matplotlib.pyplot as plt

class StatisticalFilter(Filter):

    def __init__(self, sensor_class, name):
        super().__init__(sensor_class)
        self.name = name
        self.dataset_x = []
        self.dataset_y = []
        self._trained = False
        try:
            self.load()
        except FileNotFoundError:
            print(f"StatisticalFilter: {self.name} not found, creating a new one.")

    @property
    def trained(self):
        return self._trained

    def collect(self, x, y=None):
        self.dataset_x.append(x)
        self.dataset_y.append(y)

    def clear(self):
        self.dataset_x = []
        self.dataset_y = []
        self._trained = False

    def train(self, *args, **kwargs):
        pass

    def serialized(self):
        return {
            'name': self.name,
            'dataset_x': self.dataset_x,
            'dataset_y': self.dataset_y,
        }

    def save(self):
        print("准备保存...")
        try:
            if self.dataset_x:
                pickle.dump(self.serialized(), open(os.path.join(os.path.dirname(__file__), f'dumped/{self.name}.pkl'), 'wb'))
                print("保存成功")
            else:
                print("未收集数据，不保存")
        except Exception as e:
            print(f"保存失败: {e}")

    def remove(self):
        self.clear()
        if os.path.exists(os.path.join(os.path.dirname(__file__), f'dumped/{self.name}.pkl')):
            os.remove(os.path.join(os.path.dirname(__file__), f'dumped/{self.name}.pkl'))

    def load(self):
        loaded = pickle.load(open(os.path.join(os.path.dirname(__file__), f'dumped/{self.name}.pkl'), 'rb'))
        # 确认类名一致
        assert loaded['name'] == self.name, f"Name mismatch: {loaded['name']} != {self.name}"
        self.dataset_x = loaded['dataset_x']
        self.dataset_y = loaded['dataset_y']


class StatisticalRevisionForEach(StatisticalFilter):

    def __init__(self, sensor_class, name, rate=0.5):
        self.mean_x = None
        self.std_x = None
        self.overall_mean = None
        self.rate = rate
        super().__init__(sensor_class, name)
        atexit.register(self.save)

    def filter(self, x):
        if not self._trained:
            self.collect(x)
        if self._trained:
            x = x * self.overall_mean / (self.mean_x * self.rate + self.overall_mean * (1. - self.rate))
        return x

    def train(self):
        if self.dataset_x:
            self.mean_x = np.mean(self.dataset_x, axis=0)
            self.std_x = np.std(self.dataset_x, axis=0)
            self.overall_mean = np.mean(self.mean_x)
            self._trained = True
            print("适用模型")
        else:
            pass

    def load(self):
        super().load()
        self.train()


class WeightRevisionForEach(StatisticalFilter):

    def __init__(self, sensor_class, name):
        self.mean_x = None
        self.std_x = None
        self.transfer_matrix = None
        super().__init__(sensor_class, name)
        atexit.register(self.save)

    def filter(self, x):
        if not self._trained:
            self.collect(x)
        if self._trained:
            x = self._apply_transfer_matrix(x, self.transfer_matrix)
        return x

    def train(self):
        if self.dataset_x:
            self.mean_x = np.mean(self.dataset_x, axis=0)
            self.std_x = np.std(self.dataset_x, axis=0)
            self.transfer_matrix = self._calculate_transfer_matrix(self.mean_x)
            self._trained = True
            print("适用模型")
        else:
            pass

    def load(self):
        super().load()
        self.train()

    @staticmethod
    def _calculate_transfer_matrix(mean: np.ndarray):
        size = mean.shape[0] * mean.shape[1]
        transfer_matrix = np.eye(size)
        index_matrix = np.arange(size).reshape(mean.shape)
        overall_mean = np.mean(mean)
        assert overall_mean > 0
        mean = mean * overall_mean ** -1
        for idx_row in range(mean.shape[0]):
            for idx_col in range(mean.shape[1]):
                if mean[idx_row, idx_col] >= 1.:
                    # 大于基准，降低
                    transfer_matrix[index_matrix[idx_row, idx_col], index_matrix[idx_row, idx_col]] = mean[idx_row, idx_col] ** -1
                else:
                    # 低于基准，所有高于自身的点按比例分配
                    kernel_func = lambda x_diff, y_diff: np.exp(-(x_diff ** 2 + y_diff ** 2))
                    kernel = np.zeros_like(mean)
                    for i in range(mean.shape[0]):
                        for j in range(mean.shape[1]):
                            x_diff = idx_row - i
                            y_diff = idx_col - j
                            kernel[i, j] = kernel_func(x_diff, y_diff)
                    upstreams = np.maximum((mean - mean[idx_row, idx_col]) * kernel, 0)
                    assert upstreams.sum() > 0
                    upstreams = upstreams / upstreams.sum() * (1. - mean[idx_row, idx_col])
                    transfer_matrix[index_matrix[idx_row, idx_col], :] = upstreams.flatten()
                    transfer_matrix[index_matrix[idx_row, idx_col], index_matrix[idx_row, idx_col]] = 1.
        transfer_matrix = transfer_matrix / transfer_matrix.sum(axis=0, keepdims=True) / (0.5 + mean.reshape((1, -1)) * 0.5)
        return transfer_matrix

    @staticmethod
    def _apply_transfer_matrix(data, transfer_matrix):
        return (data.flatten() @ transfer_matrix.T).reshape(data.shape)


if __name__ == '__main__':
    testing_matrix = np.array([[4, 4, 4], [4, 2, 4], [4, 6, 4]])
    testing_data = np.array([[1, 2, 3], [4, 2.5, 6], [7, 12, 9]])
    transfer_matrix = WeightRevisionForEach._calculate_transfer_matrix(testing_matrix)
    transfered_data = WeightRevisionForEach._apply_transfer_matrix(testing_data, transfer_matrix)
    pass




