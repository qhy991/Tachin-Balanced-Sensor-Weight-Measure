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
from data.preprocessing import MedianFilter
from interfaces.hand_shape.feature_extractor import FingerFeatureExtractor
from data.interpolation import Interpolation
from utils.performance_monitor import Ticker
from PyQt5.QtGui import QWheelEvent
from PyQt5 import QtWidgets
from data.data_handler import DataHandler
from config import config, save_config, get_config_mapping

legend_color = lambda i: pyqtgraph.intColor(i, 16 * 1.5, maxValue=127 + 64)
STANDARD_PEN = pyqtgraph.mkPen('k')

class HandPlotManager:
    def __init__(self,
                 widget: QtWidgets.QWidget,
                 fig_widget_1d: pyqtgraph.GraphicsLayoutWidget,
                 data_handler: DataHandler,
                 config_mapping,
                 downsample=1):
        # 将传入的 QWidget 转换为 GLViewWidget
        self.gl_widget = GLViewWidget()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.gl_widget, 0, 0)
        widget.setLayout(layout)

        # 3D场景初始化
        self.gl_widget.setBackgroundColor('k')
        self.grid = GLGridItem()
        self.gl_widget.addItem(self.grid)

        self.dd = data_handler
        self.config_mapping = config_mapping
        self.range_mapping = config_mapping['range_mapping']
        self.is_left_hand = config_mapping['is_left_hand']
        self.arrow_offset = config_mapping.get('arrow_offset', None)


        # 曲面图
        self.surface_plots = {}
        self.base_meshes = self._create_base_meshes(config_mapping)
        for idx, mesh in self.base_meshes.items():
            surface_plot = GLSurfacePlotItem(
                x=mesh['x'],
                y=mesh['y'],
                z=mesh['z'],
                shader='shaded',
                computeNormals=False
            )
            self.gl_widget.addItem(surface_plot)
            self.surface_plots.update({idx: surface_plot})

        # 箭头图
        if self.arrow_offset:
            self.arrows = {
                int(idx): GLLinePlotItem() for idx in self.range_mapping.keys()
            }
            for item in self.arrows.values():
                self.gl_widget.addItem(item)

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
        # 图例每行3个
        ax.addLegend(colCount=3)
        self.ax = ax
        self.lines = {int(idx): ax.plot(pen=pyqtgraph.mkPen(legend_color(idx), width=2),
                                        name=config_mapping['names'][idx])
                      for idx in self.range_mapping.keys()}
        # 存储
        self.filters = {int(idx): MedianFilter({'SENSOR_SHAPE': (1, 1), 'DATA_TYPE': float}, 2)
                        for idx in self.range_mapping.keys()}
        max_len = self.dd.max_len
        self.region_max = {int(idx): deque(maxlen=max_len) for idx in self.range_mapping.keys()}
        self.region_x_diff = {int(idx): deque(maxlen=max_len) for idx in self.range_mapping.keys()}
        self.region_y_diff = {int(idx): deque(maxlen=max_len) for idx in self.range_mapping.keys()}
        self.time = deque(maxlen=max_len)

        # 数据处理相关初始化
        self.filters = {int(idx): MedianFilter({'SENSOR_SHAPE': (1,1), 'DATA_TYPE': float}, 2)
                       for idx in self.range_mapping.keys()}
        self.lock = threading.Lock()
        threading.Thread(target=self.process_forever, daemon=True).start()

    def _create_base_meshes(self, config_mapping):
        base_meshes = {}
        for k, _ in self.range_mapping.items():
            x = np.linspace(-10, 10, 50)
            y = np.linspace(-10, 10, 50)
            z = np.zeros((x.size, y.size))
            base_meshes.update({int(k): {'x': x, 'y': y, 'z': z}})
        return base_meshes

    def _update_3d_arrows(self, idx, x_diff, y_diff):
        start = np.array([self.base_meshes[idx]['x'].mean(),
                          self.base_meshes[idx]['y'].mean(),
                          self.base_meshes[idx]['z'].mean()])
        end = start + np.array([x_diff * 2, y_diff * 2, 0])
        self.arrows[idx].setData(
            pos=np.array([start, end]),
            color=(1, 0, 0, 1),
            width=3
        )

    def process_forever(self):
        while True:
            try:
                if self.dd.value and self.dd.zero_set:
                    with self.dd.lock:
                        data_fingers = self.dd.value[-1]
                        time_now = self.dd.time[-1]
                        self.dd.value.clear()
                        self.dd.time.clear()

                    with self.lock:
                        for idx, data in data_fingers.items():
                            features = FingerFeatureExtractor(15, 4, 0.995, 10., 1.0)(data)
                            # 更新3D箭头
                            self._update_3d_arrows(idx,
                                                  features['center_x_diff'],
                                                  features['center_y_diff'])
                            # 更新曲线数据
                            self.lines[idx].setData(
                                list(self.dynamic_data[idx]),  # 转换为列表
                                [v['contact_strength'] for v in self.dynamic_data[idx]]
                            )
                            self.dynamic_data[idx]['points'].append({
                                'time': time_now,
                                'contact_strength': features['contact_strength']
                            })
                time.sleep(0.01)
            except Exception as e:
                raise e

    def clear(self):
        with self.lock:
            for idx in self.dynamic_data:
                self.dynamic_data[idx]['points'].clear()
                self.dynamic_data[idx]['arrows'].setData(pos=[])
            for line in self.lines.values():
                line.setData([], [])

    def plot(self):
        pass
