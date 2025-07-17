"""
显示界面，适用于large采集卡
顺便可以给small采集卡使用
"""

from PyQt5 import QtCore, QtWidgets, QtGui
from interfaces.ordinary.layout.layout_user import Ui_MainWindow
#
from usb.core import USBError
import sys
import numpy as np
from data_processing.data_handler import DataHandler
#
from interfaces.public.utils import (set_logo,
                                     config, save_config, catch_exceptions)
from interfaces.ordinary.ordinary_plot import OrdinaryPlot
import pyqtgraph as pg
#
AVAILABLE_FILTER_NAMES = ['无', '中值-0.2s', '中值-1s', '均值-0.2s', '均值-1s', '单向抵消-轻', '单向抵消-中', '单向抵消-重']


class Window(QtWidgets.QMainWindow, Ui_MainWindow):
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
        self.config, self.save_config = config, save_config
        #
        self.is_running = False
        #
        self.data_handler = self.__mode_selector(mode)
        self.plotter = OrdinaryPlot(self)
        self.plotter.set_using_calibration()
        # 界面初始配置
        self.__pre_initialize()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        #

    def __mode_selector(self, mode):
        if mode == 'standard':
            from backends.usb_driver import LargeUsbSensorDriver
            data_handler = DataHandler(LargeUsbSensorDriver)
        else:
            raise NotImplementedError()
        return data_handler

    def _catch_exceptions(self, ty, value, tb):
        catch_exceptions(self, ty, value, tb)

    def start(self):
        # 按开始键
        if not self.is_running:
            flag = self.data_handler.connect(self.com_port.text())
            self.config['port'] = self.com_port.text()
            self.save_config()
            if not flag:
                return
            self.is_running = True
            self.timer.start(self.config['trigger_time'])
            self.__set_enable_state()
            self.com_port.setEnabled(False)

    def stop(self):
        # 按停止键
        self.config['y_lim'] = self.plotter.log_y_lim
        self.save_config()
        if self.is_running:
            self.is_running = False
            if self.timer.isActive():
                self.timer.stop()
            self.data_handler.disconnect()
            self.data_handler.clear()
            self.__set_enable_state()

    def __pre_initialize(self):
        set_logo(self)
        self.__initialize_buttons()  # 初始化一般接口
        self.__set_enable_state()  # 各类开始/停止状态切换时调用
        self.com_port.setEnabled(True)  # 一旦成功开始，就再也不能修改

    def __initialize_buttons(self):
        # 菜单栏全部关闭
        self.menubar.setEnabled(False)
        # 开始
        self.button_start.clicked.connect(self.start)
        self.action_start.triggered.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        self.action_stop.triggered.connect(self.stop)
        #
        for name in AVAILABLE_FILTER_NAMES:
            self.combo_filter_time.addItem(name)
        current_idx_filter_time = self.config.get('filter_time_index')
        if current_idx_filter_time < self.combo_filter_time.count():
            self.combo_filter_time.setCurrentIndex(current_idx_filter_time)
        self.combo_interpolate.setCurrentIndex(self.config.get('interpolate_index'))
        self.combo_blur.setCurrentIndex(self.config.get('blur_index'))
        self.__set_filter()
        self.__set_interpolate_and_blur()
        self.combo_filter_time.currentIndexChanged.connect(self.__set_filter)
        self.combo_interpolate.currentIndexChanged.connect(self.__set_interpolate_and_blur)
        self.combo_blur.currentIndexChanged.connect(self.__set_interpolate_and_blur)
        self.__set_enable_state()
        #
        self.button_set_zero.clicked.connect(self.data_handler.set_zero)
        self.action_set_zero.triggered.connect(self.data_handler.set_zero)
        self.button_abandon_zero.clicked.connect(self.data_handler.abandon_zero)
        self.action_abandon_zero.triggered.connect(self.data_handler.abandon_zero)
        self.button_save_to.clicked.connect(self.__trigger_save_button)
        self.action_save_to.triggered.connect(self.__trigger_save_button)
        self.action_save_finish.triggered.connect(self.__trigger_save_button)

        str_port = self.config.get('port')
        if not isinstance(str_port, str):
            raise Exception('配置文件出错')
        self.com_port.setText(self.config['port'])
        # 标定功能
        self.button_load_calibration.clicked.connect(self.__set_calibrator)
        self.action_load_calibration.triggered.connect(self.__set_calibrator)
        self.button_exit_calibration.clicked.connect(self.__abandon_calibrator)
        self.action_exit_calibration.triggered.connect(self.__abandon_calibrator)

    def __set_enable_state(self):
        # 根据实际的开始/停止状态，设定各按钮是否激活
        self.button_start.setEnabled(not self.is_running)
        self.action_start.setEnabled(not self.is_running)
        self.button_stop.setEnabled(self.is_running)
        self.action_stop.setEnabled(self.is_running)

        self.button_save_to.setEnabled(self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("结束采集")
        else:
            self.button_save_to.setText("采集到...")
        self.action_save_to.setEnabled(self.is_running and not self.data_handler.saving_file)
        self.action_save_finish.setEnabled(self.is_running and self.data_handler.saving_file)
        if self.is_running:
            self.com_port.setEnabled(False)

    def __set_filter(self):
        # 为self.combo_filter_time逐项添加选项
        self.data_handler.set_filter("无", self.combo_filter_time.currentText())
        self.config['filter_time_index'] = self.combo_filter_time.currentIndex()
        self.save_config()

    def __set_interpolate_and_blur(self):
        interpolate = int(self.combo_interpolate.currentText())
        blur = float(self.combo_blur.currentText())
        self.data_handler.set_interpolation_and_blur(interpolate=interpolate, blur=blur)
        self.config['interpolate_index'] = self.combo_interpolate.currentIndex()
        self.config['blur_index'] = self.combo_blur.currentIndex()
        self.save_config()

    def __set_calibrator(self):
        path = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择标定文件", "", "标定文件 (*.clb; *.csv)")[0]
        if path:
            flag = self.data_handler.set_calibrator(path)
            if flag:
                self.plotter.set_using_calibration()

    def __abandon_calibrator(self):
        self.data_handler.abandon_calibrator()
        self.plotter.set_using_calibration()

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
        self.__set_enable_state()

    def trigger(self):
        try:
            self.data_handler.trigger()
            self.plotter.trigger()
            self.console_out.setText(self.get_console_str())
        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            # self.stop()
            raise e

    def trigger_null(self):
        self.plotter.trigger_null()

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.stop()
        super(Window, self).closeEvent(a0)
        sys.exit()

    def get_console_str(self):
        if self.is_running:
            if self.data_handler.saving_file:
                ret = '采集中...'
            else:
                ret = '已连接'
                if self.data_handler.tracing_points:
                    ret += f' 追踪点 {self.data_handler.tracing_points}'
        else:
            ret = '未连接'
        return ret

def start(mode='standard'):
    app = QtWidgets.QApplication(sys.argv)
    w = Window(mode)
    w.show()
    w.trigger_null()
    sys.exit(app.exec_())
