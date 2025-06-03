"""
显示界面，适用于large采集卡
顺便可以给small采集卡使用
"""

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QGraphicsSceneWheelEvent
from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent
from interfaces.ordinary.layout.layout import Ui_Form
#
from usb.core import USBError
import sys
import numpy as np
from data_processing.data_handler import DataHandler
#
from interfaces.public.utils import (set_logo,
                                     create_a_line, create_an_image,
                                     config, save_config, catch_exceptions,
                                     apply_swap)

#
LABEL_TIME = '时间/s'
LABEL_PRESSURE = '单点力/N'
LABEL_VALUE = '值'
LABEL_RESISTANCE = '电阻/(kΩ)'
Y_LIM_INITIAL = config['y_lim']
AVAILABLE_FILTER_NAMES = ['无', '中值-0.2s', '中值-1s', '均值-0.2s', '均值-1s', '单向抵消-轻', '单向抵消-中', '单向抵消-重']

MINIMUM_Y_LIM = 0.0
MAXIMUM_Y_LIM = 5.5
assert Y_LIM_INITIAL.__len__() == 2
assert Y_LIM_INITIAL[0] >= MINIMUM_Y_LIM - 0.2
assert Y_LIM_INITIAL[1] <= MAXIMUM_Y_LIM + 0.2


def log(v):
    return np.log(np.maximum(v, 1e-6)) / np.log(10)


