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
    from interfaces.hand_shape.layout.layout_3D import Ui_Form
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
from data.preprocessing import Filter, MedianFilter, RCFilterHP
from interfaces.hand_shape.hand_plot_manager_3D import HandPlotManager

STR_CONNECTED = "Connected" if LAN == "en" else "已连接"
STR_DISCONNECTED = "Disconnected" if LAN == "en" else "未连接"

#
MINIMUM_Y_LIM = 0
MAXIMUM_Y_LIM = 4
TRIGGER_TIME_RECORD_LENGTH = 10

RESOURCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}


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
        self.hand_plot_manager = HandPlotManager(widget=self.fig_image,
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
