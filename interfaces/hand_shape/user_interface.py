"""
手形界面
"""
LAN = 'chs'
# LAN = 'en'
import threading

from PyQt5 import QtCore, QtWidgets, QtGui
if LAN == "en":
    from interfaces.hand_shape.layout.layout_en import Ui_Form
else:
    from interfaces.hand_shape.layout.layout import Ui_Form
import pyqtgraph
import sys
import time
import os
import traceback
import numpy as np
from data.data_handler import DataHandler
from PIL import Image, ImageDraw
from config import config, save_config, get_config_mapping
from collections import deque
from usb.core import USBError
from multiple_skins.tactile_spliting import get_split_driver_class
from data.interpolation import Interpolation
from data.preprocessing import Filter, MedianFilter, RCFilterHP
from utils.performance_monitor import Ticker
from PyQt5.QtGui import QWheelEvent
from pyqtgraph.widgets.RawImageWidget import RawImageWidget
from interfaces.hand_shape.feature_extractor import FingerFeatureExtractor

STR_CONNECTED = "Connected" if LAN == "en" else "已连接"
STR_DISCONNECTED = "Disconnected" if LAN == "en" else "未连接"

#
STANDARD_PEN = pyqtgraph.mkPen('k')
MINIMUM_Y_LIM = 0
MAXIMUM_Y_LIM = 4
TRIGGER_TIME_RECORD_LENGTH = 10

RESOURCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
legend_color = lambda i: pyqtgraph.intColor(i, 16 * 1.5, maxValue=127 + 64)
STANDARD_PEN = pyqtgraph.mkPen('k')


