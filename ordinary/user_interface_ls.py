"""
显示界面，适用于LS采集卡
"""

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QGraphicsSceneWheelEvent
from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent
import time
from ordinary.layout.layout import Ui_Form
import pyqtgraph
#
from usb.core import USBError
import sys
import traceback
import numpy as np
from data.data_handler_ls import DataHandler
#
from config import config, save_config

#
STANDARD_PEN = pyqtgraph.mkPen('k')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('k', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}
LABEL_TIME = 'T/sec'
LABEL_PRESSURE = 'p/kPa'
LABEL_VALUE = 'Value'
Y_LIM_INITIAL = config['y_lim']
MINIMUM_Y_LIM = 0.5
MAXIMUM_Y_LIM = 5.5
assert Y_LIM_INITIAL.__len__() == 2
assert Y_LIM_INITIAL[0] >= MINIMUM_Y_LIM - 0.5
assert Y_LIM_INITIAL[1] <= MAXIMUM_Y_LIM + 0.5


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

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self.catch_exceptions
        #
        self.data_handler = DataHandler()
        self.is_running = False
        #
        self.log_y_lim = Y_LIM_INITIAL
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
        #

    def catch_exceptions(self, ty, value, tb):
        # 错误重定向为弹出对话框
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
        self.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow", "大阵列电子皮肤采集程序"))
        self.setWindowIcon(QtGui.QIcon("./ordinary/layout/tujian.ico"))
        self.initialize_image()
        self.initialize_buttons()
        self.initialize_others()
        self.set_enable_state()
        self.__apply_y_lim()
        #

    def __clicked_on_image(self, event: MouseClickEvent):
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
            if self.data_handler.value:
                v_point = self.data_handler.value[-1][xx, yy] ** -1
                print(xx, yy, round(v_point, 1))
            else:
                print(xx, yy)

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

    def create_a_line(self, fig_widget: pyqtgraph.GraphicsLayoutWidget):
        ax: pyqtgraph.PlotItem = fig_widget.addPlot()
        ax.setLabel(axis='left', text=LABEL_VALUE)
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text=LABEL_TIME)

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
        return 0, 256 * 4 - 1

    def __apply_y_lim(self):
        for line in [self.line_maximum, self.line_tracing]:
            line.getViewBox().setYRange(*self.y_lim)

    def set_enable_state(self):
        # 根据实际的开始/停止状态，设定各按钮是否激活
        self.button_start.setEnabled(not self.is_running)
        self.button_stop.setEnabled(self.is_running)
        self.button_save_to.setEnabled(self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("结束采集")
        else:
            self.button_save_to.setText("采集到...")
        if self.data_handler.driver.__class__.__name__ in ['FakeSensorDriver', 'SmallSensorDriver']:
            self.com_port.setEnabled(not self.is_running)
        else:
            self.com_port.setEnabled(False)
            self.com_port.setText("-")

    def __set_filter(self):
        self.data_handler.set_filter("无", self.combo_filter_time.currentText())
        config['filter_time_index'] = self.combo_filter_time.currentIndex()
        self.dump_config()

    def __set_interpolate_and_blur(self):
        interpolate = int(self.combo_interpolate.currentText())
        blur = float(self.combo_blur.currentText())
        self.data_handler.set_interpolation_and_blur(interpolate=interpolate, blur=blur)
        config['interpolate_index'] = self.combo_interpolate.currentIndex()
        config['blur_index'] = self.combo_blur.currentIndex()
        self.dump_config()

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

    def __trigger_save_button(self):
        if self.data_handler.output_file:
            self.data_handler.close_output_file()
            print('结束采集')
        else:
            file = QtWidgets.QFileDialog.getSaveFileName(
                self, "选择输出路径", "", "数据库 (*.db)")
            if file[0]:
                self.data_handler.link_output_file(file[0])
                print(f'开始向{file[0]}采集')
        self.set_enable_state()

    def initialize_others(self):
        str_port = config.get('port')
        if not isinstance(str_port, str):
            raise Exception('配置文件出错')
        self.com_port.setText(config['port'])

    def trigger(self):
        try:
            self.data_handler.trigger()
            time_now = time.time()
            if self.data_handler.value and time_now < self.last_trigger_time + self.TRIGGER_TIME:
                self.plot.setImage(np.maximum(np.array(self.data_handler.smoothed_value[-1].T - 0), 0),
                                   levels=self.y_lim)
                self.line_maximum.setData(self.data_handler.time, self.data_handler.maximum)
                self.line_tracing.setData(self.data_handler.t_tracing, self.data_handler.tracing)
            self.last_trigger_time = time_now
        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            self.stop()
            raise e

    def trigger_null(self):
        self.plot.setImage(np.zeros(self.data_handler.driver.SENSOR_SHAPE).T,
                           levels=self.y_lim)

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
