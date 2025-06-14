
import numpy as np
from interfaces.public.utils import create_a_line, create_an_image, apply_swap, config
from PyQt5.QtWidgets import QGraphicsSceneWheelEvent
from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent
import pyqtgraph as pg

LABEL_TIME = '时间/s'
LABEL_PRESSURE = '单点力/N'
LABEL_FORCE = '总力/N'
LABEL_VALUE = '值'
LABEL_RESISTANCE = '电阻/(kΩ)'
MINIMUM_Y_LIM = 0.0
MAXIMUM_Y_LIM = 5.0

def log(v):
    return np.log(np.maximum(v, 1e-7)) / np.log(10)

class OrdinaryPlot:

    def __init__(self, window):
        self.window = window
        self.data_handler = window.data_handler

        self.log_y_lim = self.window.config['y_lim']
        self.line_maximum = create_a_line(window.fig_1, LABEL_TIME, LABEL_RESISTANCE)
        self.line_tracing = create_a_line(window.fig_2, LABEL_TIME, LABEL_RESISTANCE)
        self.plot = create_an_image(window.fig_image,
                                    self.__clicked_on_image,
                                    self.__on_mouse_wheel
                                    )
        self.scaling = log

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
    def __y_lim(self):
        if self.data_handler.using_calibration:
            return self.data_handler.calibration_adaptor.range()
        else:
            return [-self.log_y_lim[1], -self.log_y_lim[0]]

    def __apply_y_lim(self):
        for line in [self.line_maximum, self.line_tracing]:
            if not (line is self.line_maximum and self.data_handler.using_calibration):
                line.getViewBox().setYRange(*self.__y_lim)

    def update_plot(self, scaling, data_handler, y_lim):
        self.plot.setImage(apply_swap(scaling(np.array(data_handler.value[-1].T))), levels=y_lim)
        if data_handler.using_calibration:
            self.line_maximum.setData(data_handler.time, scaling(data_handler.summed))
        else:
            self.line_maximum.setData(data_handler.time, scaling(data_handler.maximum))
        self.line_tracing.setData(data_handler.t_tracing, scaling(data_handler.tracing))

    def trigger_null(self):
        self.plot.setImage(apply_swap(np.zeros(
            [_ * self.data_handler.interpolation.interp for _ in self.data_handler.driver.SENSOR_SHAPE]).T - MAXIMUM_Y_LIM),
            levels=self.__y_lim)

    def set_using_calibration(self):
        if self.data_handler.using_calibration:
            for line in [self.line_maximum, self.line_tracing]:
                ax = line.get_axis()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{_: .2f}' for _ in values]
                ax.getAxis('left').label.setPlainText(LABEL_PRESSURE)
                # 特殊处理：改为总力
                if line is self.line_maximum:
                    ax.getAxis('left').label.setPlainText(LABEL_FORCE)
                    self.window.label_maximum.setText("总值")
                    ax.getViewBox().setYRange(0, 0.1)
                    ax.enableAutoRange(axis=pg.ViewBox.YAxis)
            self.scaling = lambda x: x
            self.__apply_y_lim()
        else:
            for line in [self.line_maximum, self.line_tracing]:
                ax = line.get_axis()
                ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                    [f'{10 ** (-_): .1f}' for _ in values]
                ax.getAxis('left').label.setPlainText(LABEL_RESISTANCE)
                if ax is self.line_maximum:
                    self.window.setText("峰值")
                    ax.getViewBox().setYRange(-MAXIMUM_Y_LIM, -MINIMUM_Y_LIM)
            self.scaling = log
            self.__apply_y_lim()

    def trigger(self):
        self.data_handler.trigger()
        with self.data_handler.lock:
            if self.data_handler.value:
                self.plot.setImage(apply_swap(self.scaling(np.array(self.data_handler.value[-1].T))),
                                   levels=self.__y_lim)
                if self.data_handler.using_calibration:
                    self.line_maximum.setData(self.data_handler.time, self.scaling(self.data_handler.summed))
                else:
                    self.line_maximum.setData(self.data_handler.time, self.scaling(self.data_handler.maximum))
                self.line_tracing.setData(self.data_handler.t_tracing, self.scaling(self.data_handler.tracing))
