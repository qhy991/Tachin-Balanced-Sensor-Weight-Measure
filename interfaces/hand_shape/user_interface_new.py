"""
手形界面
"""

import threading

from PyQt5 import QtCore, QtWidgets, QtGui
from interfaces.hand_shape.layout.layout import Ui_Form
import pyqtgraph
import sys
import time
import os
import traceback
import numpy as np
from data_handler.data_handler import DataHandler
from PIL import Image
from config import config, save_config, config_mapping
from collections import deque
from usb.core import USBError
from multiple_skins.tactile_spliting import TactileDriverWithPreprocessing
from data_handler.interpolation import Interpolation
from data_handler.preprocessing import MedianFilter
from utils.performance_monitor import Ticker

cmap = pyqtgraph.ColorMap(np.linspace(0, 1, 17), (np.array(config_mapping['color_map']) * 255).astype(int))
legend_color = lambda i: pyqtgraph.intColor(i, 16 * 1.5, maxValue=127 + 64)

STANDARD_PEN = pyqtgraph.mkPen('k')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
pass

RESOURCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
pixel_mapping = config_mapping['pixel_mapping']
range_mapping = config_mapping['range_mapping']
is_left_hand = config_mapping['is_left_hand']

#
STANDARD_PEN = pyqtgraph.mkPen('k')
MINIMUM_Y_LIM = 0
MAXIMUM_Y_LIM = 4
TRIGGER_TIME_RECORD_LENGTH = 10


