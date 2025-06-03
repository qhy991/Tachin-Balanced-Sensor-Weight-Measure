# 打开由convert_data.convert_db_to_csv转换得到的csv文件

from PyQt5 import QtCore, QtWidgets, QtGui
import pyqtgraph
import sqlite3
import os
import pandas as pd
import numpy as np
from data.data_viewer_OBSELETE.qt.ui_data_viewer import Ui_MainWindow
from config import config
import json
import warnings

STANDARD_PEN = pyqtgraph.mkPen('k')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('k', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}

LABEL_RESISTANCE = 'Resistance / kΩ'
LABEL_TIME = 'Time / sec'

SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数
warnings.warn("仅适用于USB协议导出的数据")


def scale_from_ad(value_ad):
    return value_ad * SCALE


def log(v):
    return np.log(np.maximum(v, 1e-6)) / np.log(10)

def pow(v):
    return 10 ** v

def load_from_json(_):
    return np.array(json.loads(_))


class DataViewer(QtWidgets.QMainWindow, Ui_MainWindow):

    COLORS = [[15, 15, 15],
              [48, 18, 59],
              [71, 118, 238],
              [27, 208, 213],
              [97, 252, 108],
              [210, 233, 53],
              [254, 155, 45],
              [218, 57, 7],
              [122, 4, 3]]

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.button_load.clicked.connect(self.open_file)
        self.button_export.clicked.connect(self.export_csv)
        self.image = self.create_an_image(self.fig_image)
        self.log_y_lim = config['y_lim']
        self.selected_area = (slice(0, 1), slice(0, 1))
        self.line = self.create_a_line(self.fig_line)
        self.selected_time_progress = 0.5
        self.loaded_time = None
        self.loaded_data = None

    def create_an_image(self, fig_widget: pyqtgraph.GraphicsLayoutWidget):
        fig_widget.setBackground(0.95)
        plot = pyqtgraph.ImageView()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(plot, 0, 0)
        fig_widget.setLayout(layout)
        plot.adjustSize()
        plot.ui.histogram.hide()
        plot.ui.menuBtn.hide()
        plot.ui.roiBtn.hide()
        #
        colors = self.COLORS
        pos = (0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1)
        cmap = pyqtgraph.ColorMap(pos=[_ for _ in pos], color=colors)
        plot.setColorMap(cmap)
        vb: pyqtgraph.ViewBox = plot.getImageItem().getViewBox()
        vb.setMouseEnabled(x=False, y=False)
        vb.setBackgroundColor(pyqtgraph.mkColor(0.95))

        roi = pyqtgraph.RectROI([0, 0], [1, 1], pen='r')
        plot.addItem(roi)
        roi.sigRegionChanged.connect(lambda: self.update_selection(roi))
        return plot

    def create_a_line(self, fig_widget: pyqtgraph.GraphicsLayoutWidget):
        ax: pyqtgraph.PlotItem = fig_widget.addPlot()
        ax.setLabel(axis='left', text=LABEL_RESISTANCE)
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text=LABEL_TIME)
        # ax.getAxis('left').tickStrings = lambda values, scale, spacing:\
        #     [(f'{_ ** -1: .1f}' if _ > 0. else 'INF') for _ in values]
        ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                [f'{10 ** (-_): .1f}' for _ in values]
        line: pyqtgraph.PlotDataItem = ax.plot([], [], **LINE_STYLE)
        fig_widget.setBackground('w')
        ax.getViewBox().setBackgroundColor([255, 255, 255])
        ax.getAxis('bottom').setPen(STANDARD_PEN)
        ax.getAxis('left').setPen(STANDARD_PEN)
        ax.getAxis('bottom').setTextPen(STANDARD_PEN)
        ax.getAxis('left').setTextPen(STANDARD_PEN)
        ax.getViewBox().setMouseEnabled(x=True, y=True)
        ax.hideButtons()
        line.get_axis = lambda: ax
        # 图例绑定
        ax.addLegend()
        return line

    def open_file(self):
        options = QtWidgets.QFileDialog.Options()
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open File", "", "CSV Files (*.csv);;SQLite DB Files (*.db)", options=options)
        if file_name:
            if file_name.endswith('.csv'):
                all_time, all_data = self.read_csv(file_name)
            elif file_name.endswith('.db'):
                all_time, all_data = self.read_db(file_name)
            else:
                raise Exception("不支持的文件格式")
            self.loaded_time = all_time
            self.loaded_data = all_data
            self.plot_data()

    def read_csv(self, path):
        if os.path.exists(path):
            data_loaded = pd.read_csv(path)
            time_min = data_loaded['time_after_begin'].min()
            all_time = (data_loaded['time_after_begin'] - time_min).values
            all_data = np.array([[data_loaded[f'data_row_{i}_{j}'] for j in range(64)] for i in range(64)])\
                .transpose((2, 0, 1))
            return all_time, all_data
        else:
            raise FileNotFoundError('文件不存在')

    def read_db(self, path):
        if os.path.exists(path):
            connection = sqlite3.connect(path)
            data_loaded = pd.read_sql(sql='SELECT * FROM data', con=connection)
            connection.close()
            time_min = data_loaded['time_after_begin'].min()
            all_time = (data_loaded['time_after_begin'] - time_min).values
            all_data = np.array(
                [np.array(np.vectorize(load_from_json, otypes=[object])(data_loaded.iloc[i_row, 2:].values).tolist())
                 for i_row in range(data_loaded.shape[0])])
            return all_time, all_data
        else:
            raise FileNotFoundError('文件不存在')

    def export_csv(self):
        options = QtWidgets.QFileDialog.Options()
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save File", "", "CSV Files (*.csv)", options=options)
        if file_name:
            self.export(file_name)

    def plot_data(self):
        self.image.clear()
        if self.loaded_data is None or self.loaded_time is None:
            return
        self.image.setImage(log(self.loaded_data[int(self.loaded_data.shape[0] * self.selected_time_progress), :, :]),
                            levels=(self.log_y_lim[0], self.log_y_lim[1]))
        data_chosen = self.loaded_data[:, self.selected_area[0], self.selected_area[1]]
        self.line.setData(self.loaded_time, log(scale_from_ad(data_chosen.sum(axis=(1, 2)))),
                          label=f"选择了{data_chosen.shape[1]} * {data_chosen.shape[2]}的区域",
                          **LINE_STYLE)

    def select_area(self, x_start, x_stop, y_start, y_stop):
        self.selected_area = (slice(y_start, y_stop), slice(x_start, x_stop))
        self.plot_data()

    def update_selection(self, roi):
        pos = roi.pos()
        size = roi.size()
        x_start, y_start = round(pos.x()), round(pos.y())
        x_stop, y_stop = round(pos.x() + size.x()), round(pos.y() + size.y())
        self.select_area(y_start, y_stop, x_start, x_stop)

    def export(self, path):
        pass
        time_export = self.loaded_time
        data_chosen = self.loaded_data[:, self.selected_area[0], self.selected_area[1]]
        data_export = scale_from_ad(data_chosen.sum(axis=(1, 2)))
        full_export = np.vstack([time_export, data_export]).transpose()
        for i in range(data_chosen.shape[1]):
            for j in range(data_chosen.shape[2]):
                full_export = np.hstack([full_export, scale_from_ad(data_chosen[:, i, j]).reshape((-1, 1))])
        np.savetxt(path, full_export, fmt='%.5f', delimiter=',', comments='',
                   header='time, resistance, ' + ', '.join([f'resistance_{i}_{j}'
                                                            for i in list(range(self.loaded_data.shape[0]))[self.selected_area[0]]
                                                            for j in list(range(self.loaded_data.shape[1]))[self.selected_area[1]]]))
        # 如可能，打开它
        try:
            os.system(f'start {path}')
        except Exception as e:
            print(e)
    pass


def start():
    import sys

    app = QtWidgets.QApplication(sys.argv)
    window = DataViewer()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    start()