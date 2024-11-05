from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QGraphicsSceneWheelEvent
from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent
import time
from with_nn.layout.layout import Ui_Form
import pyqtgraph
#
from usb.core import USBError
import sys
import traceback
import numpy as np
from with_nn.data_handler import DataHandler
#
from config import config, save_config

#
STANDARD_PEN = pyqtgraph.mkPen('k')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('k', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}
LABEL_TIME = 'T/sec'
LABEL_PRESSURE = 'p/kPa'
LABEL_VALUE = 'Value'
LABEL_RESISTANCE = 'Resistance/(kΩ)'
Y_LIM_INITIAL = config['y_lim']
MINIMUM_Y_LIM = 0.5
MAXIMUM_Y_LIM = 5.5
assert Y_LIM_INITIAL.__len__() == 2
assert Y_LIM_INITIAL[0] >= MINIMUM_Y_LIM - 0.5
assert Y_LIM_INITIAL[1] <= MAXIMUM_Y_LIM + 0.5


class Window(QtWidgets.QWidget, Ui_Form):

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

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self.catch_exceptions
        #
        self.data_handler = DataHandler()
        self.is_running = False
        #
        #
        self.log_y_lim = Y_LIM_INITIAL
        self.line_maximum = self.create_a_line(self.fig_0, numerical=True)
        self.line_tracing = self.create_a_line(self.fig_1, numerical=True)
        self.line_recognized = self.create_a_line(self.fig_2, numerical=False)
        self.plot = self.create_an_image(self.fig_image)
        self.pre_initialize()
        #
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        self.last_trigger_time = -0.
        #
        self.time_last_image_update = np.uint32(0)
        #

    def catch_exceptions(self, ty, value, tb):
        traceback_format = traceback.format_exception(ty, value, tb)
        traceback_string = "".join(traceback_format)
        print(traceback_string)
        QtWidgets.QMessageBox.critical(self, "错误", "{}".format(value))
        # self.old_hook(ty, value, tb)

    def dump_config(self):
        save_config()

    def start(self):
        if not self.is_running:
            flag = self.data_handler.connect(None)
            self.dump_config()
            if not flag:
                return
            self.is_running = True
            self.timer.start(self.TRIGGER_TIME)
            self.set_enable_state()

    def stop(self):
        config['y_lim'] = self.log_y_lim
        self.dump_config()
        if self.is_running:
            self.is_running = False
            if self.timer.isActive():
                self.timer.stop()
            self.data_handler.disconnect()
            self.set_enable_state()

    def pre_initialize(self):
        self.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow", "电子皮肤采集程序"))
        self.setWindowIcon(QtGui.QIcon("./with_nn/layout/tujian.ico"))
        self.initialize_image()
        self.initialize_buttons()
        self.initialize_others()
        self.set_enable_state()
        self.__apply_y_lim()
        #

    def __clicked_on_image(self, event: MouseClickEvent):
        size = [self.plot.width(), self.plot.height()]
        vb = self.plot.getView()
        vb_state = vb.state['targetRange']
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
        self.data_handler.set_tracing(xx, yy)
        print(xx, yy)
        return x, y

    def __on_mouse_wheel(self, event: QGraphicsSceneWheelEvent):
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
        colors = self.COLORS
        pos = (0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1)
        cmap = pyqtgraph.ColorMap(pos=[_ for _ in pos], color=colors)
        self.plot.setColorMap(cmap)
        vb: pyqtgraph.ViewBox = self.plot.getImageItem().getViewBox()
        vb.setMouseEnabled(x=False, y=False)
        vb.setBackgroundColor(pyqtgraph.mkColor(0.95))
        self.plot.getImageItem().scene().sigMouseClicked.connect(self.__clicked_on_image)
        self.plot.getImageItem().wheelEvent = self.__on_mouse_wheel

    def create_a_line(self, fig_widget: pyqtgraph.GraphicsLayoutWidget, numerical):
        ax: pyqtgraph.PlotItem = fig_widget.addPlot()
        ax.setLabel(axis='left', text=LABEL_RESISTANCE)
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text=LABEL_TIME)
        if numerical:
            ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                [(f'{_ ** -1: .1f}' if _ > 0. else 'INF') for _ in values]
        else:
            """设置刻度为0，1"""
            ax.getAxis('left').setTicks([[(0., '软'), (1., '硬')]])

        line: pyqtgraph.PlotDataItem = ax.plot([], [], **LINE_STYLE)
        fig_widget.setBackground('w')
        ax.getViewBox().setBackgroundColor([255, 255, 255])
        ax.getAxis('bottom').setPen(STANDARD_PEN)
        ax.getAxis('left').setPen(STANDARD_PEN)
        ax.getAxis('bottom').setTextPen(STANDARD_PEN)
        ax.getAxis('left').setTextPen(STANDARD_PEN)
        ax.getViewBox().setMouseEnabled(x=False, y=False)
        ax.hideButtons()

        return line

    def create_an_image(self, fig_widget: pyqtgraph.GraphicsLayoutWidget):
        fig_widget.setBackground(0.95)
        plot = pyqtgraph.ImageView()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(plot, 0, 0)
        fig_widget.setLayout(layout)
        plot.adjustSize()
        return plot

    @property
    def y_lim(self):
        return [10 ** (-self.log_y_lim[1]), 10 ** (-self.log_y_lim[0])]

    def __apply_y_lim(self):
        for line in [self.line_maximum, self.line_tracing]:
            line.getViewBox().setYRange(*self.y_lim)
        self.line_recognized.getViewBox().setYRange(0, 1)

    def set_enable_state(self):
        self.button_start.setEnabled(not self.is_running)
        self.button_stop.setEnabled(self.is_running)

    def __set_filter(self):
        self.data_handler.set_filter(self.combo_filter_frame.currentText(), self.combo_filter_time.currentText())
        config['filter_frame_index'] = self.combo_filter_frame.currentIndex()
        config['filter_time_index'] = self.combo_filter_time.currentIndex()
        self.dump_config()

    def initialize_buttons(self):
        self.button_start.clicked.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        self.combo_filter_frame.setCurrentIndex(config.get('filter_frame_index'))
        self.combo_filter_time.setCurrentIndex(config.get('filter_time_index'))
        self.combo_filter_frame.currentIndexChanged.connect(self.__set_filter)
        self.combo_filter_time.currentIndexChanged.connect(self.__set_filter)
        self.__set_filter()
        self.set_enable_state()
        self.button_set_zero.clicked.connect(self.data_handler.set_zero)
        self.button_abandon_zero.clicked.connect(self.data_handler.abandon_zero)

    def initialize_others(self):
        pass

    def trigger(self):
        try:
            self.data_handler.trigger()
            if self.data_handler.value:
                self.plot.setImage(np.array(self.data_handler.smoothed_value[-1].T), levels=self.y_lim)
                self.line_maximum.setData(self.data_handler.time, self.data_handler.maximum)
                self.line_tracing.setData(self.data_handler.t_tracing, self.data_handler.tracing)
                self.line_recognized.setData(self.data_handler.time, self.data_handler.recognized)
        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            self.stop()
            raise e

    def trigger_null(self):
        self.plot.setImage(np.zeros(self.data_handler.driver.SENSOR_SHAPE).T,
                           levels=self.y_lim)
        # self.plot.getImageItem().scene().sigMouseClicked.connect(self.__clicked_on_image)
        pass

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.stop()
        super(Window, self).closeEvent(a0)
        sys.exit()


def start():
    app = QtWidgets.QApplication(sys.argv)
    w = Window()
    w.show()
    w.trigger_null()
    sys.exit(app.exec_())