class HandPlotManager:

    def __init__(self, fig_widget_2d: pyqtgraph.GraphicsLayoutWidget,
                 fig_widget_1d: pyqtgraph.GraphicsLayoutWidget,
                 data_handler: DataHandler,
                 downsample=1):
        self.img_view = pyqtgraph.ImageView()
        self.img_view.ui.histogram.hide()
        self.img_view.ui.menuBtn.hide()
        self.img_view.ui.roiBtn.hide()
        fig_widget_2d.setBackground(0.95)
        layout = QtWidgets.QGridLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.img_view, 0, 0)
        fig_widget_2d.setLayout(layout)
        self.img_view.getView().setBackgroundColor(0.95)
        self.img_view.getView().setMouseEnabled(False, False)
        self.img_view.getView().setMenuEnabled(False)
        self.img_view.adjustSize()
        #
        self.y_lim_log = (
            -np.log(config_mapping['resistance_range'][1]) / np.log(10),
            -np.log(config_mapping['resistance_range'][0]) / np.log(10))
        #
        self.dd = data_handler
        # 加载底图
        self.downsample = downsample
        self.base_image = Image.open(os.path.join(RESOURCE_FOLDER, 'hand.png')).convert('RGBA')
        self.base_image = self.base_image.resize((self.base_image.size[0] // self.downsample,
                                                  self.base_image.size[1] // self.downsample),
                                                 resample=Image.BILINEAR)
        self.processing_image = self.base_image.copy()
        self.current_image = np.array(self.processing_image).transpose((1, 0, 2))
        img = np.array(self.current_image).transpose((1, 0, 2))
        if is_left_hand:
            img = img[::-1, :, :]
        self.img_view.setImage(img, autoRange=True)
        self.img_view.autoRange()
        # mapping_onto_image
        rects = {
            int(k): [(pixel_mapping[k][0] // self.downsample, pixel_mapping[k][1] // self.downsample), (pixel_mapping[k][2] // self.downsample, pixel_mapping[k][3] // self.downsample),
                     True,
                     self.make_mask((range_mapping[k][6], range_mapping[k][5])
                                    if range_mapping[k][4]
                                    else (range_mapping[k][5], range_mapping[k][6]),
                                    1.)]
            for k in range_mapping.keys()
        }
        self.proj_func = self.make_projection_function(rects)
        # 曲线图
        ax: pyqtgraph.PlotItem = fig_widget_1d.addPlot()
        ax.setLabel(axis='left', text='电阻（调和平均） (kΩ)')
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text='时间 (s)')
        ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
            [f'{10 ** (-_): .1f}' for _ in values]
        ax.getViewBox().setYRange(*self.y_lim_log)
        fig_widget_1d.setBackground('w')
        ax.getViewBox().setBackgroundColor([255, 255, 255])
        ax.getAxis('bottom').setPen(STANDARD_PEN)
        ax.getAxis('left').setPen(STANDARD_PEN)
        ax.getAxis('bottom').setTextPen(STANDARD_PEN)
        ax.getAxis('left').setTextPen(STANDARD_PEN)
        ax.getViewBox().setMouseEnabled(x=False, y=False)
        ax.getViewBox().setMenuEnabled(False)
        ax.hideButtons()
        ax.addLegend()
        self.lines = {int(idx): ax.plot(pen=pyqtgraph.mkPen(legend_color(idx), width=2),
                                        name=config_mapping['names'][idx])
                      for idx in range_mapping.keys()}
        # 存储
        self.filters = {int(idx): MedianFilter({'SENSOR_SHAPE': (1, 1), 'DATA_TYPE': float}, 2)
                        for idx in range_mapping.keys()}
        max_len = self.dd.max_len
        self.region_mean = {int(idx): deque(maxlen=max_len) for idx in range_mapping.keys()}
        self.time = deque(maxlen=max_len)
        #
        self.lock = threading.Lock()
        #
        threading.Thread(target=self.process_forever, daemon=True).start()

    @staticmethod
    def make_mask(shape, scale=1.):
        x_coord = np.abs(np.arange(shape[0]) - shape[0] // 2 + 0.5)
        y_coord = np.abs(np.arange(shape[1]) - shape[1] // 2 + 0.5)
        dist_sq = ((x_coord.reshape(-1, 1)) / shape[0] * 2) ** 3 + ((y_coord.reshape(1, -1)) / shape[1] * 2) ** 3
        mask = np.maximum(1. - dist_sq ** 3, 0)
        mask = np.ones_like(mask)  # 暂时取消
        mask *= scale
        return mask

    def reset_image(self):
        self.processing_image = self.base_image.copy()

    # def make_projection_functio_old(self, rect):
    #     """依据rect预计算投影函数"""
    #     # 计算边向量
    #     base_point = rect[0]
    #     x_delta = (rect[1][0] - rect[0][0], rect[1][1] - rect[0][1])
    #     y_rate = rect[-1].shape[1] / rect[-1].shape[0]
    #     y_delta = (-x_delta[1] * y_rate,
    #                x_delta[0] * y_rate)
    #     if not rect[2]:
    #         y_delta = (-y_delta[0], -y_delta[1])
    #     center = (round(base_point[0] + 0.5 * x_delta[0] + 0.5 * y_delta[0]),
    #               round(base_point[1] + 0.5 * x_delta[1] + 0.5 * y_delta[1]))
    #     angle = -np.arctan2(rect[1][1] - rect[0][1], rect[1][0] - rect[0][0])
    #     x_length = np.sqrt((rect[1][0] - rect[0][0]) ** 2 + (rect[1][1] - rect[0][1]) ** 2)
    #     new_shape = (int(x_length), int(x_length * y_rate))
    #     # 思路要改变。预计算映射
    #
    #     def projection_function(data: np.ndarray):
    #         # data = data * rect[3]
    #         data = Interpolation(2, 0.5, data.shape).smooth(data * rect[3])
    #         data = np.log(np.maximum(data, 1e-6)) / np.log(10)
    #         data = np.clip((data - self.y_lim_log[0]) / (self.y_lim_log[1] - self.y_lim_log[0]), 0., 1.)
    #         img_original = Image.fromarray((cmap.map(data.T, mode=float) * 255.).astype(np.uint8),
    #                                        mode='RGBA')
    #         img_scaled = img_original.resize(new_shape, resample=Image.BILINEAR)
    #         img_rotated = img_scaled.rotate(angle * 180 / np.pi, resample=Image.BILINEAR,
    #                                         expand=True, fillcolor=(0, 0, 0, 0))
    #         self.processing_image.paste(img_rotated,
    #                                     (center[0] - img_rotated.width // 2, center[1] - img_rotated.height // 2),
    #                                     mask=img_rotated.split()[-1])
    #
    #     return projection_function

    def make_projection_function(self, rects):

        idx_to_transformed_info = {idx: {} for idx in rects.keys()}
        for idx_region in rects.keys():
            rect = rects[idx_region]
            base_point = rect[0]
            x_delta = (rect[1][0] - rect[0][0], rect[1][1] - rect[0][1])
            y_rate = rect[-1].shape[1] / rect[-1].shape[0]
            y_delta = (-x_delta[1] * y_rate,
                       x_delta[0] * y_rate)
            if not rect[2]:
                y_delta = (-y_delta[0], -y_delta[1])
            center = (round(base_point[0] + 0.5 * x_delta[0] + 0.5 * y_delta[0]),
                      round(base_point[1] + 0.5 * x_delta[1] + 0.5 * y_delta[1]))
            angle = -np.arctan2(rect[1][1] - rect[0][1], rect[1][0] - rect[0][0])
            x_length = np.sqrt((rect[1][0] - rect[0][0]) ** 2 + (rect[1][1] - rect[0][1]) ** 2)
            new_shape = (int(x_length), int(x_length * y_rate))
            idx_to_transformed_info[idx_region] = {'center': center, 'angle': angle, 'new_shape': new_shape}

        # 目标：将整个计算矩阵化
        def find_response_of_point(idx_region, idx_row, idx_col):
            unit_data = np.zeros(shape=rects[idx_region][3].shape, dtype=float)
            if idx_row >= 0 and idx_col >= 0:
                unit_data[idx_row, idx_col] = 1.
            data = unit_data
            data = Interpolation(2, 0.5, data.shape).smooth(data)
            img_original = Image.fromarray((data.T * 255.).astype(np.uint8))  # 灰度
            img_scaled = img_original.resize(idx_to_transformed_info[idx_region]['new_shape'], resample=Image.BILINEAR)
            img_alpha = Image.fromarray(np.full(img_scaled.size, dtype=np.uint8, fill_value=255).T, mode='L')
            img_scaled.putalpha(img_alpha)
            img_rotated = img_scaled.rotate(idx_to_transformed_info[idx_region]['angle'] * 180 / np.pi, resample=Image.BILINEAR,
                                            expand=True)
            return img_rotated

        for idx_region in rects.keys():
            transform_matrix = np.zeros(shape=(rects[idx_region][3].shape[0] * rects[idx_region][3].shape[1],
                                               0),
                                   dtype=float)
            img_zero = find_response_of_point(idx_region, -1, -1)
            for idx_row in range(rects[idx_region][3].shape[0]):
                for idx_col in range(rects[idx_region][3].shape[1]):
                    img = find_response_of_point(idx_region, idx_row, idx_col)
                    if transform_matrix.shape[1] == 0:
                        transform_matrix = np.zeros(
                            shape=(rects[idx_region][3].shape[0] * rects[idx_region][3].shape[1],
                                   img.size[0] * img.size[1]),
                            dtype=float)
                    transform_matrix[idx_row * rects[idx_region][3].shape[1] + idx_col, :]\
                        = (np.array(img) - np.array(img_zero))[:, :, 0].ravel()

            idx_to_transformed_info[idx_region]['transform_matrix'] = transform_matrix
            idx_to_transformed_info[idx_region]['img_zero'] = np.array(img_zero)[:, :, 0]
            idx_to_transformed_info[idx_region]['rotated_shape'] = (img.size[1], img.size[0])
            idx_to_transformed_info[idx_region]['alpha'] = img.split()[1]

        def projection_function(data_dict_like):
            for idx_region, data_region in data_dict_like.items():
                data_in_lim = np.log(np.maximum(data_region, 1e-6)) / np.log(10)
                data_in_lim = np.clip((data_in_lim - self.y_lim_log[0]) / (self.y_lim_log[1] - self.y_lim_log[0]), 0., 1.)
                transformed = np.dot(data_in_lim.ravel(),
                                     idx_to_transformed_info[idx_region]['transform_matrix'])\
                    .reshape(idx_to_transformed_info[idx_region]['rotated_shape']) + idx_to_transformed_info[idx_region]['img_zero']
                img_transformed = Image.fromarray((cmap.map(transformed / 255, mode='float') * 255).astype(np.uint8), mode='RGBA')
                self.processing_image.paste(img_transformed,
                                            (idx_to_transformed_info[idx_region]['center'][0]
                                             - idx_to_transformed_info[idx_region]['rotated_shape'][0] // 2,
                                             idx_to_transformed_info[idx_region]['center'][1]
                                             - idx_to_transformed_info[idx_region]['rotated_shape'][1] // 2),
                                            mask=idx_to_transformed_info[idx_region]['alpha'])
                pass
        return projection_function

    def process_forever(self):
        ticker = Ticker()
        ticker.tic()
        while True:
            # ticker.toc("未知时间")
            self.process_image()
            ticker.toc("绘图时间")
            time.sleep(0.001)

    def process_image(self):
        if self.dd.value:
            self.dd.lock.acquire()
            data_fingers = self.dd.value.popleft()  # 唯一的数据流入位置
            time_now = self.dd.time.popleft()
            self.dd.lock.release()
            self.lock.acquire()
            self.reset_image()

            self.proj_func(data_fingers)
            for idx, data in data_fingers.items():
                mean_value = np.mean(data)
                self.region_mean[idx].append(np.log(np.maximum(mean_value, 1e-6)) / np.log(10.))
            self.lock.release()
            self.time.append(time_now)
            self.processing_image.putalpha(self.base_image.split()[-1])
            img = np.array(self.processing_image).transpose((1, 0, 2))
            self.current_image = img[::-1, :, :] if is_left_hand else img
            # 在self.lines_view上绘制每个分区的均值

    def plot(self):
        ticker = Ticker()
        ticker.tic()
        if self.current_image is not None:
            self.lock.acquire()
            # self.img_view.setImage(self.current_image, autoRange=True)
            self.img_view.setImage(self.current_image)
            self.current_image = None
            ticker.toc("更新阵列图")
            for idx, line in self.lines.items():
                line.setData(self.time, self.region_mean[idx])

            self.lock.release()


class Window(QtWidgets.QWidget, Ui_Form):

    TRIGGER_TIME = config.get("trigger_time")

    COLORS = config_mapping.get("color_map")

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self.catch_exceptions
        #
        self.data_handler = DataHandler(TactileDriverWithPreprocessing, max_len=16)
        self.is_running = False
        #
        self.hand_plot_manager = HandPlotManager(fig_widget_2d=self.fig_image,
                                                 fig_widget_1d=self.fig_lines,
                                                 data_handler=self.data_handler,
                                                 downsample=2)
        self.pre_initialize()
        #
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        #
        self.hist_trigger = deque(maxlen=TRIGGER_TIME_RECORD_LENGTH)
        #
        self.real_exit = False
        #

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)

    def catch_exceptions(self, ty, value, tb):
        traceback_format = traceback.format_exception(ty, value, tb)
        traceback_string = "".join(traceback_format)
        print(traceback_string)
        QtWidgets.QMessageBox.critical(self, "错误", "{}".format(value))
        # self.old_hook(ty, value, tb)

    def dump_config(self):
        save_config()

    def start(self):
        # 按开始键
        if not self.is_running:
            flag = self.data_handler.connect(self.com_port.text())
            config['port'] = self.com_port.text()
            self.dump_config()
            if not flag:
                return
            self.is_running = True
            self.timer.start(self.TRIGGER_TIME)
            self.set_enable_state()
            self.com_port.setEnabled(False)

    def stop(self):
        if self.is_running:
            self.is_running = False
            if self.timer.isActive():
                self.timer.stop()
            self.data_handler.disconnect()
            self.hist_trigger.clear()
            self.set_enable_state()

    def pre_initialize(self):
        self.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow", "手掌电子皮肤采集程序"))
        self.setWindowIcon(QtGui.QIcon(os.path.join(RESOURCE_FOLDER, "tujian.ico")))
        self.initialize_buttons()
        self.set_enable_state()

    def set_enable_state(self):
        self.button_start.setEnabled(not self.is_running)
        self.button_stop.setEnabled(self.is_running)
        self.label_output.setText("已连接" if self.is_running else "未连接")
        self.button_save_to.setEnabled(self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("结束采集")
        else:
            self.button_save_to.setText("采集到...")

    def initialize_buttons(self):
        self.button_start.clicked.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        self.button_set_zero.clicked.connect(self.data_handler.set_zero)
        self.button_abandon_zero.clicked.connect(self.data_handler.abandon_zero)
        self.set_enable_state()
        self.com_port.setText(config['port'])

    def trigger(self):
        try:
            self.data_handler.trigger()
            self.hand_plot_manager.plot()
            if self.is_running:
                time_now = time.time()
                if self.hist_trigger:
                    if time_now > self.hist_trigger[-1]:
                        if time_now - self.hist_trigger[0] > 1.:
                            self.label_output.setText("未连接")
                        else:
                            self.label_output.setText("已连接")
                self.hist_trigger.append(time_now)
        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            self.stop()
            raise e

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.stop()
        super(Window, self).closeEvent(a0)
        sys.exit()


def start():
    app = QtWidgets.QApplication(sys.argv)
    w = Window()
    w.show()
    w.trigger()
    sys.exit(app.exec_())
