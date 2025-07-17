"""
显示界面，适用于large采集卡
顺便可以给small采集卡使用
"""
LAN = 'chs'
# LAN = 'en'

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QGraphicsSceneWheelEvent
from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent
from multiple_skins.tactile_spliting import get_split_driver_class
import time
from interfaces.multiple_zones.layout.layout_2 import Ui_Form
import pyqtgraph
import os
#
from usb.core import USBError
import sys
import traceback
import numpy as np
from data_processing.data_handler import DataHandler
#
from config import config, save_config, get_config_mapping
from interfaces.public.utils import set_logo
#
STANDARD_PEN = pyqtgraph.mkPen('k')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('k', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}
LABEL_TIME = 'T/sec'
LABEL_PRESSURE = 'p/kPa'
LABEL_VALUE = 'Value'
LABEL_RESISTANCE = 'Resistance/(kΩ)'
Y_LIM_INITIAL = config['y_lim']

MINIMUM_Y_LIM = 0.0
MAXIMUM_Y_LIM = 5.0
assert Y_LIM_INITIAL.__len__() == 2
assert Y_LIM_INITIAL[0] >= MINIMUM_Y_LIM - 0.2
assert Y_LIM_INITIAL[1] <= MAXIMUM_Y_LIM + 0.2


RESOURCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../resources')

def log(v):
    return np.log(np.maximum(v, 1e-6)) / np.log(10)


