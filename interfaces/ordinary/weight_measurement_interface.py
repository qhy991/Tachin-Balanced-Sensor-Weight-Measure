#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
称重测量界面 - 基于传感器驱动系统

这个界面将称重功能集成到传感器驱动系统中，提供完整的称重测量功能。
"""

import os
import sys
import numpy as np
import json
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QTimer, QSize
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QGridLayout, QGroupBox, QLabel, QPushButton, 
                            QLineEdit, QComboBox, QLCDNumber, QMessageBox,
                            QFileDialog, QTextEdit, QProgressBar)
from PyQt5.QtGui import QFont, QPixmap
import pyqtgraph as pg

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_processing.data_handler import DataHandler
from backends.usb_driver import LargeUsbSensorDriver
from interfaces.public.utils import set_logo, config, save_config, catch_exceptions


class WeightMeasurementInterface(QMainWindow):
    """称重测量主界面"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("称重测量系统 - 集成版")
        self.setGeometry(100, 100, 1400, 900)
        
        # 初始化数据处理器
        self.data_handler = DataHandler(LargeUsbSensorDriver, max_len=64)
        self.is_running = False
        
        # 称重相关参数
        self.zero_pressure = 0.0
        self.is_zeroed = False
        self.measurement_active = False
        self.calibration_coefficient = 1730.6905
        self.calibration_bias = 126.1741
        self.current_weight = 0.0
        self.weight_history = []
        self.max_history_length = 100
        
        # 初始化UI
        self.init_ui()
        
        # 定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        
        # 校准文件路径
        self.calibration_file_path = None
        
        # 设置异常处理
        sys.excepthook = self._catch_exceptions
        self.config, self.save_config = config, save_config
    
    def _catch_exceptions(self, ty, value, tb):
        catch_exceptions(self, ty, value, tb)
    
    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局 - 两栏布局
        main_layout = QHBoxLayout(central_widget)
        
        # ===== 左侧栏：传感器控制和监控 =====
        left_panel = QVBoxLayout()
        
        # 传感器控制组
        sensor_group = QGroupBox("传感器控制")
        sensor_layout = QGridLayout()
        
        self.sensor_combo = QComboBox()
        self.sensor_combo.addItems(["真实传感器", "模拟传感器"])
        self.sensor_combo.currentTextChanged.connect(self.on_sensor_changed)
        
        self.port_input = QLineEdit("0")
        self.port_input.setPlaceholderText("端口号")
        
        self.start_button = QPushButton("连接传感器")
        self.start_button.clicked.connect(self.start_sensor)
        self.start_button.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        
        self.stop_button = QPushButton("断开传感器")
        self.stop_button.clicked.connect(self.stop_sensor)
        self.stop_button.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 8px;")
        
        self.status_label = QLabel("状态: 未连接")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
        sensor_layout.addWidget(QLabel("传感器:"), 0, 0)
        sensor_layout.addWidget(self.sensor_combo, 0, 1)
        sensor_layout.addWidget(QLabel("端口:"), 1, 0)
        sensor_layout.addWidget(self.port_input, 1, 1)
        sensor_layout.addWidget(self.start_button, 2, 0)
        sensor_layout.addWidget(self.stop_button, 2, 1)
        sensor_layout.addWidget(self.status_label, 3, 0, 1, 2)
        
        sensor_group.setLayout(sensor_layout)
        left_panel.addWidget(sensor_group)
        
        # 压力信息组
        pressure_group = QGroupBox("压力信息")
        pressure_layout = QGridLayout()
        
        self.total_pressure_label = QLabel("总压力: -- N")
        self.max_pressure_label = QLabel("最大压力: -- N")
        self.min_pressure_label = QLabel("最小压力: -- N")
        
        pressure_layout.addWidget(self.total_pressure_label, 0, 0)
        pressure_layout.addWidget(self.max_pressure_label, 0, 1)
        pressure_layout.addWidget(self.min_pressure_label, 1, 0)
        
        pressure_group.setLayout(pressure_layout)
        left_panel.addWidget(pressure_group)
        
        # 热力图组
        heatmap_group = QGroupBox("压力分布热力图")
        heatmap_layout = QVBoxLayout()
        
        # 热力图控制按钮
        heatmap_control_layout = QHBoxLayout()
        
        self.auto_scale_btn = QPushButton("自动缩放")
        self.auto_scale_btn.clicked.connect(self.auto_scale_heatmap)
        self.auto_scale_btn.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
        
        self.reset_scale_btn = QPushButton("重置缩放")
        self.reset_scale_btn.clicked.connect(self.reset_heatmap_scale)
        self.reset_scale_btn.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 6px;")
        
        heatmap_control_layout.addWidget(self.auto_scale_btn)
        heatmap_control_layout.addWidget(self.reset_scale_btn)
        heatmap_control_layout.addStretch()
        
        # 热力图显示区域
        self.heatmap_plot = pg.GraphicsLayoutWidget()
        self.heatmap_plot.setFixedHeight(300)
        self.heatmap_widget = self.heatmap_plot.addPlot()
        self.heatmap_widget.setAspectLocked(True)
        self.heatmap_widget.setTitle('压力分布热力图')
        self.heatmap_widget.invertY(True)  # 使Y轴朝下
        
        # 设置坐标轴范围：X轴0-64，Y轴0-64，确保正方形显示
        self.heatmap_widget.setXRange(0, 64)
        self.heatmap_widget.setYRange(0, 64)
        
        # 创建热力图图像项
        self.heatmap_image = pg.ImageItem()
        self.heatmap_widget.addItem(self.heatmap_image)
        
        # 添加颜色条
        self.heatmap_colorbar = pg.ColorBarItem(
            values=(0, 1),
            colorMap='viridis',
            label='压力强度'
        )
        self.heatmap_colorbar.setImageItem(self.heatmap_image)
        
        heatmap_layout.addLayout(heatmap_control_layout)
        heatmap_layout.addWidget(self.heatmap_plot)
        
        # 热力图信息标签
        self.heatmap_info_label = QLabel("热力图信息: 等待数据...")
        self.heatmap_info_label.setStyleSheet("font-size: 11px; color: #666; font-style: italic;")
        heatmap_layout.addWidget(self.heatmap_info_label)
        
        heatmap_group.setLayout(heatmap_layout)
        left_panel.addWidget(heatmap_group)
        
        # 校准信息组
        calibration_group = QGroupBox("校准信息")
        calibration_layout = QVBoxLayout()
        
        # 校准信息显示
        self.calibration_info_label = QLabel("未加载校准文件")
        self.calibration_info_label.setStyleSheet("font-size: 11px; color: #666; font-family: monospace; background-color: #f8f9fa; padding: 8px; border: 1px solid #dee2e6; border-radius: 4px;")
        
        # 校准控制按钮
        calibration_control_layout = QHBoxLayout()
        
        self.load_cal_btn = QPushButton("加载校准")
        self.load_cal_btn.clicked.connect(self.load_balance_calibration)
        self.load_cal_btn.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
        
        self.save_cal_btn = QPushButton("保存校准")
        self.save_cal_btn.clicked.connect(self.save_calibration)
        self.save_cal_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 6px;")
        
        calibration_control_layout.addWidget(self.load_cal_btn)
        calibration_control_layout.addWidget(self.save_cal_btn)
        calibration_control_layout.addStretch()
        
        calibration_layout.addWidget(self.calibration_info_label)
        calibration_layout.addLayout(calibration_control_layout)
        
        calibration_group.setLayout(calibration_layout)
        left_panel.addWidget(calibration_group)
        
        # 左侧占25%，右侧占75%
        main_layout.addLayout(left_panel, 25)
        
        # ===== 右侧栏：称重功能 =====
        right_panel = QVBoxLayout()
        
        # 校准参数组
        calibration_params_group = QGroupBox("校准参数")
        calibration_params_layout = QGridLayout()
        
        self.calibration_mode_label = QLabel("校准模式: 线性校准")
        self.calibration_mode_label.setStyleSheet("font-weight: bold; color: #28a745;")
        
        self.formula_label = QLabel("公式: 质量 = k × 压力 + b")
        self.formula_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        
        self.coefficient_label = QLabel("系数 (k):")
        self.coefficient_input = QLineEdit(str(self.calibration_coefficient))
        self.coefficient_input.textChanged.connect(self.on_coefficient_changed)
        
        self.bias_label = QLabel("偏置 (b):")
        self.bias_input = QLineEdit(str(self.calibration_bias))
        self.bias_input.textChanged.connect(self.on_bias_changed)
        
        self.current_params_label = QLabel("当前参数: 已加载")
        self.current_params_label.setStyleSheet("font-size: 11px; color: #28a745; background-color: #d4edda; padding: 4px; border-radius: 4px;")
        
        calibration_params_layout.addWidget(self.calibration_mode_label, 0, 0, 1, 2)
        calibration_params_layout.addWidget(self.formula_label, 1, 0, 1, 2)
        calibration_params_layout.addWidget(self.coefficient_label, 2, 0)
        calibration_params_layout.addWidget(self.coefficient_input, 2, 1)
        calibration_params_layout.addWidget(self.bias_label, 3, 0)
        calibration_params_layout.addWidget(self.bias_input, 3, 1)
        calibration_params_layout.addWidget(self.current_params_label, 4, 0, 1, 2)
        
        calibration_params_group.setLayout(calibration_params_layout)
        right_panel.addWidget(calibration_params_group)
        
        # 归零控制组
        zero_group = QGroupBox("归零控制")
        zero_layout = QHBoxLayout()
        
        self.zero_btn = QPushButton("归零")
        self.zero_btn.clicked.connect(self.perform_zero)
        self.zero_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        
        self.zero_status_label = QLabel("状态: 未归零")
        self.zero_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        self.zero_pressure_label = QLabel("归零压力: -- N")
        
        zero_layout.addWidget(self.zero_btn)
        zero_layout.addWidget(self.zero_status_label)
        zero_layout.addWidget(self.zero_pressure_label)
        zero_layout.addStretch()
        
        zero_group.setLayout(zero_layout)
        right_panel.addWidget(zero_group)
        
        # 重量显示组
        weight_group = QGroupBox("重量显示")
        weight_layout = QVBoxLayout()
        
        self.weight_display = QLCDNumber()
        self.weight_display.setDigitCount(8)
        self.weight_display.setSegmentStyle(QLCDNumber.Flat)
        self.weight_display.setStyleSheet("background-color: #000; color: #0f0; font-size: 24px;")
        self.weight_display.display("0.000")
        
        self.weight_unit_label = QLabel("克 (g)")
        self.weight_unit_label.setAlignment(QtCore.Qt.AlignCenter)
        self.weight_unit_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        
        weight_layout.addWidget(self.weight_display)
        weight_layout.addWidget(self.weight_unit_label)
        
        weight_group.setLayout(weight_layout)
        right_panel.addWidget(weight_group)
        
        # 测量控制组
        measurement_group = QGroupBox("测量控制")
        measurement_layout = QHBoxLayout()
        
        self.start_measurement_btn = QPushButton("开始测量")
        self.start_measurement_btn.clicked.connect(self.start_measurement)
        self.start_measurement_btn.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 8px;")
        
        self.stop_measurement_btn = QPushButton("停止测量")
        self.stop_measurement_btn.clicked.connect(self.stop_measurement)
        self.stop_measurement_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 8px;")
        
        self.hold_btn = QPushButton("保持读数")
        self.hold_btn.clicked.connect(self.hold_reading)
        self.hold_btn.setStyleSheet("background-color: #ffc107; color: #212529; font-weight: bold; padding: 8px;")
        
        self.clear_history_btn = QPushButton("清空历史")
        self.clear_history_btn.clicked.connect(self.clear_history)
        self.clear_history_btn.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 8px;")
        
        measurement_layout.addWidget(self.start_measurement_btn)
        measurement_layout.addWidget(self.stop_measurement_btn)
        measurement_layout.addWidget(self.hold_btn)
        measurement_layout.addWidget(self.clear_history_btn)
        
        measurement_group.setLayout(measurement_layout)
        right_panel.addWidget(measurement_group)
        
        # 实时信息组
        info_group = QGroupBox("实时信息")
        info_layout = QGridLayout()
        
        self.pressure_label = QLabel("当前压力: -- N")
        self.net_pressure_label = QLabel("净压力: -- N")
        self.stability_label = QLabel("稳定性: --")
        self.measurement_status_label = QLabel("测量状态: 停止")
        self.measurement_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        info_layout.addWidget(self.pressure_label, 0, 0)
        info_layout.addWidget(self.net_pressure_label, 0, 1)
        info_layout.addWidget(self.stability_label, 1, 0)
        info_layout.addWidget(self.measurement_status_label, 1, 1)
        
        info_group.setLayout(info_layout)
        right_panel.addWidget(info_group)
        
        # 历史记录组
        history_group = QGroupBox("历史记录")
        history_layout = QVBoxLayout()
        
        # 历史图表
        self.history_plot = pg.GraphicsLayoutWidget()
        self.history_plot.setFixedHeight(200)
        self.history_widget = self.history_plot.addPlot()
        self.history_widget.setTitle('重量变化曲线')
        self.history_widget.setLabel('left', '重量', 'g')
        self.history_widget.setLabel('bottom', '时间', 's')
        self.history_curve = self.history_widget.plot(pen='g')
        
        history_layout.addWidget(self.history_plot)
        
        history_group.setLayout(history_layout)
        right_panel.addWidget(history_group)
        
        main_layout.addLayout(right_panel, 75)
        
        # 设置窗口属性
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # 初始化UI状态
        self.update_ui_state()
    
    def update_ui_state(self):
        """更新UI状态"""
        self.start_button.setEnabled(not self.is_running)
        self.stop_button.setEnabled(self.is_running)
        self.port_input.setEnabled(not self.is_running)
        self.sensor_combo.setEnabled(not self.is_running)
        
        self.start_measurement_btn.setEnabled(self.is_running and not self.measurement_active)
        self.stop_measurement_btn.setEnabled(self.measurement_active)
    
    def on_sensor_changed(self, sensor_id_text):
        """传感器选择变化时的处理函数"""
        if not self.is_running:
            print(f"🔄 传感器选择变化为: {sensor_id_text}")
    
    def start_sensor(self):
        """开始传感器连接"""
        if self.is_running:
            return
            
        port = self.port_input.text()
        print(f"🔍 尝试连接传感器，端口: {port}")
        
        success = self.data_handler.connect(port)
        if success:
            self.is_running = True
            self.timer.start(100)  # 100ms更新频率
            self.update_ui_state()
            self.status_label.setText("状态: 已连接")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            print("✅ 传感器连接成功")
        else:
            self.status_label.setText("状态: 连接失败")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            print("❌ 传感器连接失败")
            QMessageBox.warning(self, "连接失败", f"传感器连接失败，端口: {port}")
    
    def stop_sensor(self):
        """停止传感器连接"""
        if not self.is_running:
            return
        
        self.data_handler.disconnect()
        self.is_running = False
        self.timer.stop()
        self.update_ui_state()
        self.status_label.setText("状态: 已断开")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        print("✅ 传感器已断开")
    
    def load_balance_calibration(self):
        """加载balance-sensor校准文件"""
        file_path, _ = QFileDialog.getOpenFileName(
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
                QMessageBox.warning(self, "警告", f"加载校准文件失败:\n{file_path}")
    
    def save_calibration(self):
        """保存校准数据"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存校准文件",
            "",
            "JSON文件 (*.json);;NumPy文件 (*.npy);;CSV文件 (*.csv)"
        )
        
        if file_path:
            try:
                calibration_data = {
                    'coefficient': self.calibration_coefficient,
                    'bias': self.calibration_bias,
                    'description': '传感器校准数据',
                    'timestamp': QtCore.QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')
                }
                
                if file_path.endswith('.json'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(calibration_data, f, indent=2, ensure_ascii=False)
                elif file_path.endswith('.npy'):
                    np.save(file_path, calibration_data)
                elif file_path.endswith('.csv'):
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        f.write("coefficient,bias\n")
                        f.write(f"{self.calibration_coefficient},{self.calibration_bias}\n")
                
                print(f"✅ 校准数据已保存: {file_path}")
                QMessageBox.information(self, "成功", f"校准数据已保存到:\n{file_path}")
                
            except Exception as e:
                print(f"⚠️ 保存校准数据失败: {e}")
                QMessageBox.critical(self, "错误", f"保存校准数据失败:\n{str(e)}")
    
    def update_calibration_info(self):
        """更新校准信息显示"""
        info = self.data_handler.get_balance_calibration_info()
        if info:
            info_text = f"校准状态: 已加载\n"
            info_text += f"系数: {info['coefficient']:.4f}\n"
            info_text += f"偏置: {info['bias']:.4f} g\n"
            
            if 'calibration_map_shape' in info:
                info_text += f"校准映射: {info['calibration_map_shape']}\n"
                info_text += f"映射均值: {info['calibration_map_mean']:.4f}"
            
            self.calibration_info_label.setText(info_text)
            self.calibration_info_label.setStyleSheet("font-size: 11px; color: #28a745; font-family: monospace; background-color: #d4edda; padding: 8px; border: 1px solid #c3e6cb; border-radius: 4px;")
        else:
            self.calibration_info_label.setText("未加载校准文件")
            self.calibration_info_label.setStyleSheet("font-size: 11px; color: #666; font-family: monospace; background-color: #f8f9fa; padding: 8px; border: 1px solid #dee2e6; border-radius: 4px;")
    
    def on_coefficient_changed(self, text):
        """系数输入框变化时的处理"""
        try:
            self.calibration_coefficient = float(text)
            self.update_formula_display()
            self.update_params_display()
        except ValueError:
            self.current_params_label.setText("当前参数: 无效输入")
    
    def on_bias_changed(self, text):
        """偏置输入框变化时的处理"""
        try:
            self.calibration_bias = float(text)
            self.update_formula_display()
            self.update_params_display()
        except ValueError:
            self.current_params_label.setText("当前参数: 无效输入")
    
    def update_formula_display(self):
        """更新公式显示"""
        self.formula_label.setText(f"公式: 质量 = {self.calibration_coefficient:.4f} × 压力 + {self.calibration_bias:.4f}")
    
    def update_params_display(self):
        """更新参数显示"""
        self.current_params_label.setText(f"当前参数: k={self.calibration_coefficient:.4f}, b={self.calibration_bias:.4f}")
    
    def perform_zero(self):
        """执行归零操作"""
        if not self.is_running:
            QMessageBox.warning(self, "警告", "请先连接传感器")
            return
        
        # 获取当前压力总和作为归零基准
        if len(self.data_handler.value) > 0:
            current_pressure = np.sum(self.data_handler.value[-1])
            self.zero_pressure = current_pressure
            self.is_zeroed = True
            
            self.zero_status_label.setText("状态: 已归零")
            self.zero_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.zero_pressure_label.setText(f"归零压力: {self.zero_pressure:.4f} N")
            
            print(f"✅ 归零成功，基准压力: {self.zero_pressure:.4f} N")
        else:
            QMessageBox.warning(self, "警告", "没有可用的传感器数据")
    
    def start_measurement(self):
        """开始测量"""
        if not self.is_running:
            QMessageBox.warning(self, "警告", "请先连接传感器")
            return
        
        self.measurement_active = True
        self.update_ui_state()
        self.measurement_status_label.setText("测量状态: 测量中")
        self.measurement_status_label.setStyleSheet("color: green; font-weight: bold;")
        print("✅ 开始测量")
    
    def stop_measurement(self):
        """停止测量"""
        self.measurement_active = False
        self.update_ui_state()
        self.measurement_status_label.setText("测量状态: 停止")
        self.measurement_status_label.setStyleSheet("color: red; font-weight: bold;")
        print("✅ 停止测量")
    
    def hold_reading(self):
        """保持读数"""
        if self.measurement_active:
            self.measurement_status_label.setText("测量状态: 保持")
            self.measurement_status_label.setStyleSheet("color: orange; font-weight: bold;")
            print("✅ 保持读数")
    
    def clear_history(self):
        """清空历史记录"""
        self.weight_history.clear()
        self.history_curve.setData([], [])
        print("✅ 历史记录已清空")
    
    def calculate_weight(self, pressure_data):
        """计算重量"""
        if not self.is_zeroed:
            return 0.0
        
        # 计算净压力（当前压力 - 归零压力）
        current_pressure = np.sum(pressure_data)
        net_pressure = current_pressure - self.zero_pressure
        
        # 应用校准公式：质量 = k × 压力 + b
        weight = self.calibration_coefficient * net_pressure + self.calibration_bias
        
        return weight
    
    def update_weight_display(self, weight):
        """更新重量显示"""
        self.current_weight = weight
        self.weight_display.display(f"{weight:.3f}")
        
        # 添加到历史记录
        self.weight_history.append(weight)
        if len(self.weight_history) > self.max_history_length:
            self.weight_history.pop(0)
        
        # 更新历史图表
        if len(self.weight_history) > 1:
            time_points = list(range(len(self.weight_history)))
            self.history_curve.setData(time_points, self.weight_history)
    
    def process_pressure_data(self, pressure_data):
        """处理压力数据"""
        if not self.measurement_active:
            return
        
        # 计算重量
        weight = self.calculate_weight(pressure_data)
        
        # 更新重量显示
        self.update_weight_display(weight)
        
        # 更新实时信息
        current_pressure = np.sum(pressure_data)
        net_pressure = current_pressure - self.zero_pressure if self.is_zeroed else current_pressure
        
        self.pressure_label.setText(f"当前压力: {current_pressure:.4f} N")
        self.net_pressure_label.setText(f"净压力: {net_pressure:.4f} N")
        
        # 计算稳定性（简单的标准差）
        if len(self.weight_history) > 5:
            recent_weights = self.weight_history[-5:]
            stability = np.std(recent_weights)
            self.stability_label.setText(f"稳定性: {stability:.3f}")
        else:
            self.stability_label.setText("稳定性: --")
    
    def update_heatmap(self, pressure_data):
        """更新热力图显示"""
        try:
            if pressure_data is None or pressure_data.size == 0:
                return
            
            # 确保数据是64x64
            if pressure_data.shape != (64, 64):
                print(f"⚠️ 压力数据形状不正确: {pressure_data.shape}, 期望 (64, 64)")
                return
            
            # 转置数据以正确显示坐标
            transposed_data = pressure_data.T
            
            # 更新热力图图像，直接设置到0-64范围
            self.heatmap_image.setImage(transposed_data, pos=[0, 0], scale=[1, 1])
            
            # 强制重新设置坐标轴范围，确保正方形显示
            self.heatmap_widget.setXRange(0, 64)
            self.heatmap_widget.setYRange(0, 64)
            
            # 更新颜色条范围
            data_min = np.min(pressure_data)
            data_max = np.max(pressure_data)
            self.heatmap_colorbar.setLevels((data_min, data_max))
            
            # 更新信息标签
            total_pressure = np.sum(pressure_data)
            mean_pressure = np.mean(pressure_data)
            max_pressure = np.max(pressure_data)
            
            info_text = f"总压力: {total_pressure:.2f}N\n"
            info_text += f"平均压力: {mean_pressure:.3f}N\n"
            info_text += f"最大压力: {max_pressure:.3f}N\n"
            info_text += f"数据范围: [{data_min:.3f}, {data_max:.3f}]"
            
            self.heatmap_info_label.setText(info_text)
            
        except Exception as e:
            print(f"⚠️ 更新热力图失败: {e}")
            self.heatmap_info_label.setText("热力图更新失败")
    
    def auto_scale_heatmap(self):
        """自动缩放热力图"""
        try:
            if hasattr(self, 'heatmap_widget'):
                self.heatmap_widget.autoRange()
                print("✅ 热力图已自动缩放")
        except Exception as e:
            print(f"⚠️ 自动缩放失败: {e}")
    
    def reset_heatmap_scale(self):
        """重置热力图缩放"""
        try:
            if hasattr(self, 'heatmap_widget'):
                # 重置到默认视图：X轴0-64，Y轴0-64
                self.heatmap_widget.setXRange(0, 64)
                self.heatmap_widget.setYRange(0, 64)
                print("✅ 热力图缩放已重置")
        except Exception as e:
            print(f"⚠️ 重置缩放失败: {e}")
    
    def update_data(self):
        """更新数据显示"""
        try:
            # 触发数据获取
            self.data_handler.trigger()
            
            # 获取最新数据
            if len(self.data_handler.value) > 0:
                # 获取校准后的数据
                calibrated_data = self.data_handler.value[-1]
                
                # 更新热力图
                self.update_heatmap(calibrated_data)
                
                # 更新压力信息
                total_pressure = np.sum(calibrated_data)
                max_pressure = np.max(calibrated_data)
                min_pressure = np.min(calibrated_data)
                
                self.total_pressure_label.setText(f"总压力: {total_pressure:.4f} N")
                self.max_pressure_label.setText(f"最大压力: {max_pressure:.4f} N")
                self.min_pressure_label.setText(f"最小压力: {min_pressure:.4f} N")
                
                # 处理称重数据
                self.process_pressure_data(calibrated_data)
                
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
    window = WeightMeasurementInterface()
    
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 