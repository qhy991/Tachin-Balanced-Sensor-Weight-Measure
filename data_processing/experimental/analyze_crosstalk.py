
from data_processing.convert_data import extract_data, dataframe_to_numpy
import matplotlib.pyplot as plt
import numpy as np


def analyze_crosstalk(path):
    """
    分析数据中的串扰情况
    :param path: 数据库文件路径
    :return: None
    """
    data = dataframe_to_numpy(extract_data(path))
    shape = data.shape[1:]
    if data is not None:
        THRESHOLD = 5
        mask = np.max(data.reshape((data.shape[0], -1)), axis=1) >= THRESHOLD
        data = data[mask, ...]
        data_flatten = data.reshape(data.shape[0], -1)
        # 计算相关系数矩阵
        correlation_matrix = np.corrcoef(data_flatten, rowvar=False) - np.eye(data_flatten.shape[1])
        correlation_matrix = correlation_matrix.reshape(list(shape) + list(shape))
        # 列出高相关性的点
        high_correlation_indices = np.argwhere(correlation_matrix > 0.5)
        if high_correlation_indices.size > 0:
            print('高相关性点：')
            for i_row_0, i_col_0, i_row_1, i_col_1 in high_correlation_indices:
                if i_row_0 in [56, 57, 58] and i_col_0 == 48:
                    print(f"({i_row_0}, {i_col_0}) 和 ({i_row_1}, {i_col_1}) 相关系数为 {correlation_matrix[i_row_0, i_col_0, i_row_1, i_col_1]:.2f}")



    else:
        print('文件不存在')

if __name__ == "__main__":
    import sys
    import os
    import matplotlib.pyplot as plt
    import warnings

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../output/crosstalk_0.db')

    analyze_crosstalk(path)