class Window(QtWidgets.QWidget, Ui_Form):
    """
    主窗口
    """

    TRIGGER_TIME = config["trigger_time"]
    COLORS = [[15, 15, 15],
              [48, 18, 59],
              [71, 118, 238],
              [27, 208, 213],
              [97, 252, 108],
              [210, 233, 53],
              [254, 155, 45],
              [218, 57, 7],
              [122, 4, 3]]

    def __init__(self, mode, fixed_range=False):
        """

        :param mode: "usb" or "socket"
        """
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self.catch_exceptions
        #
        self.fixed_range = fixed_range
        self.is_running = False
        self._using_calibration = False
        #
        self.log_y_lim = Y_LIM_INITIAL
        self.line_maximum = self.create_a_line(self.fig_1)
        self.line_tracing = self.create_a_line(self.fig_2)
        self.plots = {
            0: self.create_an_image(self.fig_image_0),
            1: self.create_an_image(self.fig_image_1)
        }
        self.mode = mode
        if mode == 'usb':
            from backends.usb_driver import LargeUsbSensorDriver as SensorDriver
        elif mode == 'can':
            from backends.can_driver import Can16SensorDriver as SensorDriver
        else:
            raise NotImplementedError()
        # 标定状态
        self.scaling = log
        self.__set_using_calibration(False)
        # 布局修正
        self.horizontalLayout_2.setStretch(0, 1)
        self.horizontalLayout_2.setStretch(1, 1)
        self.horizontalLayout_2.setStretch(2, 2)
        config_mapping = get_config_mapping('jk')
        self.data_handler = DataHandler(get_split_driver_class(SensorDriver, config_mapping), max_len=64)
        self.pre_initialize()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        #
        self.time_last_image_update = np.uint32(0)
        # 是否处于使用标定状态
        self.__set_calibrator(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           '../../calibrate_files/default_calibration_file.clb'))

    def catch_exceptions(self, ty, value, tb):
        # 错误重定向为弹出对话框
        traceback_format = traceback.format_exception(ty, value, tb)
        traceback_string = "".join(traceback_format)
        print(traceback_string)
        QtWidgets.QMessageBox.critical(self, ("Error" if LAN == 'en' else "错误"), "{}".format(value))
        # self.old_hook(ty, value, tb)

    @property
    def y_lim(self):
        # 这里经常改
        if self._using_calibration:
            return self.data_handler.calibration_adaptor.range()
        else:
            return [-self.log_y_lim[1], -self.log_y_lim[0]]

    def start(self):
        # 按开始键
        if not self.is_running:
            flag = self.data_handler.connect(self.com_port.text())
            config['port'] = self.com_port.text()
            save_config()
            if not flag:
                return
            self.is_running = True
            self.timer.start(self.TRIGGER_TIME)
            self.set_enable_state()
            self.com_port.setEnabled(False)

    def stop(self):
        # 按停止键
        config['y_lim'] = self.log_y_lim
        save_config()
        if self.is_running:
            self.is_running = False
            if self.timer.isActive():
                self.timer.stop()
            self.data_handler.disconnect()
            self.set_enable_state()

    def pre_initialize(self):

        set_logo(self)
        self.initialize_images()
        self.initialize_buttons()
        self.initialize_others()
        self.set_enable_state()
        self.__apply_y_lim()
        #
        self.com_port.setEnabled(False)  # 一旦成功开始，就再也不能修改

    def __make_cb_clicked_on_image(self, image_idx):
        def __clicked_on_image(event: MouseClickEvent):
            # 图上选点
            plot = self.plots[image_idx]
            size = [plot.width(), plot.height()]
            vb = plot.getView()
            vb_state = vb.state['viewRange']
            pix_offset = [-size[j] / (vb_state[j][1] - vb_state[j][0]) * vb_state[j][0] for j in range(2)]
            pix_unit = [size[j] / (vb_state[j][1] - vb_state[j][0]) for j in range(2)]
            x = (event.pos().x() - pix_offset[0]) / pix_unit[0]
            y = (event.pos().y() - pix_offset[1]) / pix_unit[1]
            xx = int(y / self.data_handler.interpolation.interp)
            yy = int(x / self.data_handler.interpolation.interp)

            if not vb.state['yInverted']:
                xx = self.data_handler.driver.get_zeros(image_idx).shape[0] - xx - 1
            if vb.state['xInverted']:
                yy = self.data_handler.driver.get_zeros(image_idx).shape[1] - yy - 1

            # 获取分片信息
            range_mapping = self.data_handler.driver.range_mapping
            if image_idx not in range_mapping:
                return
            slicing, x_invert, y_invert, xy_swap, _, _ = range_mapping[image_idx]

            if xy_swap:
                xx, yy = yy, xx
            if x_invert:
                xx = slicing[0].stop - slicing[0].start - xx - 1
            if y_invert:
                yy = slicing[1].stop - slicing[1].start - yy - 1

            # 映射到 full_data 坐标
            xx = slicing[0].start + xx
            yy = slicing[1].start + yy

            flag = 0 <= xx < self.data_handler.driver.SENSOR_SHAPE[0] and 0 <= yy < self.data_handler.driver.SENSOR_SHAPE[1]
            if flag:
                self.data_handler.set_tracing(xx, yy)
                print(xx, yy)
        return __clicked_on_image

    def __on_mouse_wheel(self, event: QGraphicsSceneWheelEvent):
        if not self.fixed_range:
            # 当鼠标滚轮滚动时，调整图像的显示范围
            if event.delta() > 0:
                if self.log_y_lim[1] < MAXIMUM_Y_LIM:
                    self.log_y_lim = (self.log_y_lim[0] + 0.1, self.log_y_lim[1] + 0.1)
            else:
                if self.log_y_lim[0] > MINIMUM_Y_LIM:
                    self.log_y_lim = (self.log_y_lim[0] - 0.1, self.log_y_lim[1] - 0.1)
            self.log_y_lim = (round(self.log_y_lim[0], 1), round(self.log_y_lim[1], 1))
            self.__apply_y_lim()
            pass

    def initialize_images(self):

        colors = self.COLORS
        pos = (0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1)
        cmap = pyqtgraph.ColorMap(pos=[_ for _ in pos], color=colors)
        for idx, plot in self.plots.items():
            plot.ui.histogram.hide()
            plot.ui.menuBtn.hide()
            plot.ui.roiBtn.hide()
            plot.setColorMap(cmap)
            vb: pyqtgraph.ViewBox = plot.getImageItem().getViewBox()
            vb.setMouseEnabled(x=False, y=False)
            vb.setBackgroundColor(pyqtgraph.mkColor(0.95))
            plot.getImageItem().scene().sigMouseClicked.connect(self.__make_cb_clicked_on_image(idx))
            plot.getImageItem().wheelEvent = self.__on_mouse_wheel
            # 设置invert
            plot.getView().invertX(config['x_invert'])
            plot.getView().invertY(config['y_invert'])

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
        ax.getViewBox().setMouseEnabled(x=False, y=False)
        ax.hideButtons()
        line.get_axis = lambda: ax
        return line

    def __apply_y_lim(self):
        for line in [self.line_maximum, self.line_tracing]:
            line.getViewBox().setYRange(*self.y_lim)
            pass

    def __set_using_calibration(self, b):
        if b:
            self._using_calibration = True
            for line in [self.line_maximum, self.line_tracing]:
                ax = line.get_axis()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{_: .1f}' for _ in values]
                ax.getAxis('left').label.setPlainText(LABEL_PRESSURE)

            self.scaling = lambda x: x
            self.__apply_y_lim()
        else:
            self._using_calibration = False
            for line in [self.line_maximum, self.line_tracing]:
                ax = line.get_axis()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{10 ** (-_): .1f}' for _ in values]
                ax.getAxis('left').label.setPlainText(LABEL_RESISTANCE)

            self.scaling = log
            self.__apply_y_lim()

    def create_an_image(self, fig_widget: pyqtgraph.GraphicsLayoutWidget):
        fig_widget.setBackground(0.95)
        plot = pyqtgraph.ImageView()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(plot, 0, 0)
        fig_widget.setLayout(layout)
        plot.adjustSize()
        return plot

    def set_enable_state(self):
        # 根据实际的开始/停止状态，设定各按钮是否激活
        self.button_start.setEnabled(not self.is_running)
        self.button_stop.setEnabled(self.is_running)
        self.button_save_to.setEnabled(self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("End acquisition" if LAN == "en" else "结束采集")
        else:
            self.button_save_to.setText("Acquire to file..." if LAN == "en" else "采集到...")
        if self.mode == 'usb':
            if self.is_running:
                self.com_port.setEnabled(False)
        elif self.mode == 'can':
            pass
        else:
            raise NotImplementedError()


    def __apply_swap(self, data):
        if config['xy_swap']:
            return data.T
        else:
            return data

    def __set_filter(self):
        self.data_handler.set_filter("None" if LAN == "en" else "无", self.combo_filter_time.currentText())
        config['filter_time_index'] = self.combo_filter_time.currentIndex()
        save_config()

    def __set_interpolate_and_blur(self):
        interpolate = int(self.combo_interpolate.currentText())
        blur = float(self.combo_blur.currentText())
        self.data_handler.set_interpolation_and_blur(interpolate=interpolate, blur=blur)
        config['interpolate_index'] = self.combo_interpolate.currentIndex()
        config['blur_index'] = self.combo_blur.currentIndex()
        save_config()

    def __set_calibrator(self, path=None):
        if path is None:
            path = QtWidgets.QFileDialog.getOpenFileName(self, "选择标定文件", "", "标定文件 (*.clb)")[0]
        if path:
            flag = self.data_handler.set_calibrator(path, forced_to_use_clb=True)
            if flag:
                # self.hand_plot_manager.set_axes_using_calibration(True)
                self.__set_using_calibration(True)
                self.scheduled_set_zero = True

    def __abandon_calibrator(self):
        self.data_handler.abandon_calibrator()
        self.__set_using_calibration(False)

    def initialize_buttons(self):
        self.button_start.clicked.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        self.combo_filter_time.setCurrentIndex(config.get('filter_time_index'))
        self.combo_interpolate.setCurrentIndex(config.get('interpolate_index'))
        self.combo_blur.setCurrentIndex(config.get('blur_index'))
        self.__set_filter()
        self.__set_interpolate_and_blur()
        self.combo_filter_time.currentIndexChanged.connect(self.__set_filter)
        self.combo_interpolate.currentIndexChanged.connect(self.__set_interpolate_and_blur)
        self.combo_blur.currentIndexChanged.connect(self.__set_interpolate_and_blur)
        self.set_enable_state()
        self.button_set_zero.clicked.connect(self.data_handler.set_zero)
        self.button_abandon_zero.clicked.connect(self.data_handler.abandon_zero)
        self.button_save_to.clicked.connect(self.__trigger_save_button)

        # 标定功能
        self.button_load_calibration.clicked.connect(lambda: self.__set_calibrator(path=None))
        self.button_exit_calibration.clicked.connect(self.__abandon_calibrator)

    def __trigger_save_button(self):
        if self.data_handler.output_file:
            self.data_handler.close_output_file()
        else:
            file = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Select path" if LAN == "en" else "选择输出路径",
                "",
                "Database (*.db)" if LAN == "en" else "数据库 (*.db)")
            if file[0]:
                self.data_handler.link_output_file(file[0])
        self.set_enable_state()

    def initialize_others(self):
        str_port = config.get('port')
        if not isinstance(str_port, str):
            raise Exception('Config file error' if LAN == "en" else '配置文件出错')

        if self.mode == 'usb':
            self.com_port.setEnabled(True)
            self.com_port.setText(config['port'])
        elif self.mode == 'can':
            self.com_port.setEnabled(False)
            self.com_port.setText('-')
        else:
            raise NotImplementedError()

    def trigger(self):
        try:
            self.data_handler.trigger()
            if self.data_handler.value:
                for idx_plot, plot in self.plots.items():
                    plot.setImage(self.__apply_swap(self.scaling(np.array(self.data_handler.value[-1][idx_plot].T))),
                                  levels=self.y_lim)
                self.line_maximum.setData(self.data_handler.time, self.scaling(self.data_handler.maximum))
                self.line_tracing.setData(self.data_handler.t_tracing, self.scaling(self.data_handler.tracing))
        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            self.stop()
            raise e

    def trigger_null(self):
        for idx_plot, plot in self.plots.items():
            plot.setImage(self.__apply_swap(self.data_handler.driver.get_zeros(idx_plot)).T
                               - MAXIMUM_Y_LIM,
                               levels=self.y_lim)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.stop()
        super(Window, self).closeEvent(a0)
        sys.exit()


def start(mode='standard'):
    app = QtWidgets.QApplication(sys.argv)
    w = Window(mode)
    w.show()
    w.trigger_null()
    sys.exit(app.exec_())