class Window(QtWidgets.QWidget, Ui_Form):
    """
    主窗口
    """


    def __init__(self, mode='standard'):
        """

        :param mode: "standard" or "socket"
        """
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self._catch_exceptions
        #
        self.is_running = False
        #
        self.log_y_lim = Y_LIM_INITIAL
        self.line_maximum = create_a_line(self.fig_1, LABEL_TIME, LABEL_RESISTANCE)
        self.line_tracing = create_a_line(self.fig_2, LABEL_TIME, LABEL_RESISTANCE)
        self.plot = create_an_image(self.fig_image,
                                    self.__clicked_on_image,
                                    self.__on_mouse_wheel
                                    )
        # 根据不同mode构造数据接口
        if mode == 'standard':
            from backends.usb_driver import LargeUsbSensorDriver
            self.data_handler = DataHandler(LargeUsbSensorDriver)
        elif mode == 'zw':
            from backends.usb_driver import ZWUsbSensorDriver
            self.data_handler = DataHandler(ZWUsbSensorDriver)
        elif mode == 'socket':
            from server.socket_client import SocketClient
            self.data_handler = DataHandler(SocketClient)
        elif mode == 'serial':
            from backends.serial_driver import Serial16SensorDriver
            self.data_handler = DataHandler(Serial16SensorDriver)
        elif mode == 'can':
            from backends.can_driver import Can16SensorDriver
            self.data_handler = DataHandler(Can16SensorDriver)
        elif mode == 'low_framerate':
            from backends.special_usb_driver import SimulatedLowFrameUsbSensorDriver
            self.data_handler = DataHandler(SimulatedLowFrameUsbSensorDriver)
        else:
            raise NotImplementedError()
        self.scaling = log
        self.__set_using_calibration(False)
        # 界面初始配置
        self.pre_initialize()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        #

    def _catch_exceptions(self, ty, value, tb):
        catch_exceptions(self, ty, value, tb)

    def start(self):
        # 按开始键
        if not self.is_running:
            flag = self.data_handler.connect(self.com_port.text())
            config['port'] = self.com_port.text()
            save_config()
            if not flag:
                return
            self.is_running = True
            self.timer.start(config['trigger_time'])
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
        self.initialize_buttons()
        self.set_enable_state()
        self.__apply_y_lim()
        self.com_port.setEnabled(True)  # 一旦成功开始，就再也不能修改

    def __clicked_on_image(self, event: MouseClickEvent):
        # 图上选点
        size = [self.plot.width(), self.plot.height()]
        vb = self.plot.getView()
        vb_state = vb.state['viewRange']
        pix_offset = [-size[j] / (vb_state[j][1] - vb_state[j][0]) * vb_state[j][0] for j in range(2)]
        pix_unit = [size[j] / (vb_state[j][1] - vb_state[j][0]) for j in range(2)]
        x = (event.pos().x() - pix_offset[0]) / pix_unit[0]
        y = (event.pos().y() - pix_offset[1]) / pix_unit[1]
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
        if not config['fixed_range']:
            # 当鼠标滚轮滚动时，调整图像的显示范围
            if event.delta() > 0:
                if self.log_y_lim[1] < MAXIMUM_Y_LIM:
                    self.log_y_lim = (self.log_y_lim[0] + 0.1, self.log_y_lim[1] + 0.1)
            else:
                if self.log_y_lim[0] > MINIMUM_Y_LIM:
                    self.log_y_lim = (self.log_y_lim[0] - 0.1, self.log_y_lim[1] - 0.1)
            self.log_y_lim = (round(self.log_y_lim[0], 1), round(self.log_y_lim[1], 1))
            self.__apply_y_lim()

    @property
    def y_lim(self):
        if self.data_handler.using_calibration:
            return self.data_handler.calibration_adaptor.range()
        else:
            return [-self.log_y_lim[1], -self.log_y_lim[0]]

    def __apply_y_lim(self):
        for line in [self.line_maximum, self.line_tracing]:
            line.getViewBox().setYRange(*self.y_lim)
            pass

    def __set_using_calibration(self, b):
        if b:
            for line in [self.line_maximum, self.line_tracing]:
                ax = line.get_axis()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{_: .1f}' for _ in values]
                ax.getAxis('left').label.setPlainText(LABEL_PRESSURE)
            self.scaling = lambda x: x
            self.__apply_y_lim()
        else:
            for line in [self.line_maximum, self.line_tracing]:
                ax = line.get_axis()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{10 ** (-_): .1f}' for _ in values]
                ax.getAxis('left').label.setPlainText(LABEL_RESISTANCE)
            self.scaling = log
            self.__apply_y_lim()

    def set_enable_state(self):
        # 根据实际的开始/停止状态，设定各按钮是否激活
        self.button_start.setEnabled(not self.is_running)
        self.button_stop.setEnabled(self.is_running)
        self.button_save_to.setEnabled(self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("结束采集")
        else:
            self.button_save_to.setText("采集到...")
        if self.is_running:
            self.com_port.setEnabled(False)

    def __set_filter(self):
        # 为self.combo_filter_time逐项添加选项
        self.data_handler.set_filter("无", self.combo_filter_time.currentText())
        config['filter_time_index'] = self.combo_filter_time.currentIndex()
        save_config()

    def __set_interpolate_and_blur(self):
        interpolate = int(self.combo_interpolate.currentText())
        blur = float(self.combo_blur.currentText())
        self.data_handler.set_interpolation_and_blur(interpolate=interpolate, blur=blur)
        config['interpolate_index'] = self.combo_interpolate.currentIndex()
        config['blur_index'] = self.combo_blur.currentIndex()
        save_config()

    def __set_calibrator(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, "选择标定文件", "", "标定文件 (*.csv;*.clb)")[0]
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
        for name in AVAILABLE_FILTER_NAMES:
            self.combo_filter_time.addItem(name)
        current_idx_filter_time = config.get('filter_time_index')
        if current_idx_filter_time < self.combo_filter_time.count():
            self.combo_filter_time.setCurrentIndex(current_idx_filter_time)
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

        str_port = config.get('port')
        if not isinstance(str_port, str):
            raise Exception('配置文件出错')
        self.com_port.setText(config['port'])
        # 标定功能
        self.button_load_calibration.clicked.connect(self.__set_calibrator)
        self.button_exit_calibration.clicked.connect(self.__abandon_calibrator)

    def __trigger_save_button(self):
        if self.data_handler.output_file:
            self.data_handler.close_output_file()
        else:
            file = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "选择输出路径",
                "",
                "数据库 (*.db)")
            if file[0]:
                self.data_handler.link_output_file(file[0])
        self.set_enable_state()

    def trigger(self):
        try:
            self.data_handler.trigger()
            with self.data_handler.lock:
                if self.data_handler.value:
                    self.plot.setImage(apply_swap(self.scaling(np.array(self.data_handler.value[-1].T))),
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
        self.plot.setImage(apply_swap(np.zeros(
            [_ * self.data_handler.interpolation.interp for _ in self.data_handler.driver.SENSOR_SHAPE]).T
                           - MAXIMUM_Y_LIM),
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
