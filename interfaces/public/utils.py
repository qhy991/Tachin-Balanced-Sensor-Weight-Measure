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
LINE_STYLE = {'pen': pyqtgraph.mkPen('w'), 'symbol': 'o', 'symbolBrush': 'w', 'symbolSize': 4}
SCATTER_STYLE = {'pen': pyqtgraph.mkPen('w', width=2), 'symbol': 's', 'brush': None, 'symbolSize': 20}
STANDARD_PEN = pyqtgraph.mkPen('w')

RESOURCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../resources')


def catch_exceptions(window, ty, value, tb):
    # 错误重定向为弹出对话框
    # traceback_format = traceback.format_exception(ty, value, tb)
    # traceback_string = "".join(traceback_format)
    # print(traceback_string)
    print(value)
    QtWidgets.QMessageBox.critical(window, "错误", "{}".format(value))

# DARK_THEME: 传入dark_theme参数
def set_logo(window, dark_theme=False, logo_suffix=''):
    window.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow", "电子皮肤采集程序"))
    window.setWindowIcon(QtGui.QIcon(os.path.join(RESOURCE_FOLDER, "logo.ico")))
    # DARK_THEME: 区分两种图标
    if not logo_suffix:
        logo_suffix = '_dark' if dark_theme else '_light'
    logo_path = os.path.join(RESOURCE_FOLDER, f"logo{logo_suffix}.png")
    pixmap = QtGui.QPixmap(logo_path)
    window.label_logo.setPixmap(pixmap)
    window.label_logo.setScaledContents(True)
    window.label_logo.setFixedSize(pixmap.size())  # 强制 QLabel 与位图保持相同比例
    window.label_logo.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
    # DARK_THEME: 设置标题栏隐藏状态
    window._title_bar_hidden = False
    window._saved_geometry = None
    window._title_bar_height = int(window.style().pixelMetric(QtWidgets.QStyle.PM_TitleBarHeight) * 1.3)

    def keyPressEvent(event):
        if event.key() == QtCore.Qt.Key_F11 and not event.isAutoRepeat():
            # 保存当前状态
            current_state = {
                'geometry': window.geometry(),
                'maximized': window.isMaximized()
            }
            print("标题栏状态切换指令下达")
            if not window._title_bar_hidden:
                print("标题栏非隐藏状态，尝试隐藏标题栏")
                # 隐藏标题栏
                window._saved_geometry = current_state
                # 清除所有窗口标志并重新设置
                window.setWindowFlags(QtCore.Qt.FramelessWindowHint)
                window.show()
                # 调整窗口大小
                if not current_state['maximized']:
                    new_geo = current_state['geometry']
                    window.setGeometry(
                        new_geo.x(),
                        new_geo.y() - window._title_bar_height,
                        new_geo.width(),
                        new_geo.height() + window._title_bar_height
                    )
                window._title_bar_hidden = True
                # 验证是否已有效隐藏标题栏
                if window.windowFlags() & QtCore.Qt.FramelessWindowHint:
                    print("标题栏已成功隐藏")
                else:
                    print("标题栏隐藏失败")
            else:
                print("标题栏非隐藏状态，尝试恢复标题栏")
                # 恢复标题栏
                window.setWindowFlags(QtCore.Qt.Window)  # 使用默认窗口样式
                window.show()
                # 恢复原始状态
                if window._saved_geometry:
                    if window._saved_geometry['maximized']:
                        window.showMaximized()
                    else:
                        window.setGeometry(window._saved_geometry['geometry'])
                window._title_bar_hidden = False
                # 验证是否已有效恢复标题栏
                if not (window.windowFlags() & QtCore.Qt.FramelessWindowHint):
                    print("标题栏已成功恢复")
                else:
                    print("标题栏恢复失败")
        else:
            # 确保事件正确传递
            super(type(window), window).keyPressEvent(event)

    window.keyPressEvent = keyPressEvent
    #
    if dark_theme:
        apply_dark_theme(window)

def create_lines(fig_widget: pyqtgraph.GraphicsLayoutWidget, x_name, y_name, count=1, ax=None):
    if ax is None:
        ax: pyqtgraph.PlotItem = fig_widget.addPlot()
        ax.setLabel(axis='left', text=y_name)
        ax.getAxis('left').enableAutoSIPrefix(False)
        ax.setLabel(axis='bottom', text=x_name)
        # ax.getAxis('left').tickStrings = lambda values, scale, spacing:\
        #     [(f'{_ ** -1: .1f}' if _ > 0. else 'INF') for _ in values]
        ax.getAxis('left').tickStrings = lambda values, scale, spacing: \
                [f'{10 ** (-_): .1f}' for _ in values]
        ax.getViewBox().setMouseEnabled(x=False, y=False)
        ax.hideButtons()
    else:
        # 清除已有的线条
        ax.clear()
    lines = []
    for i in range(count):
        line: pyqtgraph.PlotDataItem = ax.plot([], [], **LINE_STYLE)
        line.get_axis = lambda: ax
        lines.append(line)
    return ax, lines


POS = (0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1)

def create_an_image(fig_widget: pyqtgraph.GraphicsLayoutWidget,
                    on_click, on_wheel
                    ):
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

# DARK_THEME: 整体风格
def apply_dark_theme(window):
    # 设置无边框和深色主题
    window.setStyleSheet("""
        QWidget { background-color: #000000; }
        QLineEdit, QPushButton, QComboBox {
            color: white; background-color: #000000; border: 1px solid #000000;
        }
        QLabel {
            color: white; background-color: #000000; border: 0px 
        }
        QPushButton:hover { background-color: #2E2E2E; }
        QComboBox { selection-background-color: #2E2E2E; }
    """)
    window.setStyle(QtWidgets.QStyleFactory.create("Fusion"))
    palette = window.palette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#000000"))
    window.setPalette(palette)



