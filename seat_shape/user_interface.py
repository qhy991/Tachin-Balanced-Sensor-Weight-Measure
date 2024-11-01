"""
显示界面，适用于large采集卡
顺便可以给small采集卡使用
"""
import copy
import threading
import warnings

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QGraphicsSceneWheelEvent
from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent
import time
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtGui import QColor
from seat_shape.layout.layout import Ui_Form
import pyqtgraph
#
from usb.core import USBError
import sys
import traceback
import numpy as np
from ordinary.data_handler_multiple import DataHandler
from large.sensor_driver import LargeSensorDriver
#
from config import config, save_config, config_multiple, config_void_list
from ordinary.convert_data import ReplayDataSource

#
STANDARD_PEN = pyqtgraph.mkPen('k')
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('k', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}
LABEL_TIME = 'T/sec'
LABEL_PRESSURE = 'p/kPa'
LABEL_VALUE = 'Value'
LABEL_RESISTANCE = 'Resistance/(kΩ)'
Y_LIM_INITIAL = config['y_lim']
DISPLAY_SHAPES = [[32, 17], [32, 15], [8, 8]]
MINIMUM_Y_LIM = 0.0
MAXIMUM_Y_LIM = 5.0
assert Y_LIM_INITIAL.__len__() == 2
assert Y_LIM_INITIAL[0] >= MINIMUM_Y_LIM - 0.5
assert Y_LIM_INITIAL[1] <= MAXIMUM_Y_LIM + 0.5

