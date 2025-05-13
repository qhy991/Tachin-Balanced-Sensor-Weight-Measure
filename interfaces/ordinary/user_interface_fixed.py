"""
显示界面，适用于large采集卡
顺便可以给small采集卡使用
"""
# LAN = "chs"
LAN = "en"

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QGraphicsSceneWheelEvent
from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent
import time
if LAN == "en":
    from interfaces.ordinary.layout.layout_fixed_en import Ui_Form
else:
    from interfaces.ordinary.layout.layout_fixed import Ui_Form
import pyqtgraph
#
from usb.core import USBError
import sys
import traceback
import numpy as np
from data_processing.data_handler import DataHandler
from backends.sensor_driver import LargeSensorDriver
from server.socket_client import SocketClient
#
from config import config, save_config

#
STANDARD_PEN = pyqtgraph.mkPen('k')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('k', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}
font = QtGui.QFont()
FONT_SIZE = 10
font.setPointSize(FONT_SIZE)
font.setFamily('Microsoft YaHei')
FONT_METRICS = QtGui.QFontMetrics(font)
#
LABEL_TIME = 'T/sec'
LABEL_PRESSURE = 'p/kPa'
LABEL_VALUE = 'Value'
LABEL_RESISTANCE = 'Resistance/(kΩ)'
Y_LIM_INITIAL = config['y_lim']
X_INVERT = config['x_invert']
Y_INVERT = config['y_invert']
DISPLAY_RANGE = [[25, 39], [25, 39]]
MINIMUM_Y_LIM = 0.0
MAXIMUM_Y_LIM = 4.0
assert Y_LIM_INITIAL.__len__() == 2
assert Y_LIM_INITIAL[0] >= MINIMUM_Y_LIM - 0.5
assert Y_LIM_INITIAL[1] <= MAXIMUM_Y_LIM + 0.5


def log(v):
    return np.log(np.maximum(v, 1e-6)) / np.log(10)


