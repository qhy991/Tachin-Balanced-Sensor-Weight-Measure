# 做存储数据，便于对比
from abstract_sensor_driver import AbstractSensorDriver
import pickle
import time
import numpy as np


class FakeSensorDriver(AbstractSensorDriver):

    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        super(FakeSensorDriver, self).__init__()
        loaded = pickle.load(open('./resources/stored_data.dta', 'rb'))
        self.data = loaded['data']
        self.idx = 0

    def connect(self, *args, **kwargs):
        return True

    def disconnect(self):
        return True

    def get(self):
        value, t = self.get_transformed()
        voltage = 10 ** -(4 - value / 255 * 2.5) * (32768. * 25. / 5.)
        return voltage, t

    def get_transformed(self):
        ret = self.data[self.idx, :, :]
        self.idx += 1
        if self.idx == self.data.shape[0]:
            self.idx = 0
        return ret, time.time()


if __name__ == '__main__':
    if False:
        bd = BuildDataset()
        while True:
            bd.trigger()
    else:
        sd = FakeSensorDriver()
        while True:
            ret, t = sd.get()
            pass