color = [pyqtgraph.intColor(i_cycle,
                            config_multiple['tracing_list'].__len__() * 1.5,
                            maxValue=127 + 64) for i_cycle in range(config_multiple['tracing_list'].__len__())]

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

    def __init__(self, fixed_range=False):
        super().__init__()
        self.setupUi(self)
        # 重定向提示
        sys.excepthook = self.catch_exceptions
        #
        self.data_handler = DataHandler(LargeSensorDriver, ports=config_multiple['ports'], max_len=64)
        self.fixed_range = fixed_range
        self.is_running = False
        #
        self.log_y_lim = Y_LIM_INITIAL
        self._using_calibration = False
        self._using_replay = False
        self.plots = [self.create_an_image(fig_image_x)
                      for fig_image_x in [self.fig_image_0, self.fig_image_1, self.fig_image_2]]
        self.plot_lines = self.create_lines(self.fig_lines,
                                            [str(_) for _ in config_multiple['tracing_names']],
                                            color)
        self.i_plot_to_slice_to_i_driver_and_slice = [
            (0, (slice(0, 32), slice(0, 17)), 0, (slice(31, None, -1), slice(16, None, -1))),
            (1, (slice(0, 32), slice(0, 15)), 0, (slice(31, None, -1), slice(31, 16, -1))),
            (2, (slice(0, 8), slice(0, 8)), 1, (slice(19, 11, -1), slice(12, 20))),
        ]
        self.pre_initialize()
        #
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger)
        self.last_trigger_time = -0.
        #
        self.time_last_image_update = np.uint32(0)
        #
        # self.scaling = log
        self.scaling = lambda x: x

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
            if self._using_replay:
                self.replay_data.reset()
            else:
                flag = self.data_handler.connect(None)
                if not flag:
                    return
            self.is_running = True
            self.timer.start(self.TRIGGER_TIME)
            self.set_enable_state()
            # self.com_port.setEnabled(False)

    def stop(self):
        # 按停止键
        self._using_replay = False
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
        self._plot_gray_all()
        self.__apply_y_lim()
        #

    def __clicked_on_image(self, event: MouseClickEvent):
        pass

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
        for plot in self.plots:
            plot.ui.histogram.hide()
            plot.ui.menuBtn.hide()
            plot.ui.roiBtn.hide()
            #
            colors = self.COLORS
            pos = (0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1)
            cmap = pyqtgraph.ColorMap(pos=[_ for _ in pos], color=colors)
            plot.setColorMap(cmap)
            vb: pyqtgraph.ViewBox = plot.getImageItem().getViewBox()
            vb.setMouseEnabled(x=False, y=False)
            vb.setBackgroundColor(pyqtgraph.mkColor(0.95))
            plot.getImageItem().scene().sigMouseClicked.connect(self.__clicked_on_image)
            plot.getImageItem().wheelEvent = self.__on_mouse_wheel
            # 设置范围
            self.__set_xy_range()

    def create_lines(self, fig_widget: pyqtgraph.GraphicsLayoutWidget, legends, colors):
        ax: pyqtgraph.PlotItem = fig_widget.addPlot()
        ax.setLabel(axis='left', text=LABEL_RESISTANCE)
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text=LABEL_TIME)
        # ax.getAxis('left').tickStrings = lambda values, scale, spacing:\
        #     [(f'{_ ** -1: .1f}' if _ > 0. else 'INF') for _ in values]
        ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                [f'{10 ** (-_): .1f}' for _ in values]
        lines = []
        legend = ax.addLegend(colCount=5)
        for i_line in range(config_multiple['tracing_list'].__len__()):
            line_style = LINE_STYLE.copy()
            line_style.update({'pen': pyqtgraph.mkPen(colors[i_line])})
            # marker也用这个颜色
            line_style.update({'symbolBrush': colors[i_line]})
            line: pyqtgraph.PlotDataItem = ax.plot([], [], name=legends[i_line], **line_style)
            line.get_axis = lambda: ax
            lines.append(line)

        fig_widget.setBackground('w')
        ax.getViewBox().setBackgroundColor([255, 255, 255])
        ax.getAxis('bottom').setPen(STANDARD_PEN)
        ax.getAxis('left').setPen(STANDARD_PEN)
        ax.getAxis('bottom').setTextPen(STANDARD_PEN)
        ax.getAxis('left').setTextPen(STANDARD_PEN)
        ax.getViewBox().setMouseEnabled(x=False, y=False)
        ax.hideButtons()
        return lines

    @property
    def y_lim(self):
        # 这里经常改
        # return [10 ** (-self.log_y_lim[1]), 10 ** (-self.log_y_lim[0])]
        if self._using_calibration:
            return [0, 5.]
        else:
            return [self.scaling(_) for _ in [10 ** (-self.log_y_lim[1]), 10 ** (-self.log_y_lim[0])]]

    def __apply_y_lim(self):
        try:
            self.plot_lines[0].getViewBox().setYRange(*self.y_lim)
        except:
            pass
        pass

    def __set_using_calibration(self, b):
        if b:
            self._using_calibration = True
            for line in self.plot_lines:
                ax = line.get_axis()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{_: .1f}' for _ in values]
            self.__apply_y_lim()
        else:
            self._using_calibration = False
            for line in self.plot_lines:
                ax = line.getViewBox()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{10 ** (-_): .1f}' for _ in values]
            self.__apply_y_lim()

    def __set_using_replay(self, b):
        if self.is_running:
            return False
        self._using_replay = b
        return True

    def __control_replay(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, "选择回放文件", "", "数据库 (*.db)")[0]
        if path:
            self.replay_data = ReplayDataSource()
            self.replay_data.connect(path)
            flag = self.__set_using_replay(True)
            if not flag:
                raise Exception('正在采集中，无法进入回放模式')
            else:
                self.plot_lines.clear()
                for fig in [self.fig_image_0, self.fig_image_1, self.fig_image_2]:
                    fig.clear()

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
        self.button_save_to.setEnabled(self.is_running and not self._using_replay)
        self.button_replay.setEnabled(not self.is_running)
        if self.data_handler.output_file:
            self.button_save_to.setText("结束采集")
        else:
            self.button_save_to.setText("采集到...")
        self.replay_time.setEnabled(self.is_running and self._using_replay)
        self.button_replay_goto.setEnabled(self.is_running and self._using_replay)

    def __set_filter(self):
        pass

    def __set_interpolate_and_blur(self):
        self.data_handler.set_interpolation_and_blur(interpolate=1, blur=0.)
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

    def __set_replay_progress(self):
        self.replay_data.reset(float(self.replay_time.text()))

    def initialize_buttons(self):
        self.button_start.clicked.connect(self.start)
        self.button_stop.clicked.connect(self.stop)
        self.__set_filter()
        self.__set_interpolate_and_blur()
        self.set_enable_state()
        self.button_set_zero.clicked.connect(self.data_handler.set_zero)
        self.button_abandon_zero.clicked.connect(self.data_handler.abandon_zero)
        self.button_save_to.clicked.connect(self.__trigger_save_button)
        # 标定功能
        self.button_load_calibration.clicked.connect(self.__set_calibrator)
        self.button_exit_calibration.clicked.connect(self.__abandon_calibrator)
        #
        self.button_replay.clicked.connect(self.__control_replay)
        self.button_replay_goto.clicked.connect(self.__set_replay_progress)

    def _plot_gray_all(self):
        pass
        # for i_device, void_list in config_void_list.items():
        #     for area in void_list:
        #         self._plot_gray_one(int(i_device), *[_ for _ in area['y']], *area['x'])
        # pass

    def _plot_gray_one(self, i_plot, x_start, x_stop, y_start, y_stop):
        # 在对应的图号上的区域，增添一个灰色
        # 创建一个灰色区域
        gray_area = QGraphicsRectItem(x_start, y_start, x_stop - x_start, y_stop - y_start)
        gray_area.setBrush(QColor(128, 128, 128, 128))  # 设置灰色和透明度
        gray_area.setPen(pyqtgraph.mkPen(None))  # 去掉边框
        # 将灰色区域添加到 ImageItem 的父级中
        self.plots[i_plot].addItem(gray_area)


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
        # str_port = config_multiple.get('ports')
        # if not isinstance(str_port, str):
        #     raise Exception('配置文件出错')
        # self.com_port.setText(config['port'])
        pass

    def __set_xy_range(self):
        pass

    def trigger(self):
        try:
            time_now = time.time()
            if self._using_replay:
                rep = self.replay_data.get_data()
                if rep.__len__() >= 2:
                    values_smoothed = [[rep[0]] if rep[0] is not None else [], [rep[1]] if rep[1] is not None else []]
                else:
                    warnings.warn("DEBUG")
                    values_smoothed = [[rep[0]] if rep[0] is not None else [], [rep[0]] if rep[0] is not None else []]
            else:
                self.data_handler.trigger()
                values_smoothed = copy.deepcopy(self.data_handler.values_smoothed)
                self.data_handler.lock.acquire()
                t_tracing = copy.deepcopy(self.data_handler.tracing_t)
                values_tracing = copy.deepcopy(self.data_handler.tracing_points)
                self.data_handler.lock.release()
                for i in range(config_multiple['tracing_list'].__len__()):
                    assert t_tracing[i].__len__() == values_tracing[i].__len__()

                for i_l, line in enumerate(self.plot_lines):
                    try:
                        line.setData(t_tracing[i_l], self.scaling(values_tracing[i_l]))
                    except:
                        pass
            if all([bool(_) for _ in values_smoothed]):
                for i_plot, plot in enumerate(self.plots):
                    data_to_plot = np.zeros(DISPLAY_SHAPES[i_plot])
                    for mapping in self.i_plot_to_slice_to_i_driver_and_slice:
                        i_plot_, slice_plot_, i_driver_, slice_driver_ = mapping
                        if i_plot_ == i_plot:
                            data_to_plot[slice_plot_] = values_smoothed[i_driver_][-1][slice_driver_]
                    if not self._using_calibration:
                        data_to_plot = self.scaling(data_to_plot)
                    plot.setImage(data_to_plot.T,
                                  levels=self.y_lim)
                self._plot_gray_all()
                self.__set_xy_range()
                self.last_trigger_time = time_now
        except USBError:
            self.stop()
            QtWidgets.qApp.quit()
        except Exception as e:
            self.stop()
            raise e

    def trigger_null(self):
        for i_plot, plot in enumerate(self.plots):
            plot.setImage(np.zeros(DISPLAY_SHAPES[i_plot]).T - MAXIMUM_Y_LIM,
                          levels=self.y_lim)
        self._plot_gray_all()
        self.__set_xy_range()

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


if __name__ == '__main__':
    start()
