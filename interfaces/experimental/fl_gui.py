import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from backends.fl_driver import FLDriver


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = Figure(figsize=(5, 4), dpi=100), None
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("实时数据曲线")
        self.ax.set_xlabel("时间")
        self.ax.set_ylabel("行和")
        self.data = []

    def update_plot(self, new_data):
        self.data.append(new_data)
        if len(self.data) > 100:  # 限制显示的点数
            self.data.pop(0)
        self.ax.clear()
        self.ax.plot(self.data, label="总力")
        # 在y=1处画一条虚线
        self.ax.axhline(y=2., color='r', linestyle='--', label="阈值线")
        self.ax.legend()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLDriver 数据可视化")
        self.setGeometry(100, 100, 800, 600)

        self.driver = FLDriver('COM28')  # 替换为实际端口
        assert self.driver.start()

        self.canvas = PlotCanvas(self)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(100)  # 每 100 毫秒更新一次

    def update_plot(self):
        while True:
            values = self.driver.get()
            if values is not None:
                row_sums = np.sum(values, axis=1)  # 对每行求和
                total_sum = np.sum(row_sums)  # 总和
                self.canvas.update_plot(total_sum)
            else:
                break
        self.canvas.draw()

    def closeEvent(self, event):
        self.driver.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())