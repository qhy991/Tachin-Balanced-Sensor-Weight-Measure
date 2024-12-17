"""
显示界面，适用于large采集卡
顺便可以给small采集卡使用
"""

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QGraphicsSceneWheelEvent
import time
from ordinary.layout.layout_3d import Ui_Form
import pyqtgraph
import pyqtgraph.opengl as gl
#
from usb.core import USBError
import sys
import traceback
import numpy as np
from data.data_handler import DataHandler
from large.sensor_driver import LargeSensorDriver
#
from config import config, save_config
from scipy.interpolate import interp1d


def create_color_map(data):
    # Normalize data to range [0, 1]

    # Create a colormap using NumPy
    colors = np.array([
        [15, 15, 15],
        [48, 18, 59],
        [71, 118, 238],
        [27, 208, 213],
        [97, 252, 108],
        [210, 233, 53],
        [254, 155, 45],
        [218, 57, 7],
        [122, 4, 3]
    ]) / 255.0
    # Interpolate colors
    # indices = (data * (colors.shape[0] - 1)).astype(int)
    # 改成插值
    interps = [interp1d(np.linspace(0., 1., colors.shape[0]), colors[:, j], axis=0, bounds_error=False)
               for j in range(3)]
    return np.stack([interp(data) for interp in interps], axis=-1)


