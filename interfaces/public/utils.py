import os, traceback
# import everything
from PyQt5 import QtGui, QtWidgets, QtCore
import pyqtgraph
from config import config, save_config

COLORS = [[15, 15, 15],
          [48, 18, 59],
          [71, 118, 238],
          [27, 208, 213],
          [97, 252, 108],
          [210, 233, 53],
          [254, 155, 45],
          [218, 57, 7],
          [122, 4, 3]]
LINE_STYLE = {'pen': pyqtgraph.mkPen('k'), 'symbol': 'o', 'symbolBrush': 'k', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('k', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}
STANDARD_PEN = pyqtgraph.mkPen('k')

RESOURCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../resources')


def catch_exceptions(window, ty, value, tb):
    # 错误重定向为弹出对话框
    # traceback_format = traceback.format_exception(ty, value, tb)
    # traceback_string = "".join(traceback_format)
    # print(traceback_string)
    print(value)
    QtWidgets.QMessageBox.critical(window, "错误", "{}".format(value))


def set_logo(window):
    window.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow", "电子皮肤采集程序"))
    window.setWindowIcon(QtGui.QIcon(os.path.join(RESOURCE_FOLDER, "logo.ico")))
    logo_path = os.path.join(RESOURCE_FOLDER, "logo.png")
    pixmap = QtGui.QPixmap(logo_path)
    window.label_logo.setPixmap(pixmap)
    window.label_logo.setScaledContents(True)
    window.label_logo.setFixedSize(pixmap.size())  # 强制 QLabel 与位图保持相同比例
    window.label_logo.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)


def create_a_line(fig_widget: pyqtgraph.GraphicsLayoutWidget, x_name, y_name):
    ax: pyqtgraph.PlotItem = fig_widget.addPlot()
    ax.setLabel(axis='left', text=y_name)
    ax.getAxis('left').enableAutoSIPrefix(False)
    ax.setLabel(axis='bottom', text=x_name)
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


POS = (0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1)

def create_an_image(fig_widget: pyqtgraph.GraphicsLayoutWidget,
                    on_click, on_wheel
                    ):
    fig_widget.setBackground(0.95)
    plot = pyqtgraph.ImageView()
    layout = QtWidgets.QGridLayout()
    layout.addWidget(plot, 0, 0)
    fig_widget.setLayout(layout)
    plot.adjustSize()

    plot.ui.histogram.hide()
    plot.ui.menuBtn.hide()
    plot.ui.roiBtn.hide()
    #
    cmap = pyqtgraph.ColorMap(pos=[_ for _ in POS], color=COLORS)
    plot.setColorMap(cmap)
    vb: pyqtgraph.ViewBox = plot.getImageItem().getViewBox()
    vb.setMouseEnabled(x=False, y=False)
    vb.setBackgroundColor(pyqtgraph.mkColor(0.95))
    plot.getImageItem().scene().sigMouseClicked.connect(on_click)
    plot.getImageItem().wheelEvent = on_wheel
    plot.getView().invertX(config['x_invert'])
    plot.getView().invertY(config['y_invert'])
    return plot

#
def apply_swap(data):
    if config['xy_swap']:
        return data.T
    else:
        return data