class Window(QtWidgets.QWidget, Ui_Form):
    """
    主窗口
    """

    TRIGGER_TIME = config["trigger_time"]
    # COLORS = [[15, 15, 15],
    #           [48, 18, 59],
    #           [71, 118, 238],
    #           [27, 208, 213],
    #           [97, 252, 108],
    #           [210, 233, 53],
    #           [254, 155, 45],
    #           [218, 57, 7],
    #           [122, 4, 3]]
    COLORS = [[0.14902, 0.14902, 0.14902, 1.0], [0.25107, 0.25237, 0.63374, 1.0],
     [0.27628, 0.42118, 0.89123, 1.0], [0.25862, 0.57958, 0.99876, 1.0],
     [0.15844, 0.73551, 0.92305, 1.0], [0.09267, 0.86554, 0.7623, 1.0],
     [0.19659, 0.94901, 0.59466, 1.0], [0.42778, 0.99419, 0.38575, 1.0],
     [0.64362, 0.98999, 0.23356, 1.0], [0.80473, 0.92452, 0.20459, 1.0],
     [0.93301, 0.81236, 0.22667, 1.0], [0.99314, 0.67408, 0.20348, 1.0],
     [0.9836, 0.49291, 0.12849, 1.0], [0.92105, 0.31489, 0.05475, 1.0],
     [0.81608, 0.18462, 0.01809, 1.0], [0.66449, 0.08436, 0.00424, 1.0],
     [0.4796, 0.01583, 0.01055, 1.0]]

    def __init__(self, mode='direct', fixed_range=True):
        """

        :param mode: "direct" or "socket"
        """
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self.catch_exceptions
        #
        if mode == 'direct':
            self.data_handler = DataHandler(LargeSensorDriver)
        elif mode == 'socket':
            self.data_handler = DataHandler(SocketClient)
        else:
            raise NotImplementedError()
        self.fixed_range = fixed_range
        self.is_running = False
        #
        self.log_y_lim = Y_LIM_INITIAL
        self._using_calibration = False
        self.line_maximum = self.create_a_line(self.fig_1)
        self.line_tracing = self.create_a_line(self.fig_2)
        self.plot = self.create_an_image(self.fig_image)
        self.pre_initialize()
        #
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        self.last_trigger_time = -0.
        #
        self.time_last_image_update = np.uint32(0)
        # 是否处于使用标定状态
        self.scaling = log

    def catch_exceptions(self, ty, value, tb):
        # 错误重定向为弹出对话框
        traceback_format = traceback.format_exception(ty, value, tb)
        traceback_string = "".join(traceback_format)
        print(traceback_string)
        QtWidgets.QMessageBox.critical(self, "Error" if LAN == "en" else "错误",
                                       "{}".format(value))
        # self.old_hook(ty, value, tb)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)

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
        # 按停止键
        config['y_lim'] = self.log_y_lim
        self.dump_config()
        if self.is_running:
            self.is_running = False
            if self.timer.isActive():
                self.timer.stop()
            self.data_handler.disconnect()
            self.set_enable_state()

    def pre_initialize(self):
        self.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow",
                                                              "E-skin Display" if LAN == "en" else
                                                              "电子皮肤采集程序-途见科技"))
        self.setWindowIcon(QtGui.QIcon("./ordinary/layout/tujian.ico"))
        logo_path = "./ordinary/resources/logo.png"
        self.label_logo.setPixmap(QtGui.QPixmap(logo_path))
        self.label_logo.setScaledContents(True)
        self.initialize_background()
        self.initialize_image()
        self.initialize_buttons()
        self.initialize_others()
        self.set_enable_state()
        self.__apply_y_lim()
        self.trigger_null()
        #

    def initialize_background(self):
        pass

    def __clicked_on_image(self, event: MouseClickEvent):
        # 图上选点
        size = [self.plot.width(), self.plot.height()]
        vb = self.plot.getView()
        vb_state = vb.state['viewRange']
        pix_offset = [-size[j] / (vb_state[j][1] - vb_state[j][0]) * vb_state[j][0] for j in range(2)]
        pix_unit = [size[j] / (vb_state[j][1] - vb_state[j][0]) for j in range(2)]
        x = (event.pos().x() - pix_offset[0]) / pix_unit[0]
        y = (event.pos().y_down() - pix_offset[1]) / pix_unit[1]
        xx = int(y / self.data_handler.interpolation.interp)
        yy = int(x / self.data_handler.interpolation.interp)

        if not vb.state['yInverted']:
            xx = self.data_handler.driver.SENSOR_SHAPE[0] - xx - 1
        if vb.state['xInverted']:
            yy = self.data_handler.driver.SENSOR_SHAPE[1] - yy - 1
        flag = 0 <= xx < self.data_handler.driver.SENSOR_SHAPE[0] and 0 <= yy < self.data_handler.driver.SENSOR_SHAPE[1]
        if flag:
            self.data_handler.set_tracing(xx, yy)
            print(xx, yy)

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

    def initialize_image(self):
        self.plot.ui.histogram.hide()
        self.plot.ui.menuBtn.hide()
        self.plot.ui.roiBtn.hide()
        #
        # 设置Form的backgroud-color
        #
        colors = [[int(_ * 255) for _ in color] for color in self.COLORS]
        pos = np.linspace(0, 1, 17).tolist()
        cmap = pyqtgraph.ColorMap(pos=[_ for _ in pos], color=colors)
        self.plot.setColorMap(cmap)
        vb: pyqtgraph.ViewBox = self.plot.getImageItem().getViewBox()
        vb.setMouseEnabled(x=False, y=False)
        vb.invertX(X_INVERT)
        vb.invertY(Y_INVERT)
        vb.setBackgroundColor(pyqtgraph.mkColor(0.95))
        self.plot.getImageItem().scene().sigMouseClicked.connect(self.__clicked_on_image)
        self.plot.getImageItem().wheelEvent = self.__on_mouse_wheel
        # 设置范围
        self.__set_xy_range()

    def __set_xy_range(self):
        interp = self.data_handler.interpolation.interp
        x_range = [(DISPLAY_RANGE[0][0] - 0.5) * interp, (DISPLAY_RANGE[0][1] - 1.5) * interp]
        y_range = [(DISPLAY_RANGE[1][0] - 0.5) * interp, (DISPLAY_RANGE[1][1] - 1.5) * interp]
        self.plot.getView().setRange(xRange=x_range,
                                     yRange=y_range)

    def create_a_line(self, fig_widget: pyqtgraph.GraphicsLayoutWidget):
        ax: pyqtgraph.PlotItem = fig_widget.addPlot()
        ax.setLabel(axis='left', text=LABEL_RESISTANCE, **{'font-size': '10pt', 'font-family': 'Microsoft YaHei'})
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text=LABEL_TIME, **{'font-size': '10pt', 'font-family': 'Microsoft YaHei'})
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
        ax.getAxis('bottom').setStyle(tickFont=font)
        ax.getAxis('left').setStyle(tickFont=font)
        ax.getViewBox().setMouseEnabled(x=False, y=False)
        ax.hideButtons()
        line.get_axis = lambda: ax
        return line

    @property
    def y_lim(self):
        # 这里经常改
        # return [10 ** (-self.log_y_lim[1]), 10 ** (-self.log_y_lim[0])]
        if self._using_calibration:
            return [0, 5.]
        else:
            return [-self.log_y_lim[1], -self.log_y_lim[0]]

    def __apply_swap(self, data):
        if config['xy_swap']:
            return data.T
        else:
            return data

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
            self.__apply_y_lim()
        else:
            self._using_calibration = False
            for line in [self.line_maximum, self.line_tracing]:
                ax = line.getViewBox()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{10 ** (-_): .1f}' for _ in values]
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

    def __set_filter(self):
        self.data_handler.set_filter("无", "Average-0.2s" if LAN == "en" else "均值-0.2s")

    def __set_interpolate_and_blur(self):
        self.data_handler.set_interpolation_and_blur(interpolate=4, blur=0.125)

    def initialize_buttons(self):
        self.button_start.clicked.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        self.__set_filter()
        self.__set_interpolate_and_blur()
        self.set_enable_state()

    def __trigger_save_button(self):
        if self.data_handler.output_file:
            self.data_handler.close_output_file()
            print('结束采集')
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
        self.com_port.setText(config['port'])

    def trigger(self):
        try:
            self.data_handler.trigger()
            time_now = time.time()
            if self.data_handler.smoothed_value and time_now < self.last_trigger_time + self.TRIGGER_TIME:
                self.plot.setImage(self.__apply_swap(log(np.array(self.data_handler.smoothed_value[-1].T))),
                                   levels=self.y_lim)
                self.__set_xy_range()
                self.plot.getView().invertX(X_INVERT)
                self.plot.getView().invertY(Y_INVERT)
                self.line_maximum.setData(self.data_handler.time, log(self.data_handler.maximum))
                self.line_tracing.setData(self.data_handler.t_tracing, log(self.data_handler.tracing))
            self.last_trigger_time = time_now
        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            self.stop()
            raise e

    def trigger_null(self):
        self.plot.setImage(self.__apply_swap(np.zeros(
            [_ * self.data_handler.interpolation.interp for _ in self.data_handler.driver.SENSOR_SHAPE])).T
                           - MAXIMUM_Y_LIM,
                           levels=self.y_lim)
        self.__set_xy_range()
        self.plot.getView().invertX(X_INVERT)
        self.plot.getView().invertY(Y_INVERT)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.stop()
        super(Window, self).closeEvent(a0)
        sys.exit()


def start(mode='direct'):
    app = QtWidgets.QApplication(sys.argv)
    w = Window(mode)
    w.trigger_null()
    w.show()
    sys.exit(app.exec_())