#
STANDARD_PEN = pyqtgraph.mkPen('k')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('k', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}
LABEL_TIME = 'T/sec'
LABEL_PRESSURE = 'p/kPa'
LABEL_VALUE = 'Value'
LABEL_RESISTANCE = 'Resistance/(kΩ)'
Y_LIM_INITIAL = config['y_lim']
DISPLAY_RANGE = [[24, 40], [24, 40]]
MINIMUM_Y_LIM = 0.0
MAXIMUM_Y_LIM = 5.0
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
    COLORS = [[15, 15, 15],
              [48, 18, 59],
              [71, 118, 238],
              [27, 208, 213],
              [97, 252, 108],
              [210, 233, 53],
              [254, 155, 45],
              [218, 57, 7],
              [122, 4, 3]]

    def __init__(self, mode='direct', fixed_range=False):
        """

        :param mode: "direct" or "socket"
        """
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self.catch_exceptions
        #
        if mode == 'direct':
            self.data_handler = DataHandler(UsbSensorDriver)
        elif mode == 'socket':
            self.data_handler = DataHandler(SocketClient)
        else:
            raise NotImplementedError()
        self.fixed_range = fixed_range
        self.is_running = False
        # 绘图用固定坐标
        # xx = np.arange(self.data_handler.driver.SENSOR_SHAPE[0] * self.data_handler.interpolation.interp)
        xx = np.arange((DISPLAY_RANGE[0][1] - DISPLAY_RANGE[0][0]) * self.data_handler.interpolation.interp)
        xx = xx / xx.shape[0] - 0.5
        # yy = np.arange(self.data_handler.driver.SENSOR_SHAPE[1] * self.data_handler.interpolation.interp)
        yy = np.arange((DISPLAY_RANGE[1][1] - DISPLAY_RANGE[1][0]) * self.data_handler.interpolation.interp)
        yy = yy / yy.shape[0] - 0.5
        self.xx, self.yy = xx, yy
        self.log_y_lim = Y_LIM_INITIAL
        self._using_calibration = False
        self.plot = self.create_3d_plot(self.fig_image)
        self.pre_initialize()
        #
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        self.last_trigger_time = -0.
        #
        self.time_last_image_update = np.uint32(0)
        # 是否处于使用标定状态
        self.scaling = log
        # 绘图用
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
        self.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow", "电子皮肤采集程序"))
        self.setWindowIcon(QtGui.QIcon("./ordinary/layout/tujian.ico"))
        self.initialize_image()
        self.initialize_buttons()
        self.initialize_others()
        self.set_enable_state()
        self.__apply_y_lim()

    def create_3d_plot(self, fig_widget: QtWidgets.QWidget):
        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(pos=QtGui.QVector3D(0.64, 0.77, 0.5), distance=0.3, elevation=30, azimuth=50)
        self.grid = gl.GLGridItem()
        self.view.addItem(self.grid)
        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.view, 0, 0)
        fig_widget.setLayout(layout)
        return self.view

    def initialize_image(self):
        self.view.clear()
        self.grid = gl.GLGridItem()
        self.view.addItem(self.grid)

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

    @property
    def y_lim(self):
        # 这里经常改
        # return [10 ** (-self.log_y_lim[1]), 10 ** (-self.log_y_lim[0])]
        if self._using_calibration:
            return [0, 5.]
        else:
            return [-self.log_y_lim[1], -self.log_y_lim[0]]

    def __apply_y_lim(self):
        # for line in [self.line_maximum, self.line_tracing]:
        #     line.getViewBox().setYRange(*self.y_lim)
        #     pass
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
        self.button_save_to.setEnabled(self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("结束采集")
        else:
            self.button_save_to.setText("采集到...")
        if self.data_handler.driver.__class__.__name__ in \
                ['FakeSensorDriver', 'SmallSensorDriver', 'SocketClient', 'LargeSensorDriver']:
            self.com_port.setEnabled(not self.is_running)
        else:
            self.com_port.setEnabled(False)
            self.com_port.setText("-")

    def __set_filter(self):
        # self.data_handler.set_filter("无", self.combo_filter_time.currentText())
        # config['filter_time_index'] = self.combo_filter_time.currentIndex()
        self.dump_config()

    def __set_interpolate_and_blur(self):
        # interpolate = int(self.combo_interpolate.currentText())
        # blur = float(self.combo_blur.currentText())
        self.data_handler.set_interpolation_and_blur(interpolate=1, blur=2)
        # config['interpolate_index'] = self.combo_interpolate.currentIndex()
        # config['blur_index'] = self.combo_blur.currentIndex()
        self.dump_config()

    def __set_calibrator(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, "选择标定文件", "", "标定文件 (*.csv)")[0]
        if path:
            flag = self.data_handler.set_calibrator(path)
            if flag:
                self.__set_using_calibration(True)

    def __abandon_calibrator(self):
        self.data_handler.abandon_calibrator()
        self.__set_using_calibration(False)

    def initialize_buttons(self):
        self.button_start.clicked.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        # self.combo_filter_time.setCurrentIndex(config.get('filter_time_index'))
        # self.combo_interpolate.setCurrentIndex(config.get('interpolate_index'))
        # self.combo_blur.setCurrentIndex(config.get('blur_index'))
        self.__set_filter()
        self.__set_interpolate_and_blur()
        # self.combo_filter_time.currentIndexChanged.connect(self.__set_filter)
        # self.combo_interpolate.currentIndexChanged.connect(self.__set_interpolate_and_blur)
        # self.combo_blur.currentIndexChanged.connect(self.__set_interpolate_and_blur)
        self.set_enable_state()
        self.button_set_zero.clicked.connect(self.data_handler.set_zero)
        self.button_abandon_zero.clicked.connect(self.data_handler.abandon_zero)
        self.button_save_to.clicked.connect(self.__trigger_save_button)
        # 标定功能
        # self.button_load_calibration.clicked.connect(self.__set_calibrator)
        # self.button_exit_calibration.clicked.connect(self.__abandon_calibrator)

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

    def __set_xy_range(self):
        interp = self.data_handler.interpolation.interp
        x_range = [DISPLAY_RANGE[0][0] * interp - 0.5, (DISPLAY_RANGE[0][1] - 1) * interp - 0.5]
        y_range = [DISPLAY_RANGE[1][0] * interp - 0.5, (DISPLAY_RANGE[1][1] - 1) * interp - 0.5]
        self.plot.getView().setRange(xRange=x_range,
                                     yRange=y_range)

    MESH_PLOT_STYLE = {
        'shader': 'shaded',
                       'glOptions': 'additive',
                        'smooth': True,
        'drawEdges': True,
        'edgeColor': (1, 1, 1, 0.01),
                       }
    # 设置上色、光源

    def trigger(self):
        try:
            self.data_handler.trigger()
            time_now = time.time()
            if self.data_handler.value and time_now < self.last_trigger_time + self.TRIGGER_TIME:
                self.view.clear()

                Z = log(np.array(self.data_handler.smoothed_value[-1]))
                Z = Z[DISPLAY_RANGE[0][0] : DISPLAY_RANGE[0][1], DISPLAY_RANGE[1][0] : DISPLAY_RANGE[1][1]]
                Z = (np.clip(Z, min(self.y_lim), max(self.y_lim)) - min(self.y_lim)) / (max(self.y_lim) - min(self.y_lim))
                colors = create_color_map(Z)
                self.surface = gl.GLSurfacePlotItem(x=-self.xx, y=self.yy, z=Z * 0.05, colors=colors[:, :, :3], **self.MESH_PLOT_STYLE)
                # self.surface = gl.GLSurfacePlotItem(x=X, y=Y, z=Z * 0.1, **self.MESH_PLOT_STYLE)

                self.view.addItem(self.surface)
            self.last_trigger_time = time_now
        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            self.stop()
            raise e

    def trigger_null(self):
        self.view.clear()
        Z = np.zeros([int(_ * self.data_handler.interpolation.interp) for _ in self.data_handler.driver.SENSOR_SHAPE])
        Z = Z[DISPLAY_RANGE[0][0]: DISPLAY_RANGE[0][1], DISPLAY_RANGE[1][0]: DISPLAY_RANGE[1][1]]
        colors = create_color_map(Z)
        self.surface = gl.GLSurfacePlotItem(x=-self.xx, y=self.yy, z=Z * 0.1, colors=colors[:, :, :3], **self.MESH_PLOT_STYLE)
        self.view.addItem(self.surface)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.stop()
        super(Window, self).closeEvent(a0)
        sys.exit()


def start(mode='direct'):
    app = QtWidgets.QApplication(sys.argv)
    w = Window(mode)
    w.show()
    w.trigger_null()
    sys.exit(app.exec_())
