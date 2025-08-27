#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传感器驱动与balance-sensor校准集成示例

这个示例展示了如何将balance-sensor的校准功能集成到传感器驱动的数据处理流程中。
"""

import sys
import os
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_processing.data_handler import DataHandler
from backends.usb_driver import LargeUsbSensorDriver


class IntegratedSensorInterface(QtWidgets.QMainWindow):
    """集成校准功能的传感器界面"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("传感器驱动 - 集成Balance-Sensor校准")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化数据处理器
        self.data_handler = DataHandler(LargeUsbSensorDriver, max_len=64)
        self.is_running = False
        
        # 初始化UI
        self.init_ui()
        
        # 定时器
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)
        
        # 校准文件路径
        self.calibration_file_path = None
    
    def init_ui(self):
        """初始化用户界面"""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # 控制面板
        control_panel = QtWidgets.QHBoxLayout()
        
        # 连接控制
        self.connect_btn = QtWidgets.QPushButton("连接传感器")
        self.connect_btn.clicked.connect(self.toggle_connection)
        control_panel.addWidget(self.connect_btn)
        
        # 端口输入
        self.port_input = QtWidgets.QLineEdit("0")
        self.port_input.setPlaceholderText("端口号")
        control_panel.addWidget(QtWidgets.QLabel("端口:"))
        control_panel.addWidget(self.port_input)
        
        # 校准控制
        self.load_cal_btn = QtWidgets.QPushButton("加载Balance校准")
        self.load_cal_btn.clicked.connect(self.load_balance_calibration)
        control_panel.addWidget(self.load_cal_btn)
        
        self.clear_cal_btn = QtWidgets.QPushButton("清除校准")
        self.clear_cal_btn.clicked.connect(self.clear_balance_calibration)
        control_panel.addWidget(self.clear_cal_btn)
        
        control_panel.addStretch()
        layout.addLayout(control_panel)
        
        # 状态显示
        self.status_label = QtWidgets.QLabel("状态: 未连接")
        layout.addWidget(self.status_label)
        
        # 校准信息显示
        self.cal_info_label = QtWidgets.QLabel("校准信息: 未加载")
        self.cal_info_label.setStyleSheet("font-family: monospace; background-color: #f8f9fa; padding: 8px; border: 1px solid #dee2e6; border-radius: 4px;")
        layout.addWidget(self.cal_info_label)
        
        # 数据可视化
        plot_layout = QtWidgets.QHBoxLayout()
        
        # 原始数据热力图
        self.raw_plot_widget = pg.GraphicsLayoutWidget()
        self.raw_plot = self.raw_plot_widget.addPlot()
        self.raw_plot.setTitle("原始数据")
        self.raw_image = pg.ImageItem()
        self.raw_plot.addItem(self.raw_image)
        plot_layout.addWidget(self.raw_plot_widget)
        
        # 校准后数据热力图
        self.cal_plot_widget = pg.GraphicsLayoutWidget()
        self.cal_plot = self.cal_plot_widget.addPlot()
        self.cal_plot.setTitle("校准后数据")
        self.cal_image = pg.ImageItem()
        self.cal_plot.addItem(self.cal_image)
        plot_layout.addWidget(self.cal_plot_widget)
        
        layout.addLayout(plot_layout)
        
        # 数据统计
        stats_layout = QtWidgets.QHBoxLayout()
        
        self.raw_stats_label = QtWidgets.QLabel("原始数据统计: --")
        stats_layout.addWidget(self.raw_stats_label)
        
        self.cal_stats_label = QtWidgets.QLabel("校准后数据统计: --")
        stats_layout.addWidget(self.cal_stats_label)
        
        layout.addLayout(stats_layout)
    
    def toggle_connection(self):
        """切换传感器连接状态"""
        if not self.is_running:
            # 连接传感器
            port = self.port_input.text()
            success = self.data_handler.connect(port)
            if success:
                self.is_running = True
                self.timer.start(100)  # 100ms更新频率
                self.connect_btn.setText("断开传感器")
                self.status_label.setText("状态: 已连接")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                print("✅ 传感器连接成功")
            else:
                self.status_label.setText("状态: 连接失败")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                print("❌ 传感器连接失败")
        else:
            # 断开传感器
            self.data_handler.disconnect()
            self.is_running = False
            self.timer.stop()
            self.connect_btn.setText("连接传感器")
            self.status_label.setText("状态: 已断开")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            print("✅ 传感器已断开")
    
    def load_balance_calibration(self):
        """加载balance-sensor校准文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择Balance-Sensor校准文件",
            "",
            "校准文件 (*.json *.npy *.csv);;JSON文件 (*.json);;NumPy文件 (*.npy);;CSV文件 (*.csv);;所有文件 (*)"
        )
        
        if file_path:
            success = self.data_handler.set_balance_calibration(file_path)
            if success:
                self.calibration_file_path = file_path
                self.update_calibration_info()
                print(f"✅ 已加载校准文件: {os.path.basename(file_path)}")
            else:
                QtWidgets.QMessageBox.warning(self, "警告", f"加载校准文件失败:\n{file_path}")
    
    def clear_balance_calibration(self):
        """清除balance-sensor校准"""
        self.data_handler.abandon_balance_calibration()
        self.calibration_file_path = None
        self.update_calibration_info()
        print("✅ 已清除校准")
    
    def update_calibration_info(self):
        """更新校准信息显示"""
        info = self.data_handler.get_balance_calibration_info()
        if info:
            info_text = f"校准状态: 已加载\n"
            info_text += f"系数: {info['coefficient']:.6f}\n"
            info_text += f"偏置: {info['bias']:.6f}\n"
            
            if 'calibration_map_shape' in info:
                info_text += f"校准映射: {info['calibration_map_shape']}\n"
                info_text += f"映射均值: {info['calibration_map_mean']:.6f}"
            
            self.cal_info_label.setText(info_text)
            self.cal_info_label.setStyleSheet("font-family: monospace; background-color: #d4edda; padding: 8px; border: 1px solid #c3e6cb; border-radius: 4px;")
        else:
            self.cal_info_label.setText("校准信息: 未加载")
            self.cal_info_label.setStyleSheet("font-family: monospace; background-color: #f8f9fa; padding: 8px; border: 1px solid #dee2e6; border-radius: 4px;")
    
    def update_data(self):
        """更新数据显示"""
        try:
            # 触发数据获取
            self.data_handler.trigger()
            
            # 获取最新数据
            if len(self.data_handler.data) > 0:
                # 原始数据（应用滤波器前）
                raw_data = self.data_handler.data[-1]
                
                # 校准后数据（应用所有处理后）
                calibrated_data = self.data_handler.value[-1]
                
                # 更新热力图
                self.raw_image.setImage(raw_data.T)
                self.cal_image.setImage(calibrated_data.T)
                
                # 更新统计信息
                raw_sum = np.sum(raw_data)
                raw_mean = np.mean(raw_data)
                raw_max = np.max(raw_data)
                
                cal_sum = np.sum(calibrated_data)
                cal_mean = np.mean(calibrated_data)
                cal_max = np.max(calibrated_data)
                
                self.raw_stats_label.setText(f"原始数据 - 总和: {raw_sum:.2f}, 均值: {raw_mean:.3f}, 最大值: {raw_max:.3f}")
                self.cal_stats_label.setText(f"校准后数据 - 总和: {cal_sum:.2f}, 均值: {cal_mean:.3f}, 最大值: {cal_max:.3f}")
                
        except Exception as e:
            print(f"⚠️ 更新数据时出错: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.is_running:
            self.data_handler.disconnect()
        event.accept()


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = IntegratedSensorInterface()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 