class HandPlotManager:

    def __init__(self, fig_widget_2d: pyqtgraph.widgets.RawImageWidget.RawImageWidget,
                 fig_widget_1d: pyqtgraph.GraphicsLayoutWidget,
                 data_handler: DataHandler,
                 config_mapping, image,
                 downsample=1):

        self.cmap = pyqtgraph.ColorMap(np.linspace(0, 1, 17), (np.array(config_mapping['color_map']) * 255).astype(int))
        pixel_mapping = config_mapping['pixel_mapping']
        range_mapping = config_mapping['range_mapping']
        self.is_left_hand = config_mapping['is_left_hand']
        self.arrow_offset = config_mapping.get('arrow_offset', None)

        self.img_view = fig_widget_2d

        self.log_y_lim = (config['y_lim'][0], config['y_lim'][1])
        # imageAxisOrder
        #
        self.dd = data_handler
        # 加载底图
        self.downsample = downsample
        self.original_base_image = image
        self.original_base_image = self.original_base_image.resize((self.original_base_image.width // downsample,
                                                  self.original_base_image.height // downsample),
                                                 resample=Image.BILINEAR)
        self.base_image = self.original_base_image.copy()

        self.processing_image = self.base_image.copy()
        self.current_image = np.array(self.processing_image).transpose((1, 0, 2))
        img = np.array(self.current_image).transpose((1, 0, 2))
        if self.is_left_hand:
            img = img[::-1, :, :]
        self.img_view.setImage(img)
        # mapping_onto_image
        rects = {
            int(k): [((pixel_mapping[str(k)][0] + 0.5 * self.downsample) // self.downsample + 1,
                      (pixel_mapping[str(k)][1] + 0.5 * self.downsample) // self.downsample + 1),
                     ((pixel_mapping[str(k)][2] + 0.5 * self.downsample) // self.downsample + 1,
                      (pixel_mapping[str(k)][3] + 0.5 * self.downsample) // self.downsample + 1),
                     True,
                     self.make_mask((range_mapping[k][6], range_mapping[k][5])
                                    if range_mapping[k][4]
                                    else (range_mapping[k][5], range_mapping[k][6]),
                                    1.),
                     int(k)]
            for k in range_mapping.keys()
        }
        self.proj_funcs = {idx: self.make_projection_function(rect) for idx, rect in rects.items()}
        # 曲线图
        ax: pyqtgraph.PlotItem = fig_widget_1d.addPlot()
        # ax.setLabel(axis='left', text='Resistance (min) (kΩ)' if LAN == "en" else '电阻（最小值） (kΩ)')
        ax.setLabel(axis='left', text='Contact strength' if LAN == "en" else '接触强度')
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text='Time (s)' if LAN == "en" else '时间 (s)')
        # ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
        #     [f'{10 ** (-_): .1f}' for _ in values]
        # ax.getViewBox().setYRange(-self.log_y_lim[1], -self.log_y_lim[0])
        ax.getViewBox().setYRange(0, 256)
        fig_widget_1d.setBackground('w')
        ax.getViewBox().setBackgroundColor([255, 255, 255])
        ax.getAxis('bottom').setPen(STANDARD_PEN)
        ax.getAxis('left').setPen(STANDARD_PEN)
        ax.getAxis('bottom').setTextPen(STANDARD_PEN)
        ax.getAxis('left').setTextPen(STANDARD_PEN)
        ax.getViewBox().setMouseEnabled(x=False, y=False)
        ax.getViewBox().setMenuEnabled(False)
        ax.hideButtons()
        # 图例每行3个
        ax.addLegend(colCount=3)
        self.ax = ax
        self.lines = {int(idx): ax.plot(pen=pyqtgraph.mkPen(legend_color(idx), width=2),
                                        name=config_mapping['names'][idx])
                      for idx in range_mapping.keys()}
        # 存储
        self.filters = {int(idx): MedianFilter({'SENSOR_SHAPE': (1, 1), 'DATA_TYPE': float}, 2)
                        for idx in range_mapping.keys()}
        max_len = self.dd.max_len
        self.region_max = {int(idx): deque(maxlen=max_len) for idx in range_mapping.keys()}
        self.region_x_diff = {int(idx): deque(maxlen=max_len) for idx in range_mapping.keys()}
        self.region_y_diff = {int(idx): deque(maxlen=max_len) for idx in range_mapping.keys()}
        self.time = deque(maxlen=max_len)
        #
        self.img_view.wheelEvent = self.__on_mouse_wheel
        #
        self.lock = threading.Lock()
        #
        threading.Thread(target=self.process_forever, daemon=True).start()
        #
        self.img_view.resizeEvent = self.resize_event
        self.resize_transform = []  # 包括了缩放的比例和偏移量
        # 计算用
        self.finger_feature_extractors = {int(k): FingerFeatureExtractor(15, 4, 0.995, 10., 1.0)
                                          for k in config_mapping['range_mapping'].keys()}

    def clear(self):
        with self.lock:
            self.processing_image = self.base_image.copy()
            for idx in self.lines.keys():
                self.region_max[idx].clear()
                self.region_x_diff[idx].clear()
                self.region_y_diff[idx].clear()
            self.time.clear()

    @staticmethod
    def make_mask(shape, scale=1.):
        x_coord = np.abs(np.arange(shape[0]) - shape[0] // 2 + 0.5)
        y_coord = np.abs(np.arange(shape[1]) - shape[1] // 2 + 0.5)
        dist_sq = ((x_coord.reshape(-1, 1)) / shape[0] * 2) ** 3 + ((y_coord.reshape(1, -1)) / shape[1] * 2) ** 3
        mask = np.maximum(1. - dist_sq ** 3, 0)
        mask = np.ones_like(mask)  # 暂时取消
        mask *= scale
        return mask

    def save_y_lim(self):
        config['y_lim'] = (self.log_y_lim[0], self.log_y_lim[1])
        save_config()

    def resize_event(self, event):
        pass
        width_origin = self.original_base_image.width
        height_origin = self.original_base_image.height
        width_border = self.img_view.width()
        height_border = self.img_view.height()
        if width_border == 0 or height_border == 0:
            return
        if width_origin / height_origin > width_border / height_border:
            print("宽度占满")
            self.resize_transform = [width_border / width_origin, width_border / width_origin,
                                     0, 0.5 * (height_border - width_border / width_origin * height_origin)]
        else:
            print("高度占满")
            self.resize_transform = [height_border / height_origin, height_border / height_origin,
                                     0.5 * (width_border - height_border / height_origin * width_origin), 0]
        # 强制1:1
        self.resize_image()
        # super(pyqtgraph.widgets.RawImageWidget.RawImageWidget, self.img_view).resizeEvent(event)

    def resize_image(self):
        img = self.original_base_image.copy()
        img = img.resize((
            int(img.width * self.resize_transform[0]),
            int(img.height * self.resize_transform[1]),
        ),
            resample=Image.BILINEAR)
        img_empty = Image.new('RGBA',
                              (self.img_view.width(), self.img_view.height()),
                              (0, 0, 0, 0))
        img_empty.paste(img, (int(self.resize_transform[2]), int(self.resize_transform[3])),
                        mask=img.split()[-1])
        img = img_empty
        self.base_image = img.copy()
        self.current_image = np.array(img).swapaxes(0, 1)[::-1, :, :]\
            if self.is_left_hand else np.array(img).swapaxes(0, 1)
        self.plot()

    def reset_image(self):
        self.processing_image = self.base_image.copy()

    def make_projection_function(self, rect):
        """依据rect预计算投影函数"""
        # 计算边向量
        base_point = rect[0]
        x_delta = (rect[1][0] - rect[0][0], rect[1][1] - rect[0][1])
        # y_rate = (rect[3].shape[1] / rect[3].shape[0]) ** -1
        y_rate = rect[3].shape[1] / rect[3].shape[0]
        y_delta = (-x_delta[1] * y_rate,
                   x_delta[0] * y_rate)
        if not rect[2]:
            y_delta = (-y_delta[0], -y_delta[1])

        center = (round(base_point[0] + 0.5 * x_delta[0] + 0.5 * y_delta[0]),
                  round(base_point[1] + 0.5 * x_delta[1] + 0.5 * y_delta[1]))
        angle = -np.arctan2(rect[1][1] - rect[0][1], rect[1][0] - rect[0][0])
        x_length = np.sqrt((rect[1][0] - rect[0][0]) ** 2 + (rect[1][1] - rect[0][1]) ** 2)
        new_shape = (int(x_length), int(x_length * y_rate))
        pass

        def projection_function(data: np.ndarray):
            # data = data * rect[3]
            data = Interpolation(2, 1.0, data.shape).smooth(data * rect[3])
            data = np.log(np.maximum(data, 1e-6)) / np.log(10)
            data = np.clip((data + self.log_y_lim[1]) / (self.log_y_lim[1] - self.log_y_lim[0]), 0., 1.)
            img_original = Image.fromarray((self.cmap.map(data.T, mode=float) * 255.).astype(np.uint8),
                                           mode='RGBA')
            img_scaled = img_original.resize((int(new_shape[0] * self.resize_transform[0]),
                                              int(new_shape[1] * self.resize_transform[1])),
                                             resample=Image.BILINEAR)
            img_rotated = img_scaled.rotate(angle * 180 / np.pi, resample=Image.BILINEAR,
                                            expand=True, fillcolor=(0, 0, 0, 0))
            self.processing_image.paste(img_rotated,
                                        (int(center[0] * self.resize_transform[0] - img_rotated.width // 2 + self.resize_transform[2]),
                                         int(center[1] * self.resize_transform[1] - img_rotated.height // 2 + self.resize_transform[3])),
                                        mask=img_rotated.split()[-1])
            pass
            # 0304新增
            # new code to draw the arrow
            if self.arrow_offset is not None:
                idx = rect[4]
                offset_x = self.arrow_offset[str(idx)][0] * self.resize_transform[0]
                offset_y = self.arrow_offset[str(idx)][1] * self.resize_transform[1]
                if self.region_x_diff[idx] and self.region_y_diff[idx]:
                    x_diff = self.region_x_diff[idx][-1] * self.resize_transform[0] * 0.5
                    y_diff = self.region_y_diff[idx][-1] * self.resize_transform[1] * 0.5
                    arrow_length = np.sqrt(x_diff ** 2 + y_diff ** 2)
                    arrow_angle = np.arctan2(y_diff, x_diff)
                    arrow_end_x = center[0] * self.resize_transform[0] + offset_x + arrow_length * np.cos(arrow_angle) + self.resize_transform[2]
                    arrow_end_y = center[1] * self.resize_transform[1] + offset_y + arrow_length * np.sin(arrow_angle) + self.resize_transform[3]

                    draw = ImageDraw.Draw(self.processing_image)
                    draw.line([(center[0] * self.resize_transform[0] + offset_x + self.resize_transform[2],
                                center[1] * self.resize_transform[1] + offset_y + self.resize_transform[3]),
                               (arrow_end_x,
                                arrow_end_y)],
                              fill=(255, 0, 0, 255), width=int(1 * (self.resize_transform[0] + self.resize_transform[1]) + 1))
                    if arrow_length > 2:
                        arrow_size = int(3 * (self.resize_transform[0] + self.resize_transform[1]) + 1)
                        draw.polygon([(arrow_end_x, arrow_end_y),
                                      (arrow_end_x - arrow_size * np.cos(arrow_angle - np.pi / 6),
                                       arrow_end_y - arrow_size * np.sin(arrow_angle - np.pi / 6)),
                                      (arrow_end_x - arrow_size * np.cos(arrow_angle + np.pi / 6),
                                       arrow_end_y - arrow_size * np.sin(arrow_angle + np.pi / 6))],
                                     fill=(255, 0, 0, 255),)

        return projection_function

    def __on_mouse_wheel(self, event: QWheelEvent):
        return
        if not config['fixed_range']:
            # 当鼠标滚轮滚动时，调整图像的显示范围
            if event.angleDelta().y() > 0:
                if self.log_y_lim[1] < MAXIMUM_Y_LIM:
                    self.log_y_lim = (self.log_y_lim[0] + 0.1, self.log_y_lim[1] + 0.1)
            else:
                if self.log_y_lim[0] > MINIMUM_Y_LIM:
                    self.log_y_lim = (self.log_y_lim[0] - 0.1, self.log_y_lim[1] - 0.1)
            self.log_y_lim = (round(self.log_y_lim[0], 1), round(self.log_y_lim[1], 1))
            self.ax.getViewBox().setYRange(-self.log_y_lim[1], -self.log_y_lim[0])
            self.save_y_lim()

    def process_forever(self):
        ticker = Ticker()
        ticker.tic()
        while True:
            try:
                self.process_image()
            except ValueError:
                pass
            # ticker.toc("process_image")
            time.sleep(0.001)

    def process_image(self):
        if self.dd.value and self.dd.zero_set:
            self.dd.lock.acquire()
            data_fingers = self.dd.value[-1]  # 唯一的数据流入位置
            time_now = self.dd.time[-1]
            self.dd.value.clear()
            self.dd.time.clear()
            self.dd.lock.release()
            self.lock.acquire()
            self.reset_image()
            for idx, data in data_fingers.items():
                self.proj_funcs[idx](data)
                # 0304前旧版本
                # max_value = np.max(data)
                # max_value = np.log(np.maximum(max_value, 1e-6)) / np.log(10.)
                # 新的
                max_value = self.finger_feature_extractors[idx](data)['contact_strength']
                x_diff = self.finger_feature_extractors[idx](data)['center_x_diff']
                y_diff = self.finger_feature_extractors[idx](data)['center_y_diff']
                self.region_max[idx].append(max_value)
                self.region_x_diff[idx].append(x_diff)
                self.region_y_diff[idx].append(y_diff)
            self.lock.release()
            self.time.append(time_now)
            self.processing_image.putalpha(self.base_image.split()[-1])
            img = np.array(self.processing_image).transpose((1, 0, 2))
            self.current_image = img[::-1, :, :] if self.is_left_hand else img
            # 在self.lines_view上绘制每个分区的均值

    def plot(self):
        if self.current_image is not None:
            self.lock.acquire()
            self.img_view.setImage(self.current_image)
            self.current_image = None
            for idx, line in self.lines.items():
                line.setData(self.time, self.region_max[idx])

            self.lock.release()


class Window(QtWidgets.QWidget, Ui_Form):

    TRIGGER_TIME = config.get("trigger_time")

    def __init__(self, mode):
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self.catch_exceptions
        #
        if mode == 'zw':
            from backends.usb_driver import ZWUsbSensorDriver as SensorDriver
            # 修改horizontalLayout_3的layoutStretch
            # self.horizontalLayout_3.setStretch(3, 2)
        elif mode == 'zy':
            from backends.usb_driver import ZYUsbSensorDriver as SensorDriver
            self.horizontalLayout_3.setStretch(0, 1)
            self.horizontalLayout_3.setStretch(1, 1)
        elif mode == 'zv':
            from backends.usb_driver import ZVUsbSensorDriver as SensorDriver
            self.horizontalLayout_3.setStretch(0, 1)
            self.horizontalLayout_3.setStretch(1, 1)
        elif mode == 'gl':
            from backends.usb_driver import GLUsbSensorDriver as SensorDriver
            self.horizontalLayout_3.setStretch(0, 1)
            self.horizontalLayout_3.setStretch(1, 1)
        else:
            raise Exception("Invalid mode")
        config_mapping = get_config_mapping(mode)
        self.data_handler = DataHandler(get_split_driver_class(SensorDriver, config_mapping), max_len=256)
        # self.data_handler.set_filter(filter_name_frame="无", filter_name_time="中值-0.2s")
        self.data_handler.filter_time = Filter(self.data_handler.driver)
        self.data_handler.filter_frame = Filter(self.data_handler.driver)
        self.data_handler.filter_after_zero = RCFilterHP(self.data_handler.driver, alpha=0.0001)
        self.is_running = False
        #
        base_image = Image.open(os.path.join(RESOURCE_FOLDER, f'hand_{mode}.png')).convert('RGBA')
        self.hand_plot_manager = HandPlotManager(fig_widget_2d=self.fig_image,
                                                 fig_widget_1d=self.fig_lines,
                                                 data_handler=self.data_handler,
                                                 config_mapping=config_mapping,
                                                 image=base_image,
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
        self.scheduled_set_zero = False

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
        QtWidgets.QMessageBox.critical(self, "Error" if LAN == "en" else "错误", "{}".format(value))
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
            self.scheduled_set_zero = True

    def stop(self):
        if self.is_running:
            self.is_running = False
            if self.timer.isActive():
                self.timer.stop()
            self.data_handler.disconnect()
            self.hist_trigger.clear()
            self.set_enable_state()
            self.scheduled_set_zero = False

    def clear(self):
        self.data_handler.clear()
        self.hand_plot_manager.clear()

    def pre_initialize(self):
        self.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow",
                                                              "E-skin Display" if LAN == 'en' else "电子皮肤采集程序"))
        self.setWindowIcon(QtGui.QIcon(os.path.join(RESOURCE_FOLDER, "tujian.ico")))
        logo_path = os.path.join(RESOURCE_FOLDER, "logo.png")
        self.label_logo.setPixmap(QtGui.QPixmap(logo_path))
        self.label_logo.setScaledContents(True)
        self.initialize_buttons()
        self.set_enable_state()

    def set_enable_state(self):
        self.button_start.setEnabled(not self.is_running)
        self.button_stop.setEnabled(self.is_running)
        self.label_output.setText(STR_CONNECTED if self.is_running else STR_DISCONNECTED)
        self.button_save_to.setEnabled(self.is_running)
        self.button_set_zero.setEnabled(self.is_running)
        self.button_abandon_zero.setEnabled(self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("End acquisition" if LAN == "en" else "结束采集")
        else:
            self.button_save_to.setText("Acquire to file..." if LAN == "en" else "采集到...")

    def initialize_buttons(self):
        self.button_start.clicked.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        self.button_set_zero.clicked.connect(self.data_handler.set_zero)
        self.button_abandon_zero.clicked.connect(self.clear)
        self.set_enable_state()
        self.com_port.setText(config['port'])

    def trigger(self):
        try:
            self.data_handler.trigger()
            if self.scheduled_set_zero:
                success = self.data_handler.set_zero()
                if success:
                    self.scheduled_set_zero = False
            self.hand_plot_manager.plot()
            if self.is_running:
                time_now = time.time()
                if self.hist_trigger:
                    if time_now > self.hist_trigger[-1]:
                        if time_now - self.hist_trigger[0] > 1.:
                            self.label_output.setText(STR_DISCONNECTED)
                        else:
                            self.label_output.setText(STR_CONNECTED)
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


def start(mode):
    app = QtWidgets.QApplication(sys.argv)
    w = Window(mode)
    w.show()
    w.trigger()
    sys.exit(app.exec_())
