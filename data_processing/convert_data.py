
import sqlite3
import warnings

import pandas as pd
import os

import numpy as np
import json
import time


def extract_data(path):
    if os.path.exists(path):
        assert path.endswith('.db')
        connection = sqlite3.connect(path)
        data = pd.read_sql(sql='SELECT * FROM data', con=connection)
        data_time = pd.DataFrame(data[['time', 'time_after_begin']])
        to_be_concatenated = [data_time]
        for c in data.columns:
            if c.startswith('data_row_'):
                i = int(c.split('_')[-1])
                data_row = np.vectorize(json.loads, otypes=[object])(data[c].values)
                print(data_row.shape)
                if not bool(data_row):
                    print('文件为空')
                    return None
                data_row = np.array([_ for _ in data_row])
                to_be_concatenated.append(pd.DataFrame(data_row,
                                                       columns=[f'data_row_{i}_col_{j}'
                                                                for j in range(data_row.shape[1])]))
            elif c.startswith('data_region_'):
                i = int(c.split('_')[-1])
                j = int(c.split('_')[-3])
                data_row = np.vectorize(json.loads, otypes=[object])(data[c].values)
                data_row = np.array([_ for _ in data_row])
                to_be_concatenated.append(pd.DataFrame(data_row,
                                                         columns=[f'data_region_{j}_row_{i}_col_{k}'
                                                                  for k in range(data_row.shape[1])]))
            elif c.startswith('config_') or c.startswith('feature_') or c.startswith('label_'):
                to_be_concatenated.append(pd.DataFrame(data[c].values.reshape((-1, 1)), columns=[c]))
                pass
        data_by_col = pd.concat(to_be_concatenated, axis=1)
        connection.close()
        return data_by_col
    else:
        print('文件不存在')
        return None

def dataframe_to_numpy(data_by_col, with_time=False):
    """
    将DataFrame转换为numpy数组
    :param data_by_col: DataFrame
    :return: numpy数组
    """
    if data_by_col is not None:
        # 只保留data_row_开头的列
        data_row_cols = [col for col in data_by_col.columns if col.startswith('data_row_')]
        # 形如data_row_0_col_0, data_row_0_col_1, ..., data_row_1_col_0, ...，识别行列数并折叠
        row_count = len(pd.unique([col.split('_')[2] for col in data_row_cols]))
        col_count = len(pd.unique([col.split('_')[4] for col in data_row_cols]))
        data_array = data_by_col[data_row_cols].values.reshape((-1, row_count, col_count))
        if with_time:
            time_data = data_by_col[['time_after_begin']].values.ravel()
            return data_array, time_data
        else:
            return data_array
    else:
        if with_time:
            return None, None
        else:
            return None

def convert_db_to_csv(path):
    data_by_col = extract_data(path)
    if data_by_col is not None:
        save_path = path[:-3] + '.csv'
        data_by_col.to_csv(save_path, index=False)
        print('导出完成')
        try:
            os.startfile(save_path)
        except Exception as e:
            print(e)
    else:
        print('文件不存在')


class ReplayDataSource:
    def __init__(self):
        self.output_file = None
        self.path_db = None
        self.cursor = None
        #
        self.data = None
        self.begin_time = None
        self.speed_rate = 10.

    def connect(self, path):
        if os.path.exists(path):
            assert path.endswith('.db')
            connection = sqlite3.connect(path)
            # self.data = pd.read_sql(sql='SELECT * FROM data', con=connection)
            self.data = pd.read_sql(sql='SELECT * FROM data LIMIT 16', con=connection)
            warnings.warn('只读取了前16行')
            self.begin_time = self.data['time'].values[0]
        else:
            print('文件不存在')
            return None

    def reset(self, time_offset=0.):
        assert time_offset >= 0.
        self.begin_time = time.time() - time_offset / self.speed_rate

    def get_data(self):
        # 取时间小于self.begin_time的最后一组
        if self.data is not None:
            time_now = time.time()
            frame_dict = {}
            for i_driver in pd.unique(self.data['i_driver']):
                data = self.data[self.data['i_driver'] == i_driver]
                index = int((data['time_after_begin'].searchsorted(
                    time_now - self.begin_time + data['time_after_begin'].iloc[0], side='right')) * self.speed_rate)
                print(index)
                data = data.iloc[:index]
                # data = data[data['time_after_begin'] - data['time_after_begin'].iloc[0] < time_now - self.begin_time]
                if data.shape[0] > 0:
                    data = data.iloc[-1]
                    frame = np.ndarray((data.shape[0] - 3, data.shape[0] - 3))
                    for row_index in range(data.shape[0] - 3):
                        frame[row_index, :] = np.array(json.loads(data[f'data_row_{row_index}']))
                        frame_dict.update({int(i_driver): frame})
                else:
                    return None
            return frame_dict
        else:
            return None


if __name__ == '__main__':
    pass


