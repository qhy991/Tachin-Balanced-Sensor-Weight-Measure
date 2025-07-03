"""
手形界面（3D版）
"""
LAN = 'chs'
import threading
import time
import numpy as np
from PIL import Image, ImageDraw
from collections import deque
import pyqtgraph
from pyqtgraph.opengl import GLViewWidget, GLGridItem, GLLinePlotItem, GLSurfacePlotItem
from data_processing.preprocessing import MedianFilter
from interfaces.hand_shape.feature_extractor import FingerFeatureExtractor
from data_processing.interpolation import Interpolation
from utils.performance_monitor import Ticker
from PyQt5.QtGui import QWheelEvent
from PyQt5 import QtWidgets
from data_processing.data_handler import DataHandler
from config import config, save_config, get_config_mapping
from scipy.interpolate import interp1d

legend_color = lambda i: pyqtgraph.intColor(i, 16 * 1.5, maxValue=127 + 64)
STANDARD_PEN = pyqtgraph.mkPen('k')

MESH_PLOT_STYLE = {
    # 'shader': 'shaded',
    'glOptions': 'additive',
    # 'smooth': True,
    'drawEdges': True,
    'edgeColor': (1, 1, 1, 0.05),
}


# 设置上色、光源


class HandPlotManager:

    def __init__(self,
                 widget: QtWidgets.QWidget,
                 fig_widget_1d: pyqtgraph.GraphicsLayoutWidget,
                 data_handler: DataHandler,
                 config_mapping, image,
                 downsample=1):
        # 配置
        self.cmap = pyqtgraph.ColorMap(np.linspace(0, 1, 17), (np.array(config_mapping['color_map']) * 255).astype(int))
        pixel_mapping = config_mapping['pixel_mapping']
        range_mapping = config_mapping['range_mapping']
        self.is_left_hand = config_mapping['is_left_hand']
        self.arrow_offset = config_mapping.get('arrow_offset', None)
        self.log_y_lim = (config['y_lim'][0], config['y_lim'][1])
        # 数据源
        self.dd = data_handler
        # 3D场景
        self.gl_widget = GLViewWidget()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.gl_widget, 0, 0)
        widget.setLayout(layout)
        self.gl_widget.setBackgroundColor('k')
        self.gl_widget.setCameraPosition(
            azimuth=44.0,
            elevation=43.0,
            distance=8.
        )
        self.gl_widget.mouseReleaseEvent = self._on_mouse_release
        # 区域划分
        rects = {
            int(k): [(pixel_mapping[str(k)][0],
                      pixel_mapping[str(k)][1]),
                     (pixel_mapping[str(k)][2],
                      pixel_mapping[str(k)][3]),
                     True,
                     np.zeros((range_mapping[k][6], range_mapping[k][5])
                              if range_mapping[k][4]
                              else (range_mapping[k][5], range_mapping[k][6])),
                     int(k)]
            for k in range_mapping.keys()
        }
        # 分区投影函数
        self.mesh_functions = {
            int(k): self.make_mesh_function(rects[int(k)]) for k in pixel_mapping.keys()
        }
        # 表面
        self.surface_plots = {}
        self.meshes = {int(k): self.mesh_functions[int(k)](np.zeros((range_mapping[k][5], range_mapping[k][6])))
                            for k in pixel_mapping.keys()}
        for k, mesh in self.meshes.items():
            surface_plot = GLSurfacePlotItem(
                x=mesh['x'] / 100.,
                y=mesh['y'] / 100.,
                z=mesh['z'] * 0.,
                computeNormals=False,
                colors=create_color_map(mesh['z'] * 0.),
                **MESH_PLOT_STYLE
            )
            self.gl_widget.addItem(surface_plot)
            self.surface_plots.update({int(k): surface_plot})
        # 箭头
        # if self.arrow_offset is not None:
        #     for k, mesh in self.meshes.items():
        #         arrow_plot = GLLinePlotItem(
        #             mesh['x'] / 100.,
        #             mesh['y'] / 100.,
        #             mesh['z'] * 0.,
        #             color=(1, 1, 1, 0.5),
        #             width=2,
        #             antialias=True,
        #         )
        #         self.gl_widget.addItem(arrow_plot)
        #         self.surface_plots.update({int(k): arrow_plot})

        # 曲线图
        ax: pyqtgraph.PlotItem = fig_widget_1d.addPlot()
        ax.setLabel(axis='left', text='Contact strength' if LAN == "en" else '接触强度')
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text='Time (s)' if LAN == "en" else '时间 (s)')
        ax.getViewBox().setYRange(0, 256)
        fig_widget_1d.setBackground('w')
        ax.getViewBox().setBackgroundColor([255, 255, 255])
        ax.getAxis('bottom').setPen(STANDARD_PEN)
        ax.getAxis('left').setPen(STANDARD_PEN)
        ax.getAxis('bottom').setTextPen(STANDARD_PEN)
        ax.getAxis('left').setTextPen(STANDARD_PEN)
        ax.getViewBox().setMouseEnabled(x=False, y=False)
        ax.getViewBox().setMenuEnabled(False)
        ax.hideButtons()
        ax.addLegend(colCount=3)
        self.ax = ax
        self.lines = {int(idx): ax.plot(pen=pyqtgraph.mkPen(legend_color(idx), width=2),
                                        name=config_mapping['names'][idx])
                      for idx in range_mapping.keys()}
        # 存储
        self.filters = {int(idx): MedianFilter({'SENSOR_SHAPE': (1, 1), 'DATA_TYPE': float}, 2)
                        for idx in range_mapping.keys()}
        max_len = self.dd.max_len
        self.region_max = {int(idx): deque(maxlen=max_len) for idx in range_mapping.keys()}
        self.region_x_diff = {int(idx): deque(maxlen=max_len) for idx in range_mapping.keys()}
        self.region_y_diff = {int(idx): deque(maxlen=max_len) for idx in range_mapping.keys()}
        self.time = deque(maxlen=max_len)
        #
        #
        self.lock = threading.Lock()
        #
        threading.Thread(target=self.process_forever, daemon=True).start()
        #
        # self.img_view.resizeEvent = self.resize_event  # 换成三维场景的
        # self.resize_transform = []  # 包括了缩放的比例和偏移量
        # 计算用
        self.finger_feature_extractors = {int(k): FingerFeatureExtractor(15, 4, 0.995, 10., 1.0)
                                          for k in config_mapping['range_mapping'].keys()}

    def clear(self):
        with self.lock:
            for idx in self.lines.keys():
                self.region_max[idx].clear()
                self.region_x_diff[idx].clear()
                self.region_y_diff[idx].clear()
            self.time.clear()

    @staticmethod
    def make_mask(shape, scale=1.):
        x_coord = np.abs(np.arange(shape[0]) - shape[0] // 2 + 0.5)
        y_coord = np.abs(np.arange(shape[1]) - shape[1] // 2 + 0.5)
        dist_sq = ((x_coord.reshape(-1, 1)) / shape[0] * 2) ** 3 + ((y_coord.reshape(1, -1)) / shape[1] * 2) ** 3
        mask = np.maximum(1. - dist_sq ** 3, 0)
        mask = np.ones_like(mask)  # 暂时取消
        mask *= scale
        return mask

    def save_y_lim(self):
        config['y_lim'] = (self.log_y_lim[0], self.log_y_lim[1])
        save_config()

    def make_mesh_function(self, rect):
        base_point = rect[0]
        x_delta = (rect[1][0] - rect[0][0], rect[1][1] - rect[0][1])
        # y_rate = (rect[3].shape[1] / rect[3].shape[0]) ** -1
        y_rate = rect[3].shape[1] / rect[3].shape[0]
        y_delta = (-x_delta[1] * y_rate,
                   x_delta[0] * y_rate)
        if not rect[2]:
            y_delta = (-y_delta[0], -y_delta[1])

        center = (round(base_point[0] + 0.5 * x_delta[0] + 0.5 * y_delta[0]),
                  round(base_point[1] + 0.5 * x_delta[1] + 0.5 * y_delta[1]))
        angle = -np.arctan2(rect[1][1] - rect[0][1], rect[1][0] - rect[0][0])
        x_length = np.sqrt((rect[1][0] - rect[0][0]) ** 2 + (rect[1][1] - rect[0][1]) ** 2)
        new_shape = (int(x_length), int(x_length * y_rate))

        def mesh_function(data: np.ndarray):
            x = center[0] + (np.linspace(0, new_shape[0], data.shape[0] + 2) - 0.5 * new_shape[0]) * x_length / (data.shape[0] + 2) / 10
            y = center[1] + (np.linspace(0, new_shape[1], data.shape[1] + 2) - 0.5 * new_shape[1]) * x_length * y_rate / (data.shape[1] + 2) / 10

            data = np.log(np.maximum(data, 1e-6)) / np.log(10)
            data = np.clip((data + self.log_y_lim[1]) / (self.log_y_lim[1] - self.log_y_lim[0]), 0., 1.)
            # 外面加一圈
            data = np.pad(data, ((1, 1), (1, 1)), mode='constant', constant_values=0.)
            data = Interpolation(1, 2.0, data.shape).smooth(data)
            z = data.copy()

            return {'x': x - 450, 'y': y - 600, 'z': z}

        return mesh_function

    def __on_mouse_wheel(self, event: QWheelEvent):
        return
        if not config['fixed_range']:
            # 当鼠标滚轮滚动时，调整图像的显示范围
            if event.angleDelta().y() > 0:
                if self.log_y_lim[1] < MAXIMUM_Y_LIM:
                    self.log_y_lim = (self.log_y_lim[0] + 0.1, self.log_y_lim[1] + 0.1)
            else:
                if self.log_y_lim[0] > MINIMUM_Y_LIM:
                    self.log_y_lim = (self.log_y_lim[0] - 0.1, self.log_y_lim[1] - 0.1)
            self.log_y_lim = (round(self.log_y_lim[0], 1), round(self.log_y_lim[1], 1))
            self.ax.getViewBox().setYRange(-self.log_y_lim[1], -self.log_y_lim[0])
            self.save_y_lim()

    def process_forever(self):
        ticker = Ticker()
        ticker.tic()
        while True:
            try:
                self.process_image()
            except ValueError:
                pass
            # ticker.toc("process_image")
            time.sleep(0.001)

    def process_image(self):
        if self.dd.value and self.dd.zero_set:
            with self.dd.lock:
                data_fingers = self.dd.value[-1]  # 唯一的数据流入位置
                time_now = self.dd.time[-1]
                self.dd.value.clear()
                self.dd.time.clear()
            with self.lock:
                for idx, data in data_fingers.items():
                    self.meshes[idx] = self.mesh_functions[idx](data)
                    max_value = self.finger_feature_extractors[idx](data)['contact_strength']
                    x_diff = self.finger_feature_extractors[idx](data)['center_x_diff']
                    y_diff = self.finger_feature_extractors[idx](data)['center_y_diff']
                    self.region_max[idx].append(max_value)
                    self.region_x_diff[idx].append(x_diff)
                    self.region_y_diff[idx].append(y_diff)
            self.time.append(time_now)

    def plot(self):
        with self.lock:

            for k, surface_plot in self.surface_plots.items():
                surface_plot.setData(
                    x=self.meshes[k]['x'] / 100.,
                    y=self.meshes[k]['y'] / 100.,
                    z=self.meshes[k]['z'] * 0.5,
                    colors=create_color_map(self.meshes[k]['z']),
                )

            for idx, line in self.lines.items():
                line.setData(self.time, self.region_max[idx])

    def _on_mouse_release(self, event):
        """鼠标释放时显示当前相机视角参数"""
        azimuth = self.gl_widget.opts['azimuth']
        elevation = self.gl_widget.opts['elevation']
        distance = self.gl_widget.opts['distance']
        center = self.gl_widget.opts['center']  # 获取相机的中心位置
        print(f"Camera Parameters - Azimuth: {azimuth}, Elevation: {elevation}, Distance: {distance}, Center: {center}")
        GLViewWidget.mouseReleaseEvent(self.gl_widget, event)

    def set_axes_using_calibration(self, b):
        if b:
            self.clear()
            self.ax.setLabel(axis='left', text='总力(N)')
            # 设置Y轴自由
            self.ax.getViewBox().setYRange(0, 0.1)
            self.ax.enableAutoRange(axis=pyqtgraph.ViewBox.YAxis)

            def update_y_range():
                current_range = self.ax.viewRange()[1]  # 获取当前Y轴范围
                if current_range[1]  < 0.1:  # 如果范围不足1
                    new_range = (0., 0.1)
                    self.ax.sigRangeChanged.disconnect(update_y_range)
                    self.ax.getViewBox().setYRange(new_range[0], new_range[1])
                    self.ax.sigRangeChanged.connect(update_y_range)
                else:
                    self.ax.enableAutoRange(axis=pyqtgraph.ViewBox.YAxis)

            self.ax.sigRangeChanged.connect(update_y_range)  # 监听范围变化
        else:
            self.clear()
            self.ax.setLabel(axis='left', text='接触强度')
            self.ax.getViewBox().setYRange(0, 200)


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
    ]) / 255.0 * 1.0
    # Interpolate colors
    # indices = (data * (colors.shape[0] - 1)).astype(int)
    # 改成插值
    interps = [interp1d(np.linspace(0., 1., colors.shape[0]), colors[:, j], axis=0, bounds_error=False,
                        fill_value=(colors[0, j], colors[-1, j]))
               for j in range(3)]
    return np.stack([interp(data) for interp in interps], axis=-1)

