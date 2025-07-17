import warnings
import numpy as np
from backends.abstract_sensor_driver import AbstractSensorDriver
import json
from backends.multiple_can_backend import CanBackend
import os
from multiple_skins.tactile_spliting import SplitDataDict


class SeatSensorDriver(AbstractSensorDriver):

    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数。与采集卡有关
    SENSOR_SHAPE = (56, 16)
    range_mapping = {
        0: ((slice(0, 24), slice(0, 16)), False, False, False, 1.0, 1.0),
        1: ((slice(24, 40), slice(0, 16)), False, False, False, 1.0, 1.0),
        2: ((slice(40, 56), slice(0, 16)), False, False, False, 1.0, 1.0)
    }

    def __init__(self, time_tolerance=0.5):
        super(SeatSensorDriver, self).__init__()

        config_array_seat = json.load(open(os.path.join(os.path.dirname(__file__), '../config_files/config_array_24_16_seat.json'), 'rt'))
        config_array_back = json.load(open(os.path.join(os.path.dirname(__file__),'../config_files/config_array_16_back.json'), 'rt'))
        config_array_head = json.load(open(os.path.join(os.path.dirname(__file__),'../config_files/config_array_16_head.json'), 'rt'))
        self.indices = [0, 1, 2]
        sb = CanBackend({0: config_array_seat, 1: config_array_head, 2: config_array_back})
        self.time_tolerance = time_tolerance
        self.sensor_backend = sb

    @property
    def connected(self):
        return self.sensor_backend.active

    def connect(self, port):
        return self.sensor_backend.start(port)

    def disconnect(self):
        return self.sensor_backend.stop()

    def get(self):
        if self.sensor_backend.err_queue:
            raise self.sensor_backend.err_queue.popleft()
        result_dict = {}
        process_flag = True
        ts = {}
        for index in self.indices:
            if not self.sensor_backend.is_ready(index):
                process_flag = False
                break
        if process_flag:
            success_flag = True
            for index in self.indices:
                data, t = self.sensor_backend.get(index)
                result_dict[index] = (data, t)
                ts[index] = t
                if data is None:
                    success_flag = False
            # 附加一段代码：如果ts之间差异过大，对较小的t继续取数，以提高时间一致性
            max_ts = np.max(list(ts.values()))
            for index in self.indices:
                while max_ts - ts[index] > self.time_tolerance:
                    data, t = self.sensor_backend.get(index)
                    if data is not None:
                        result_dict[index] = (data, t)
                        ts[index] = t
                        print(f"跳过1条通道{index}的数据")
                    else:
                        break
            if success_flag:
                # print(f"时间不一致性：{np.max(list(ts.values())) - np.min(list(ts.values()))}")
                return self.__make_split_data_dict(result_dict), np.mean(list(ts.values()))
            else:
                warnings.warn("读取异常")
                return None, None
        else:
            return None, None

    # 适配SplitDataDict

    def get_zeros(self, idx):
        if idx in self.indices:
            return np.zeros(self.sensor_backend.index_to_decoder[idx].sensor_shape, dtype=self.DATA_TYPE)
        else:
            raise IndexError

    def __make_split_data_dict(self, data):
        # 将数据转换为SplitDataDict格式
        virtual_full_data = np.zeros(self.SENSOR_SHAPE, dtype=self.DATA_TYPE)
        data_dict = SplitDataDict(virtual_full_data, self.range_mapping)
        for index, (data_array, _) in data.items():
            if index in self.range_mapping:
                data_dict[index] = data_array
            else:
                raise KeyError(f"Index {index} not found in range_mapping")
        return data_dict


if __name__ == '__main__':
    #  测试SeatSensorDriver
    driver = SeatSensorDriver()
    if driver.connect(None):
        print("Connected to CAN device.")
        last_timestamp = None
        while True:
            data, timestamp = driver.get()
            if data is not None:
                for index in range(3):
                    print("Data received:", np.sum(data[index]))
                # print("Timestamp:", timestamp)
                if last_timestamp is not None:
                    # print("Time difference:", timestamp - last_timestamp)
                    pass
                last_timestamp = timestamp
    else:
        print("Failed to connect to CAN device.")

