#!/usr/bin/env python3
"""
双校准比较对话框

重构版本：使用模块化的管理器类
"""

import sys
import os
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QPushButton, QSlider, QSpinBox, QGroupBox,
                             QScrollArea, QWidget, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

# 导入重构后的管理器类
from .managers.heatmap_manager import HeatmapManager
from .managers.statistics_manager import StatisticsManager
from .managers.region_application_manager import RegionApplicationManager
from .managers.comparison_manager import ComparisonManager
from .managers.taring_manager import TaringManager
from .managers.region_detection import RegionDetector  # 🔧 修复：使用managers目录下的新版本
from .utils.region_renderer import RegionRenderer
from .utils.configuration import ConfigurationManager

class DualCalibrationComparisonDialog(QtWidgets.QDialog):
    """双校准器实时比较对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # 🆕 新增：区域数量配置默认值 - 必须在setup_ui之前初始化
        self.default_region_count = 2  # 默认检测2个区域
        self.max_region_count = 10     # 最大支持10个区域
        
        # 🔧 重构：初始化管理器类
        self.heatmap_manager = HeatmapManager()
        self.region_detector = RegionDetector()
        
        # 🆕 新增：自动加载torch校准包
        calibration_package_path = "calibration_package.pt"
        if os.path.exists(calibration_package_path):
            print(f"🔧 自动加载torch校准包: {calibration_package_path}")
            if self.region_detector.load_torch_calibration_package(calibration_package_path):
                print("✅ torch校准包加载成功，压强转换功能已启用")
            else:
                print("⚠️ torch校准包加载失败，压强转换功能将使用备用方法")
        else:
            print(f"⚠️ 校准包文件不存在: {calibration_package_path}，压强转换功能将使用备用方法")
        
        self.region_renderer = RegionRenderer(self.heatmap_manager)
        self.statistics_manager = StatisticsManager()
        self.region_application_manager = RegionApplicationManager(
            self.heatmap_manager, 
            self.region_renderer, 
            self.statistics_manager
        )
        # 🆕 新增：传递RegionDetector引用给RegionApplicationManager
        self.region_application_manager.region_detector = self.region_detector
        self.comparison_manager = ComparisonManager()
        self.taring_manager = TaringManager(self)
        self.configuration_manager = ConfigurationManager()
        
        self.setup_ui()
        self.setup_timer()
        self._update_count = 0
        self._pressure_patches = []  # 保存压力区域的图形元素
        # 🔧 新增：保存基准数据用于区域选取
        self.baseline_raw_data = None      # 🔧 修复：没有按压时的原始数据（不是校准后的数据）
        self.baseline_pressure_data = None  # 没有按压时的压力数据
    
    def setup_ui(self):
        """设置用户界面"""
        try:
            print("🔧 开始设置双校准器比较对话框UI...")
            
            # 检查校准器状态（但不阻止UI创建）
            try:
                if hasattr(self.parent, 'calibration_manager'):
                    print(f"✅ 找到calibration_manager")
                    if hasattr(self.parent.calibration_manager, 'dual_calibration_mode'):
                        print(f"   校准模式: {'新版本校准' if self.parent.calibration_manager.dual_calibration_mode else '单校准器'}")
                    else:
                        print(f"   校准模式: 未知")
                    
                    if hasattr(self.parent.calibration_manager, 'new_calibrator'):
                        print(f"   新版本校准器: {self.parent.calibration_manager.new_calibrator is not None}")
                    else:
                        print(f"   新版本校准器: 未找到")
                else:
                    print("⚠️ 未找到calibration_manager，将创建基本UI")
            except Exception as e:
                print(f"⚠️ 检查校准器状态时出错: {e}，继续创建UI")
            
            self.setWindowTitle("新版本校准器实时监控")
            self.setGeometry(100, 100, 1400, 800)
            
            # 主布局
            layout = QtWidgets.QVBoxLayout()
            
            # 标题
            title_label = QtWidgets.QLabel("新版本校准器实时监控")
            title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
            title_label.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(title_label)
            
            # 控制按钮
            control_layout = QtWidgets.QHBoxLayout()
            
            self.button_start_stop = QtWidgets.QPushButton("开始比较")
            self.button_start_stop.clicked.connect(self.toggle_comparison)
            self.button_start_stop.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(self.button_start_stop)
            
            # 添加去皮功能按钮
            self.button_taring = QtWidgets.QPushButton("执行去皮")
            self.button_taring.clicked.connect(self.perform_taring)
            self.button_taring.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(self.button_taring)
            
            self.button_reset_taring = QtWidgets.QPushButton("重置去皮")
            self.button_reset_taring.clicked.connect(self.reset_taring)
            self.button_reset_taring.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(self.button_reset_taring)
            
            # 🔍 新增：形态学区域识别控制
            control_layout.addWidget(QtWidgets.QLabel("区域识别阈值:"))
            self.threshold_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.threshold_slider.setRange(50, 95)
            self.threshold_slider.setValue(80)
            self.threshold_slider.setToolTip("调整压力区域识别的阈值百分位数")
            self.threshold_slider.valueChanged.connect(self.on_threshold_changed)
            control_layout.addWidget(self.threshold_slider)
            
            self.threshold_label = QtWidgets.QLabel("80%")
            self.threshold_label.setStyleSheet("color: #2c3e50; font-weight: bold; min-width: 40px;")
            control_layout.addWidget(self.threshold_label)
            
            # 🆕 新增：区域数量配置控制
            control_layout.addWidget(QtWidgets.QLabel("检测区域数量:"))
            self.region_count_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.region_count_slider.setRange(1, self.max_region_count)  # 支持1-10个区域
            self.region_count_slider.setValue(self.default_region_count)  # 默认检测2个区域
            self.region_count_slider.setToolTip(f"选择要检测的压力区域数量 (1-{self.max_region_count})")
            self.region_count_slider.valueChanged.connect(self.on_region_count_changed)
            control_layout.addWidget(self.region_count_slider)
            
            self.region_count_config_label = QtWidgets.QLabel(f"{self.default_region_count}")
            self.region_count_config_label.setStyleSheet("color: #e74c3c; font-weight: bold; min-width: 30px;")
            control_layout.addWidget(self.region_count_config_label)
            
            # 添加区域数量显示标签
            self.region_count_label = QtWidgets.QLabel("区域: 0")
            self.region_count_label.setStyleSheet("color: #e74c3c; font-weight: bold; min-width: 60px;")
            control_layout.addWidget(self.region_count_label)
            
            self.button_identify_regions = QtWidgets.QPushButton("重新识别区域")
            self.button_identify_regions.clicked.connect(self.manual_identify_regions)
            self.button_identify_regions.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(self.button_identify_regions)
            
            self.button_save_screenshot = QtWidgets.QPushButton("保存截图")
            self.button_save_screenshot.clicked.connect(self.save_screenshot)
            self.button_save_screenshot.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(self.button_save_screenshot)
            
            self.button_close = QtWidgets.QPushButton("关闭")
            self.button_close.clicked.connect(self.close)
            self.button_close.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(self.button_close)
            
            # 添加设置基准数据按钮
            self.button_set_baseline = QtWidgets.QPushButton("设置区域选取基准")
            self.button_set_baseline.clicked.connect(self.set_baseline_for_region_selection)
            self.button_set_baseline.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(self.button_set_baseline)
            
            # 添加重置基准数据按钮
            self.button_reset_baseline = QtWidgets.QPushButton("重置区域选取基准")
            self.button_reset_baseline.clicked.connect(self.reset_baseline_for_region_selection)
            self.button_reset_baseline.setStyleSheet("background-color: #95a5a6; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(self.button_reset_baseline)


            control_layout.addStretch()
            layout.addLayout(control_layout)
            
            # 热力图显示区域
            heatmap_layout = QtWidgets.QHBoxLayout()
            
            # 原始数据热力图
            raw_group = QtWidgets.QGroupBox("原始数据")
            raw_layout = QtWidgets.QVBoxLayout()
            self.raw_canvas = self.create_heatmap_canvas("原始数据")
            raw_layout.addWidget(self.raw_canvas)
            raw_group.setLayout(raw_layout)
            heatmap_layout.addWidget(raw_group)
            
            # 新版本校准结果热力图
            # 🆕 修复：总是创建新版本校准热力图，不依赖校准器状态
            new_group = QtWidgets.QGroupBox("新版本校准")
            new_layout = QtWidgets.QVBoxLayout()
            self.new_canvas = self.create_heatmap_canvas("新版本校准")
            new_layout.addWidget(self.new_canvas)
            new_group.setLayout(new_layout)
            heatmap_layout.addWidget(new_group)
            
            # 🆕 新增：Group Box: 用于显示去除基准数据后的变化量
            change_data_group = QtWidgets.QGroupBox("去除基准后的变化量")
            change_data_layout = QtWidgets.QVBoxLayout()
            self.change_data_canvas = self.create_heatmap_canvas("变化量数据")
            change_data_layout.addWidget(self.change_data_canvas)
            change_data_group.setLayout(change_data_layout)
            heatmap_layout.addWidget(change_data_group)
            
            # 🆕 新增：Group Box: 用于显示选中区域的新版本校准数据
            region_calibration_group = QtWidgets.QGroupBox("选中区域的新版本校准数据")
            region_calibration_layout = QtWidgets.QVBoxLayout()
            self.region_calibration_canvas = self.create_heatmap_canvas("区域新版本校准数据")
            region_calibration_layout.addWidget(self.region_calibration_canvas)
            region_calibration_group.setLayout(region_calibration_layout)
            heatmap_layout.addWidget(region_calibration_group)
            
            # 🆕 新增：Group Box: 用于显示检测区域的压强热力图
            pressure_heatmap_group = QtWidgets.QGroupBox("检测区域压强热力图")
            pressure_heatmap_layout = QtWidgets.QVBoxLayout()
            self.pressure_heatmap_canvas = self.create_heatmap_canvas("检测区域压强 (N)")
            pressure_heatmap_layout.addWidget(self.pressure_heatmap_canvas)
            pressure_heatmap_group.setLayout(pressure_heatmap_layout)
            heatmap_layout.addWidget(pressure_heatmap_group)
            
            layout.addLayout(heatmap_layout)
            
            # 统计信息显示区域
            stats_layout = QtWidgets.QHBoxLayout()
            
            # 原始数据统计
            raw_stats_group = QtWidgets.QGroupBox("原始数据统计")
            raw_stats_layout = QtWidgets.QVBoxLayout()
            
            # 🆕 新增：创建详细的统计标签
            self.raw_mean_label = QtWidgets.QLabel("均值: 等待数据...")
            self.raw_std_label = QtWidgets.QLabel("标准差: 等待数据...")
            self.raw_min_label = QtWidgets.QLabel("最小值: 等待数据...")
            self.raw_max_label = QtWidgets.QLabel("最大值: 等待数据...")
            self.raw_range_label = QtWidgets.QLabel("范围: 等待数据...")
            
            # 设置样式
            for label in [self.raw_mean_label, self.raw_std_label, self.raw_min_label, self.raw_max_label, self.raw_range_label]:
                label.setStyleSheet("font-family: monospace; font-size: 11px; color: #3498db;")
                raw_stats_layout.addWidget(label)
            
            raw_stats_group.setLayout(raw_stats_layout)
            stats_layout.addWidget(raw_stats_group)
            
            # 新版本校准统计
            # 🆕 修复：总是创建新版本校准统计，不依赖校准器状态
            new_stats_group = QtWidgets.QGroupBox("新版本校准统计")
            new_stats_layout = QtWidgets.QVBoxLayout()
            
            # 🆕 新增：创建详细的统计标签
            self.new_mean_label = QtWidgets.QLabel("均值: 等待数据...")
            self.new_std_label = QtWidgets.QLabel("标准差: 等待数据...")
            self.new_min_label = QtWidgets.QLabel("最小值: 等待数据...")
            self.new_max_label = QtWidgets.QLabel("最大值: 等待数据...")
            self.new_range_label = QtWidgets.QLabel("范围: 等待数据...")
            
            # 设置样式
            for label in [self.new_mean_label, self.new_std_label, self.new_min_label, self.new_max_label, self.new_range_label]:
                label.setStyleSheet("font-family: monospace; font-size: 11px; color: #e74c3c;")
                new_stats_layout.addWidget(label)
            
            new_stats_group.setLayout(new_stats_layout)
            stats_layout.addWidget(new_stats_group)
            
            # 🆕 新增：变化量数据统计框
            self.change_data_stats_group = QtWidgets.QGroupBox("变化量数据统计")
            change_data_stats_layout = QtWidgets.QVBoxLayout()
            
            # 🆕 新增：创建详细的变化量统计标签
            self.change_data_mean_label = QtWidgets.QLabel("均值: 等待数据...")
            self.change_data_std_label = QtWidgets.QLabel("标准差: 等待数据...")
            self.change_data_min_label = QtWidgets.QLabel("最小值: 等待数据...")
            self.change_data_max_label = QtWidgets.QLabel("最大值: 等待数据...")
            self.change_data_range_label = QtWidgets.QLabel("范围: 等待数据...")
            
            # 设置样式
            for label in [self.change_data_mean_label, self.change_data_std_label, self.change_data_min_label, self.change_data_max_label, self.change_data_range_label]:
                label.setStyleSheet("font-family: monospace; font-size: 11px; color: #f39c12;")
                change_data_stats_layout.addWidget(label)
            
            self.change_data_stats_group.setLayout(change_data_stats_layout)
            stats_layout.addWidget(self.change_data_stats_group)
            
            # 🆕 新增：区域校准值统计框
            self.region_calibration_stats_group = QtWidgets.QGroupBox("选中区域的新版本校准统计")
            region_calibration_stats_layout = QtWidgets.QVBoxLayout()
            
            # 🆕 新增：创建详细的区域校准值统计标签
            self.region_calibration_mean_label = QtWidgets.QLabel("均值: 等待数据...")
            self.region_calibration_std_label = QtWidgets.QLabel("标准差: 等待数据...")
            self.region_calibration_min_label = QtWidgets.QLabel("最小值: 等待数据...")
            self.region_calibration_max_label = QtWidgets.QLabel("最大值: 等待数据...")
            self.region_calibration_range_label = QtWidgets.QLabel("范围: 等待数据...")
            self.region_calibration_sum_label = QtWidgets.QLabel("总和: 等待数据...")
            
            # 设置样式
            for label in [self.region_calibration_mean_label, self.region_calibration_std_label, 
                         self.region_calibration_min_label, self.region_calibration_max_label, 
                         self.region_calibration_range_label, self.region_calibration_sum_label]:
                label.setStyleSheet("font-family: monospace; font-size: 11px; color: #e67e22;")
                region_calibration_stats_layout.addWidget(label)
            
            self.region_calibration_stats_group.setLayout(region_calibration_stats_layout)
            stats_layout.addWidget(self.region_calibration_stats_group)
            
            # 🆕 新增：检测区域压强统计框
            self.pressure_heatmap_stats_group = QtWidgets.QGroupBox("检测区域压强统计")
            pressure_heatmap_stats_layout = QtWidgets.QVBoxLayout()
            
            # 🆕 新增：创建详细的压强统计标签
            self.pressure_heatmap_mean_label = QtWidgets.QLabel("平均压强: 等待数据...")
            self.pressure_heatmap_max_label = QtWidgets.QLabel("最大压强: 等待数据...")
            self.pressure_heatmap_min_label = QtWidgets.QLabel("最小压强: 等待数据...")
            self.pressure_heatmap_total_force_label = QtWidgets.QLabel("总力: 等待数据...")
            self.pressure_heatmap_regions_label = QtWidgets.QLabel("检测区域数: 等待数据...")
            
            # 设置样式
            for label in [self.pressure_heatmap_mean_label, self.pressure_heatmap_max_label, 
                         self.pressure_heatmap_min_label, self.pressure_heatmap_total_force_label,
                         self.pressure_heatmap_regions_label]:
                label.setStyleSheet("font-family: monospace; font-size: 11px; color: #9b59b6;")
                pressure_heatmap_stats_layout.addWidget(label)
            
            self.pressure_heatmap_stats_group.setLayout(pressure_heatmap_stats_layout)
            stats_layout.addWidget(self.pressure_heatmap_stats_group)
            
            # 🆕 新增：两个区域的独立统计显示
            # 区域1统计框
            region1_stats_group = QtWidgets.QGroupBox("区域1统计")
            region1_stats_layout = QtWidgets.QVBoxLayout()
            self.region1_stats_label = QtWidgets.QLabel("等待区域1数据...")
            self.region1_stats_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #e67e22;")
            region1_stats_layout.addWidget(self.region1_stats_label)
            region1_stats_group.setLayout(region1_stats_layout)
            stats_layout.addWidget(region1_stats_group)
            
            # 区域2统计框
            region2_stats_group = QtWidgets.QGroupBox("区域2统计")
            region2_stats_layout = QtWidgets.QVBoxLayout()
            self.region2_stats_label = QtWidgets.QLabel("等待区域2数据...")
            self.region2_stats_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #9b59b6;")
            region2_stats_layout.addWidget(self.region2_stats_label)
            region2_stats_group.setLayout(region2_stats_layout)
            stats_layout.addWidget(region2_stats_group)
            
            layout.addLayout(stats_layout)
            
            # 比较结果
            comparison_group = QtWidgets.QGroupBox("比较结果")
            comparison_layout = QtWidgets.QVBoxLayout()
            self.comparison_label = QtWidgets.QLabel("等待比较数据...")
            self.comparison_label.setStyleSheet("font-family: monospace; font-size: 12px; color: #e74c3c;")
            comparison_layout.addWidget(self.comparison_label)
            comparison_group.setLayout(comparison_layout)
            layout.addWidget(comparison_group)
            
            self.setLayout(layout)
            print("✅ 双校准器比较对话框UI设置完成")
            
            # 🆕 新增：加载用户配置偏好
            self.load_user_preferences()
            
            # 🔧 重构：设置统计管理器的标签
            self.statistics_manager.setup_raw_labels({
                'mean': self.raw_mean_label,
                'std': self.raw_std_label,
                'min': self.raw_min_label,
                'max': self.raw_max_label,
                'range': self.raw_range_label
            })
            
            if hasattr(self, 'new_mean_label'):
                self.statistics_manager.setup_new_labels({
                    'mean': self.new_mean_label,
                    'std': self.new_std_label,
                    'min': self.new_min_label,
                    'max': self.new_max_label,
                    'range': self.new_range_label
                })
            
            # 🆕 新增：设置变化量统计标签
            if hasattr(self, 'change_data_mean_label'):
                self.statistics_manager.setup_change_data_labels({
                    'mean': self.change_data_mean_label,
                    'std': self.change_data_std_label,
                    'min': self.change_data_min_label,
                    'max': self.change_data_max_label,
                    'range': self.change_data_range_label
                })
            
            # 🆕 新增：设置区域校准值统计标签
            if hasattr(self, 'region_calibration_mean_label'):
                self.statistics_manager.setup_region_calibration_labels({
                    'mean': self.region_calibration_mean_label,
                    'std': self.region_calibration_std_label,
                    'min': self.region_calibration_min_label,
                    'max': self.region_calibration_max_label,
                    'range': self.region_calibration_range_label,
                    'sum': self.region_calibration_sum_label
                })
            
            # 🆕 新增：设置压强热力图统计标签
            if hasattr(self, 'pressure_heatmap_mean_label'):
                self.statistics_manager.setup_pressure_heatmap_labels({
                    'mean': self.pressure_heatmap_mean_label,
                    'max': self.pressure_heatmap_max_label,
                    'min': self.pressure_heatmap_min_label,
                    'total_force': self.pressure_heatmap_total_force_label,
                    'regions': self.pressure_heatmap_regions_label
                })
            
            # 设置比较管理器的标签
            self.comparison_manager.set_comparison_label(self.comparison_label)
            
        except Exception as e:
            print(f"❌ 设置双校准器比较对话框UI失败: {e}")
            import traceback
            traceback.print_exc()
    
    def update_single_heatmap(self, canvas, data):
        """辅助函数：更新单个热力图"""
        self.heatmap_manager.update_single_heatmap(canvas, data)
    
    def set_baseline_for_region_selection(self):
        """设置区域选取的基准数据（没有按压时的状态）"""
        try:
            if hasattr(self.parent, 'calibration_manager'):
                # 🔧 修复：获取当前帧的原始数据作为基准（不是校准后的数据）
                raw_data = self.parent.calibration_handler._get_current_frame_data()
                
                # 🔧 修复：保存原始数据作为基准，不是校准后的数据
                self.baseline_raw_data = raw_data.copy()
                
                # 获取校准结果用于压力基准（如果有的话）
                calibration_results = self.parent.calibration_manager.apply_dual_calibration(raw_data)
                if 'new' in calibration_results and 'pressure_data' in calibration_results['new']:
                    self.baseline_pressure_data = calibration_results['new']['pressure_data'].copy()
                else:
                    self.baseline_pressure_data = None
                
                # 🆕 新增：保存基准校准数据，用于变化量计算
                if 'new' in calibration_results and 'data' in calibration_results['new']:
                    self.baseline_calibrated_data = calibration_results['new']['data'].copy()
                    print(f"   🔧 基准校准数据已保存，范围: [{self.baseline_calibrated_data.min():.2f}, {self.baseline_calibrated_data.max():.2f}]")
                else:
                    self.baseline_calibrated_data = None
                    print(f"   ⚠️ 无法获取基准校准数据")
                
                # 🔧 修复：使用RegionDetector设置基准数据（只传递原始数据）
                self.region_detector.set_baseline_data(self.baseline_raw_data)
                
                print(f"✅ 区域选取基准数据设置完成:")
                print(f"   原始基准数据范围: [{self.baseline_raw_data.min():.2f}, {self.baseline_raw_data.max():.2f}]")
                if self.baseline_pressure_data is not None:
                    print(f"   压力基准数据范围: [{self.baseline_pressure_data.min():.2f}N, {self.baseline_pressure_data.max():.2f}N]")
                print(f"   现在区域选取将基于变化量进行识别")
                
                QtWidgets.QMessageBox.information(self, "成功", "区域选取基准数据设置完成！\n\n现在区域选取将基于变化量进行识别，更准确地找到压力区域。")
            else:
                QtWidgets.QMessageBox.warning(self, "失败", "无法访问校准管理器")
                
        except Exception as e:
            print(f"❌ 设置区域选取基准数据失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"设置基准数据失败:\n{str(e)}")

    def reset_baseline_for_region_selection(self):
        """重置区域选取的基准数据"""
        try:
            self.baseline_raw_data = None
            self.baseline_pressure_data = None
            self.baseline_calibrated_data = None  # 🆕 新增：清空基准校准数据
            
            # 使用RegionDetector重置基准数据
            self.region_detector.reset_baseline_data()
            
            print("✅ 区域选取基准数据已重置")
            QtWidgets.QMessageBox.information(self, "成功", "区域选取基准数据已重置！\n\n现在区域选取将基于绝对值进行识别。")
            
        except Exception as e:
            print(f"❌ 重置区域选取基准数据失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"重置基准数据失败:\n{str(e)}")
            
    def create_heatmap_canvas(self, title):
        """创建热力图画布"""
        return self.heatmap_manager.create_heatmap_canvas(title)
    
    def identify_pressure_regions_morphological(self, pressure_data, threshold_percentile=80):
        """使用轮廓跟踪方法识别压力区域点"""
        try:
            print(f"🔍 开始轮廓跟踪压力区域识别...")
            print(f"   压力数据范围: [{pressure_data.min():.2f}N, {pressure_data.max():.2f}N]")

            # 1. 阈值分割：使用百分位数确定阈值
            threshold = np.percentile(pressure_data, threshold_percentile)
            print(f"   阈值 (第{threshold_percentile}百分位): {threshold:.2f}N")

            # 2. 二值化
            binary_mask = pressure_data > threshold
            print(f"   二值化后激活点数: {binary_mask.sum()}")

            # 3. 形态学操作：开运算去除噪声（使用更小的核）
            kernel_size = 2  # 减小核大小，保留更多细节
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            opened_mask = cv2.morphologyEx(binary_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
            print(f"   开运算后激活点数: {opened_mask.sum()}")

            # 4. 形态学操作：闭运算填充小孔
            closed_mask = cv2.morphologyEx(opened_mask, cv2.MORPH_CLOSE, kernel)
            print(f"   闭运算后激活点数: {closed_mask.sum()}")

            # 5. 轮廓检测
            contours, hierarchy = cv2.findContours(closed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            print(f"   检测到轮廓数量: {len(contours)}")

            # 6. 轮廓筛选和分析
            filtered_regions = []
            min_contour_area = 3

            for i, contour in enumerate(contours):
                # 计算轮廓面积
                contour_area = cv2.contourArea(contour)

                if contour_area >= min_contour_area:
                    # 计算轮廓中心
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        center_x = int(M["m10"] / M["m00"])
                        center_y = int(M["m01"] / M["m00"])
                    else:
                        # 如果矩计算失败，使用轮廓的边界框中心
                        x, y, w, h = cv2.boundingRect(contour)
                        center_x = int(x + w/2)
                        center_y = int(y + h/2)

                    # 计算边界框
                    x, y, w, h = cv2.boundingRect(contour)

                    # 计算区域平均压力
                    contour_mask = np.zeros_like(closed_mask)
                    cv2.fillPoly(contour_mask, [contour], 1)
                    region_pressure_values = pressure_data[contour_mask == 1]
                    region_avg_pressure = region_pressure_values.mean()

                    # 计算轮廓周长和紧凑度
                    perimeter = cv2.arcLength(contour, True)
                    compactness = (contour_area * 4 * np.pi) / (perimeter ** 2) if perimeter > 0 else 0

                    region_info = {
                        'id': i + 1,
                        'center': (center_x, center_y),
                        'bbox': (x, y, x + w, y + h),
                        'area': int(contour_area),
                        'avg_pressure': region_avg_pressure,
                        'contour': contour,  # 保存原始轮廓
                        'contour_mask': contour_mask,
                        'perimeter': perimeter,
                        'compactness': compactness,
                        'method': 'contour_tracing'
                    }
                    filtered_regions.append(region_info)

                    print(f"   区域 {i+1}: 中心({center_x}, {center_y}), 面积{contour_area:.1f}, "
                          f"周长{perimeter:.1f}, 紧凑度{compactness:.3f}")

            # 7. 按面积排序，选择最大的区域
            if filtered_regions:
                filtered_regions.sort(key=lambda x: x['area'], reverse=True)
                largest_region = filtered_regions[0]
                print(f"✅ 轮廓跟踪压力区域识别完成，选择面积最大的区域")
                print(f"   最大区域: ID={largest_region['id']}, 面积={largest_region['area']:.1f}, "
                      f"紧凑度={largest_region['compactness']:.3f}")
                return [largest_region]
            else:
                print("⚠️ 未识别出有效的压力区域")
                return []

        except Exception as e:
            print(f"❌ 轮廓跟踪压力区域识别失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def draw_pressure_regions_on_heatmap(self, ax, regions, color='red', linewidth=3):
        """在热力图上绘制识别出的压力区域"""
        self.region_renderer.draw_pressure_regions_on_heatmap(ax, regions, color, linewidth)
    
    def setup_timer(self):
        """设置定时器"""
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_comparison)
        self.comparison_running = False
        
    def toggle_comparison(self):
        """切换比较状态"""
        if self.comparison_running:
            self.stop_comparison()
        else:
            self.start_comparison()
    
    def start_comparison(self):
        """开始比较"""
        self.comparison_running = True
        self.button_start_stop.setText("停止比较")
        self.button_start_stop.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 8px;")
        self.timer.start(100)  # 100ms更新一次
        print("🔄 双校准器实时比较已开始")
        
    def stop_comparison(self):
        """停止比较"""
        self.comparison_running = False
        self.button_start_stop.setText("开始比较")
        self.button_start_stop.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        self.timer.stop()
        print("⏹️ 双校准器实时比较已停止")
        
    def update_comparison(self):
        """更新比较数据"""
        try:
            # 获取当前数据
            if hasattr(self.parent, 'calibration_handler'):
                raw_data = self.parent.calibration_handler._get_current_frame_data()
            else:
                raw_data = self.parent.get_current_frame_data()
            
            # 检查数据是否真的在变化
            if hasattr(self, '_last_raw_data'):
                if self._last_raw_data is not None:
                    # 检查数据是否全为零
                    if np.all(raw_data == 0):
                        print("⚠️ 检测到原始数据全为零，可能传感器未连接或数据采集异常")
                        # 即使数据为零，也要强制更新几次以显示校准效果
                        if not hasattr(self, '_zero_data_count'):
                            self._zero_data_count = 0
                        self._zero_data_count += 1
                        
                        # 每5次零数据时强制更新一次
                        if self._zero_data_count % 5 != 0:
                            return
                        else:
                            print(f"📊 数据为零，强制更新校准结果 #{self._update_count + 1}")
                    else:
                        # 数据不为零，检查是否有变化
                        data_diff = np.abs(raw_data - self._last_raw_data)
                        max_diff = np.max(data_diff)
                        
                        # 如果绝对变化小于阈值，认为数据基本不变
                        if max_diff < 1.0:  # 使用绝对阈值而不是相对阈值
                            if not hasattr(self, '_no_change_count'):
                                self._no_change_count = 0
                            self._no_change_count += 1
                            
                            # 每8次无变化时强制更新一次
                            if self._no_change_count % 8 != 0:
                                return
                            else:
                                print(f"📊 数据变化很小，强制更新校准结果 #{self._update_count + 1}")
                        else:
                            # 数据有变化，重置计数器
                            self._no_change_count = 0
                            self._zero_data_count = 0
                            print(f"🔄 检测到数据变化，最大变化: {max_diff:.4f}")
                else:
                    # 第一次运行，初始化
                    print("🔄 首次运行，初始化数据")
            else:
                # 第一次运行，初始化
                print("🔄 首次运行，初始化数据")
            
            self._last_raw_data = raw_data.copy()
            
            # 应用双校准器
            if hasattr(self.parent, 'calibration_manager'):
                calibration_results = self.parent.calibration_manager.apply_dual_calibration(raw_data)
            else:
                calibration_results = self.parent.apply_dual_calibration(raw_data)
            
            if calibration_results is None:
                print("⚠️ 双校准器应用失败，跳过更新")
                return
            
            self._update_count += 1
            print(f"🔄 更新双校准器比较数据 #{self._update_count}")
            
            # 更新热力图
            self.update_heatmaps(calibration_results)
            
            # 🎯 修复：在热力图更新完成后再更新统计信息，确保压力统计信息已准备好
            self.update_statistics(calibration_results)
            
            # 更新比较结果
            self.update_comparison_results(calibration_results)
            
        except Exception as e:
            print(f"❌ 更新双校准器比较失败: {e}")
            import traceback
            traceback.print_exc()
    
    def update_heatmaps(self, results):
        """更新热力图"""
        try:
            print(f"🔄 更新双校准器比较数据 #{self._update_count}")
            
            # 🆕 修改：检查是否有必要的数据
            if 'raw' not in results:
                print("⚠️ 没有原始数据，跳过热力图更新")
                return
            
            # 🎯 第一步：更新原始数据热力图
            if 'raw' in results and hasattr(self, 'raw_canvas'):
                raw_data = results['raw']['data']
                self.update_single_heatmap(self.raw_canvas, raw_data)
                print(f"✅ 原始数据热力图更新完成，数据范围: [{raw_data.min():.2f}, {raw_data.max():.2f}]")
            
            # 🎯 第二步：更新新版本校准热力图
            if 'new' in results and hasattr(self, 'new_canvas'):
                new_data = results['new']['data']
                self.update_single_heatmap(self.new_canvas, new_data)
                print(f"✅ 新版本校准热力图更新完成，数据范围: [{new_data.min():.2f}, {new_data.max():.2f}]")
                
                # 🆕 新增：更新变化量数据热力图（移到区域检测之前）
                change_data = None
                if hasattr(self, 'change_data_canvas') and self.baseline_calibrated_data is not None:
                    try:
                        # 🔧 修改：基于未去皮校准数据的差值计算变化量
                        # 确保使用未去皮的校准数据进行变化量计算
                        
                        # 获取当前未去皮的校准数据
                        current_raw = self.parent.calibration_handler._get_current_frame_data()
                        current_calibration_results = self.parent.calibration_manager.apply_dual_calibration(current_raw)
                        
                        if 'new' in current_calibration_results and 'data' in current_calibration_results['new']:
                            current_calibrated_data = current_calibration_results['new']['data']
                            
                            # 计算变化量：当前未去皮校准数据 - 基准未去皮校准数据
                            change_data = current_calibrated_data - self.baseline_calibrated_data
                            
                            print(f"   🔧 基于未去皮校准数据计算变化量:")
                            print(f"     基准校准数据范围: [{self.baseline_calibrated_data.min():.2f}, {self.baseline_calibrated_data.max():.2f}]")
                            print(f"     当前校准数据范围: [{current_calibrated_data.min():.2f}, {current_calibrated_data.max():.2f}]")
                            print(f"     变化量范围: [{change_data.min():.2f}, {change_data.max():.2f}]")
                            
                        else:
                            print(f"   ⚠️ 无法获取当前校准数据，跳过变化量计算")
                            
                    except Exception as e:
                        print(f"⚠️ 计算变化量失败: {e}")
                        import traceback
                        traceback.print_exc()
                
                # 🆕 新增：识别校准区域（基于变化量数据）
                try:
                    print(f"🔍 开始识别校准区域...")
                    threshold_percentile = self.threshold_slider.value()
                    
                    # 🔧 修复：优先使用变化量数据进行区域检测
                    if change_data is not None:
                        print(f"   🎯 使用变化量数据进行区域检测")
                        data_for_detection = change_data
                        detection_method = "变化量数据"
                    else:
                        print(f"   ⚠️ 变化量数据不可用，使用校准数据进行区域检测")
                        data_for_detection = new_data
                        detection_method = "校准数据"
                    
                    calibrated_regions = self.identify_calibrated_regions(data_for_detection, threshold_percentile)
                    
                    if calibrated_regions:
                        print(f"✅ 识别到 {len(calibrated_regions)} 个校准区域（基于{detection_method}）")
                        # 更新区域数量显示
                        if hasattr(self, 'region_count_label'):
                            self.region_count_label.setText(f"主区域: {len(calibrated_regions)}")
                            self.region_count_label.setStyleSheet("color: #27ae60; font-weight: bold; min-width: 60px;")
                        
                        # 将区域信息添加到results中，供其他方法使用
                        if 'calibrated_regions' not in results:
                            results['calibrated_regions'] = {}
                        results['calibrated_regions']['regions'] = calibrated_regions
                        
                        # 在校准热力图上绘制区域
                        new_fig = self.new_canvas.figure
                        new_ax = new_fig.axes[0]
                        self.draw_calibrated_regions_on_heatmap(new_ax, calibrated_regions, color='red', linewidth=3)
                        new_fig.canvas.draw()
                        
                        # 🆕 新增：更新区域统计标签
                        self._update_region_stats_labels(calibrated_regions, results)
                        
                        print(f"✅ 校准区域绘制完成")
                    else:
                        print(f"⚠️ 未识别到校准区域")
                        # 更新区域数量显示
                        if hasattr(self, 'region_count_label'):
                            self.region_count_label.setText("主区域: 0")
                            self.region_count_label.setStyleSheet("color: #e74c3c; font-weight: bold; min-width: 60px;")
                        
                        # 清空区域信息
                        if 'calibrated_regions' in results:
                            results['calibrated_regions']['regions'] = []
                        
                except Exception as e:
                    print(f"⚠️ 区域识别失败: {e}")
                    import traceback
                    traceback.print_exc()
                
                # 🆕 新增：更新变化量数据热力图（如果之前没有计算）
                if change_data is not None:
                    try:
                        # 更新变化量热力图
                        self.update_single_heatmap(self.change_data_canvas, change_data)
                        
                        # 将变化量数据添加到results中，供统计管理器使用
                        if 'change_data' not in results:
                            results['change_data'] = {}
                        results['change_data']['data'] = change_data
                        
                        print(f"✅ 变化量数据热力图更新完成:")
                        print(f"   变化量范围: [{change_data.min():.2f}, {change_data.max():.2f}]")
                        print(f"   变化量均值: {change_data.mean():.2f}")
                        print(f"   变化量标准差: {change_data.std():.2f}")
                        
                    except Exception as e:
                        print(f"⚠️ 更新变化量数据热力图失败: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("⚠️ 未设置基准数据或变化量画布不存在，跳过变化量热力图更新")
            
            # 🎯 第三步：使用统一方法将校准区域应用到所有热力图
            calibrated_regions = results.get('calibrated_regions', {}).get('regions', [])
            if calibrated_regions:
                self._apply_regions_to_all_heatmaps(calibrated_regions, results)
            else:
                # 没有选中区域：更新区域数量显示
                if hasattr(self, 'region_count_label'):
                    self.region_count_label.setText("主区域: 0")
                    self.region_count_label.setStyleSheet("color: #e74c3c; font-weight: bold; min-width: 60px;")
                
        except Exception as e:
            print(f"❌ 更新热力图失败: {e}")
            import traceback
            traceback.print_exc()
    
    def update_statistics(self, results):
        """更新统计信息"""
        print(f"🔧 开始更新统计信息...")
        
        # 使用StatisticsManager更新所有统计信息
        self.statistics_manager.update_raw_statistics(results)
        print(f"   ✅ 原始数据统计更新完成")
        
        self.statistics_manager.update_new_statistics(results)
        print(f"   ✅ 新版本校准统计更新完成")
        
        self.statistics_manager.update_change_data_statistics(results)  # 🆕 新增：更新变化量统计
        print(f"   ✅ 变化量统计更新完成")
        
        self.statistics_manager.update_region_calibration_statistics(results)  # 🆕 新增：更新区域校准值统计
        print(f"   ✅ 区域校准值统计更新完成")
        
        # 🆕 新增：更新压强热力图统计
        self.statistics_manager.update_pressure_heatmap_statistics(results)
        print(f"   ✅ 压强热力图统计更新完成")
        
        print(f"🎉 所有统计信息更新完成")
    
    def update_comparison_results(self, results):
        """更新比较结果"""
        self.comparison_manager.update_comparison_results(results)
    
    def save_screenshot(self):
        """保存截图"""
        try:
            filename = f"双校准器比较_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.grab().save(filename)
            print(f"✅ 截图已保存: {filename}")
            QtWidgets.QMessageBox.information(self, "保存成功", f"截图已保存为: {filename}")
        except Exception as e:
            print(f"❌ 保存截图失败: {e}")
            QtWidgets.QMessageBox.critical(self, "保存失败", f"保存截图失败:\n{str(e)}")
    
    def perform_taring(self):
        """执行去皮操作"""
        return self.taring_manager.perform_taring()
    
    def reset_taring(self):
        """重置去皮操作"""
        return self.taring_manager.reset_taring()
    
    def on_threshold_changed(self, value):
        """阈值滑块值改变事件"""
        self.threshold_label.setText(f"{value}%")
        print(f"🔧 区域识别阈值已调整为: {value}%")
    
    def on_region_count_changed(self, value):
        """区域数量配置滑块值改变事件"""
        self.region_count_config_label.setText(f"{value}")
        print(f"🔧 检测区域数量已调整为: {value}个")
        
        # 如果当前正在运行比较，立即重新识别区域
        if hasattr(self, '_comparison_running') and self._comparison_running:
            print(f"🔄 检测到区域数量配置变化，正在重新识别区域...")
            self.manual_identify_regions()
    
    def manual_identify_regions(self):
        """手动重新识别校准区域"""
        try:
            if hasattr(self, 'new_canvas'):
                print("🔍 手动重新识别校准区域...")
                
                # 获取当前阈值
                threshold_percentile = self.threshold_slider.value()
                
                # 获取最新的校准数据
                raw_data = self.parent.calibration_handler._get_current_frame_data()
                calibration_results = self.parent.calibration_manager.apply_new_calibration(raw_data)
                
                if 'new' in calibration_results:
                    new_data = calibration_results['new']['data']
                    
                    # 🔧 修复：优先使用变化量数据进行区域检测
                    data_for_detection = None
                    detection_method = ""
                    
                    if self.baseline_calibrated_data is not None:
                        try:
                            # 计算变化量
                            change_data = new_data - self.baseline_calibrated_data
                            data_for_detection = change_data
                            detection_method = "变化量数据"
                            print(f"🔧 手动识别：使用变化量数据进行区域检测")
                            print(f"   变化量范围: [{change_data.min():.2f}, {change_data.max():.2f}]")
                        except Exception as e:
                            print(f"⚠️ 计算变化量失败，使用校准数据: {e}")
                            data_for_detection = new_data
                            detection_method = "校准数据"
                    else:
                        print(f"⚠️ 未设置基准数据，使用校准数据进行区域检测")
                        data_for_detection = new_data
                        detection_method = "校准数据"
                    
                    # 重新识别区域
                    calibrated_regions = self.identify_calibrated_regions(data_for_detection, threshold_percentile)
                    
                    # 更新校准热力图上的区域标记
                    if calibrated_regions:
                        new_fig = self.new_canvas.figure
                        new_ax = new_fig.axes[0]
                        self.draw_calibrated_regions_on_heatmap(new_ax, calibrated_regions, color='red', linewidth=3)
                        new_fig.canvas.draw()
                        
                        # 显示识别结果
                        QtWidgets.QMessageBox.information(
                            self, 
                            "区域识别完成", 
                            f"成功识别出校准区域！\n"
                            f"检测方法: {detection_method}\n"
                            f"识别策略: 基于压力强度排序（优先识别按压强度最高的区域）\n"
                            f"用户配置区域数量: {self.region_count_slider.value()}个\n"
                            f"实际检测到区域: {len(calibrated_regions)}个\n"
                            f"阈值: {threshold_percentile}%\n"
                            f"区域已用不同颜色标记。\n\n"
                            f"💡 提示：系统现在会优先识别压力值最高的区域，"
                            f"而不是面积最大的区域，这样能更准确地找到实际的按压位置。"
                        )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self, 
                            "识别失败", 
                            f"未识别出有效的校准区域。\n"
                            f"检测方法: {detection_method}\n"
                            f"当前阈值: {threshold_percentile}%\n"
                            f"请尝试降低阈值或检查数据。"
                        )
                else:
                    QtWidgets.QMessageBox.warning(self, "提示", "无法获取校准数据。")
            else:
                QtWidgets.QMessageBox.warning(self, "提示", "请先启动监控功能获取校准数据。")
                
        except Exception as e:
            print(f"❌ 手动识别校准区域失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"手动识别失败:\n{str(e)}")
            
    def draw_calibrated_regions_on_heatmap(self, ax, regions, color='red', linewidth=3):
        """在校准热力图上绘制识别出的区域（使用轮廓跟踪）"""
        self.region_renderer.draw_calibrated_regions_on_heatmap(ax, regions, color, linewidth)
    
    def identify_calibrated_regions(self, calibrated_data, threshold_percentile=80):
        """在校准后的数据上识别高响应区域，基于压力强度进行区域选取（而非面积）"""
        # 🔧 修复：不要每次都重新设置基准数据，基准数据应该在set_baseline_for_region_selection中设置一次
        # 这里只需要确保RegionDetector有正确的基准数据即可
        
        # 🆕 修复：调整阈值百分位数，使其更容易检测到多个区域
        # 如果用户设置的阈值太高，可能导致检测不到足够的区域
        adjusted_threshold = min(threshold_percentile, 70)  # 最高不超过70%
        if adjusted_threshold != threshold_percentile:
            print(f"🔧 调整区域检测阈值: {threshold_percentile}% → {adjusted_threshold}% (确保能检测到多个区域)")
        
        # 🎯 关键改进：现在使用基于压力强度的区域识别
        # 系统会优先识别压力值最高的区域，而不是面积最大的区域
        max_regions = self.region_count_slider.value()
        return self.region_detector.identify_calibrated_regions(
            calibrated_data, 
            adjusted_threshold, 
            max_regions
        )
    
    def _create_contour_from_mask(self, contour_mask):
        """从轮廓掩码创建轮廓"""
        # 使用RegionRenderer中的方法
        return self.region_renderer._create_contour_from_mask(contour_mask)

    def _create_combined_region_mask(self, regions, data_shape):
        """创建所有选中区域的组合掩码"""
        # 使用RegionApplicationManager中的方法
        return self.region_application_manager._create_combined_region_mask(regions, data_shape)
    
    def _update_region_stats_labels(self, regions, results):
        """更新区域统计标签"""
        try:
            if not regions:
                # 没有区域时，显示等待状态
                if hasattr(self, 'region1_stats_label'):
                    self.region1_stats_label.setText("等待区域1数据...")
                if hasattr(self, 'region2_stats_label'):
                    self.region2_stats_label.setText("等待区域2数据...")
                return
            
            # 更新区域1统计
            if len(regions) >= 1 and hasattr(self, 'region1_stats_label'):
                region1 = regions[0]
                region1_stats = self._calculate_region_stats(region1, results)
                self.region1_stats_label.setText(
                    f"区域1: 面积{region1_stats['area']}, "
                    f"中心({region1_stats['center_x']},{region1_stats['center_y']})\n"
                    f"平均压力: {region1_stats['avg_pressure']:.1f}N\n"
                    f"最大压力: {region1_stats['max_pressure']:.1f}N\n"
                    f"压力密度: {region1_stats['pressure_density']:.2f}N/像素\n"
                    f"压力评分: {region1_stats['pressure_score']:.2f}\n"
                    f"紧凑度: {region1_stats['compactness']:.3f}"
                )
                self.region1_stats_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #27ae60;")
            
            # 更新区域2统计
            if len(regions) >= 2 and hasattr(self, 'region2_stats_label'):
                region2 = regions[1]
                region2_stats = self._calculate_region_stats(region2, results)
                self.region2_stats_label.setText(
                    f"区域2: 面积{region2_stats['area']}, "
                    f"中心({region2_stats['center_x']},{region2_stats['center_y']})\n"
                    f"平均压力: {region2_stats['avg_pressure']:.1f}N\n"
                    f"最大压力: {region2_stats['max_pressure']:.1f}N\n"
                    f"压力密度: {region2_stats['pressure_density']:.2f}N/像素\n"
                    f"压力评分: {region2_stats['pressure_score']:.2f}\n"
                    f"紧凑度: {region2_stats['compactness']:.3f}"
                )
                self.region2_stats_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #9b59b6;")
            elif hasattr(self, 'region2_stats_label'):
                # 只有一个区域时，区域2显示等待状态
                self.region2_stats_label.setText("等待区域2数据...")
                self.region2_stats_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #9b59b6;")
            
            print(f"✅ 区域统计标签更新完成，共 {len(regions)} 个区域")
            
        except Exception as e:
            print(f"⚠️ 更新区域统计标签失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_region_stats(self, region, results):
        """计算单个区域的统计信息"""
        try:
            # 基础信息
            area = region.get('area', 0)
            center = region.get('center', (0, 0))
            center_x, center_y = center
            compactness = region.get('compactness', 0.0)
            
            # 🆕 新增：压力强度信息（优先使用新字段）
            avg_pressure = region.get('avg_pressure', 0.0)
            max_pressure = region.get('max_pressure', 0.0)
            pressure_density = region.get('pressure_density', 0.0)
            pressure_score = region.get('pressure_score', 0.0)
            
            # 如果没有新的压力强度信息，尝试从压力数据计算
            if avg_pressure == 0.0 and 'new' in results and 'pressure_data' in results['new']:
                pressure_data = results['new']['pressure_data']
                
                # 使用区域掩码计算压力统计
                if 'contour_mask' in region:
                    contour_mask = region['contour_mask']
                    region_pressures = pressure_data[contour_mask == 1]
                    
                    if len(region_pressures) > 0:
                        avg_pressure = float(region_pressures.mean())
                        max_pressure = float(region_pressures.max())
                        pressure_density = float(np.sum(region_pressures) / area) if area > 0 else 0.0
                    else:
                        # 如果没有掩码数据，使用边界框估算
                        bbox = region.get('bbox', (0, 0, 1, 1))
                        x1, y1, x2, y2 = bbox
                        region_pressures = pressure_data[y1:y2, x1:x2]
                        avg_pressure = float(region_pressures.mean())
                        max_pressure = float(region_pressures.max())
                        pressure_density = float(np.sum(region_pressures) / area) if area > 0 else 0.0
            
            # 计算压力评分（如果没有的话）
            if pressure_score == 0.0 and avg_pressure > 0:
                pressure_score = (avg_pressure * 0.4 + max_pressure * 0.4 + pressure_density * 0.2)
            
            return {
                'area': area,
                'center_x': center_x,
                'center_y': center_y,
                'compactness': compactness,
                'avg_pressure': avg_pressure,
                'max_pressure': max_pressure,
                'pressure_density': pressure_density,
                'pressure_score': pressure_score
            }
            
        except Exception as e:
            print(f"⚠️ 计算区域统计失败: {e}")
            return {
                'area': 0,
                'center_x': 0,
                'center_y': 0,
                'compactness': 0.0,
                'avg_pressure': 0.0,
                'max_pressure': 0.0,
                'pressure_density': 0.0,
                'pressure_score': 0.0
            }

    def _apply_regions_to_all_heatmaps(self, calibrated_regions, results):
        """🎯 统一管理：将校准区域应用到所有相关热力图上"""
        # 设置画布引用
        self.region_application_manager.set_canvases(
            getattr(self, 'new_canvas', None),
            getattr(self, 'change_data_canvas', None),  # 🆕 新增：变化量画布
            getattr(self, 'region_calibration_canvas', None), # 🆕 新增：区域校准值画布
            getattr(self, 'region_count_label', None),
            getattr(self, 'pressure_heatmap_canvas', None)  # 🆕 新增：压强热力图画布
        )
        
        # 使用RegionApplicationManager应用区域
        self.region_application_manager.apply_regions_to_all_heatmaps(calibrated_regions, results)

    def _print_calibration_to_pressure_relationship(self, region, region_mask):
        """打印响应值到压力值的关系式"""
        try:
            print(f"\n🔬 区域 {region['id']} 的响应值到压力值关系分析:")
            
            # 获取该区域的校准值（使用去皮前的数据，用于关系式验证）
            if hasattr(self, '_last_calibrated_data') and self._last_calibrated_data is not None:
                # 使用去皮前的校准数据进行关系式验证
                if hasattr(self, '_last_calibrated_untared_data') and self._last_calibrated_untared_data is not None:
                    # 优先使用去皮前的校准数据
                    region_calibrated_values = self._last_calibrated_untared_data[region_mask]
                    print(f"   📊 校准值统计 (去皮前，用于关系式验证):")
                else:
                    # 备用：使用去皮后的校准数据
                    region_calibrated_values = self._last_calibrated_data[region_mask]
                    print(f"   📊 校准值统计 (去皮后，注意：此值不适合关系式验证):")
                
                avg_calibrated = region_calibrated_values.mean()
                min_calibrated = region_calibrated_values.min()
                max_calibrated = region_calibrated_values.max()
                
                print(f"      平均值: {avg_calibrated:.2f}")
                print(f"      最小值: {min_calibrated:.2f}")
                print(f"      最大值: {max_calibrated:.2f}")
                print(f"      标准差: {region_calibrated_values.std():.2f}")
            else:
                print(f"   ⚠️ 无法获取校准值数据")
                return
            
            # 获取该区域的压力值
            if hasattr(self, '_last_pressure_with_offset_data') and self._last_pressure_with_offset_data is not None:
                region_pressure_values = self._last_pressure_with_offset_data[region_mask]
                avg_pressure = region_pressure_values.mean()
                min_pressure = region_pressure_values.min()
                max_pressure = region_pressure_values.max()
                
                print(f"   📊 压力值统计:")
                print(f"      平均值: {avg_pressure:.2f}N")
                print(f"      最小值: {min_pressure:.2f}N")
                print(f"      最大值: {max_pressure:.2f}N")
                print(f"      标准差: {region_pressure_values.std():.2f}N")
            else:
                print(f"   ⚠️ 无法获取压力值数据")
                return
            
            # 计算转换关系
            if hasattr(self, 'parent') and hasattr(self.parent, 'calibration_manager'):
                new_calibrator = self.parent.calibration_manager.new_calibrator
                if hasattr(new_calibrator, 'conversion_poly_coeffs'):
                    a, b, c = new_calibrator.conversion_poly_coeffs
                    print(f"   🔧 压力转换关系式:")
                    print(f"      P(N) = {a:.6f} × V² + {b:.6f} × V + {c:.6f}")
                    print(f"      其中 V 是校准值，P 是压力值(N)")
                    
                    # 验证关系式
                    expected_pressure = a * avg_calibrated**2 + b * avg_calibrated + c
                    actual_pressure = avg_pressure
                    error = abs(expected_pressure - actual_pressure)
                    
                    print(f"   ✅ 关系式验证:")
                    print(f"      校准值 V = {avg_calibrated:.2f}")
                    print(f"      计算压力 P = {expected_pressure:.2f}N")
                    print(f"      实际压力 P = {actual_pressure:.2f}N")
                    print(f"      误差: {error:.2f}N ({error/actual_pressure*100:.1f}%)")
                    
                    if error < 1.0:
                        print(f"      🎯 关系式验证通过！误差小于1N")
                    else:
                        print(f"      ⚠️ 关系式验证失败，误差较大")
                else:
                    print(f"   ⚠️ 无法获取压力转换系数")
            else:
                print(f"   ⚠️ 无法访问校准管理器")
                
        except Exception as e:
            print(f"   ❌ 关系式分析失败: {e}")
            import traceback
            traceback.print_exc()

    def analyze_regions_pressure(self, pressure_data, calibrated_regions):
        """分析识别出的区域的压力值（支持轮廓跟踪数据）"""
        try:
            print(f"�� 开始分析识别区域的压力值...")

            region_pressures = []
            for region in calibrated_regions:
                # 支持轮廓跟踪和传统mask两种方法
                if 'contour_mask' in region:
                    region_mask = region['contour_mask']
                    region_pressure_values = pressure_data[region_mask == 1]
                else:
                    region_mask = region['mask']
                    region_pressure_values = pressure_data[region_mask]

                region_pressure_info = {
                    'id': region['id'],
                    'center': region['center'],
                    'avg_pressure': float(region_pressure_values.mean()),
                    'min_pressure': float(region_pressure_values.min()),
                    'max_pressure': float(region_pressure_values.max()),
                    'std_pressure': float(region_pressure_values.std()),
                    'area': region['area']
                }
                region_pressures.append(region_pressure_info)

                print(f"   区域 {region['id']}: 平均压力 {region_pressure_info['avg_pressure']:.2f}N, "
                      f"范围 [{region_pressure_info['min_pressure']:.2f}N, {region_pressure_info['max_pressure']:.2f}N]")

            # 计算整体统计
            if region_pressures:
                all_pressures = [r['avg_pressure'] for r in region_pressures]
                overall_stats = {
                    'total_regions': len(region_pressures),
                    'avg_pressure': float(np.mean(all_pressures)),
                    'min_pressure': float(np.min(all_pressures)),
                    'max_pressure': float(np.max(all_pressures)),
                    'std_pressure': float(np.std(all_pressures)),
                    'region_details': region_pressures
                }

                print(f"✅ 区域压力分析完成，{len(region_pressures)} 个区域")
                print(f"   整体平均压力: {overall_stats['avg_pressure']:.2f}N")
                print(f"   压力范围: [{overall_stats['min_pressure']:.2f}N, {overall_stats['max_pressure']:.2f}N]")

                return overall_stats
            else:
                print("⚠️ 没有区域可分析")
                return None

        except Exception as e:
            print(f"❌ 区域压力分析失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_user_preferences(self):
        """保存用户配置偏好"""
        self.configuration_manager.save_user_preferences(
            self.threshold_slider.value(),
            self.region_count_slider.value(),
            self.max_region_count
        )
    
    def load_user_preferences(self):
        """加载用户配置偏好"""
        config = self.configuration_manager.load_user_preferences()
        
        # 应用配置
        if 'threshold_percentile' in config:
            threshold = max(50, min(95, config['threshold_percentile']))
            self.threshold_slider.setValue(threshold)
            self.threshold_label.setText(f"{threshold}%")
        
        if 'region_count' in config:
            region_count = max(1, min(self.max_region_count, config['region_count']))
            self.region_count_slider.setValue(region_count)
            self.region_count_config_label.setText(f"{region_count}")
    
    def closeEvent(self, event):
        """窗口关闭事件 - 保存用户配置"""
        try:
            self.save_user_preferences()
            print("💾 已保存用户配置偏好")
        except Exception as e:
            print(f"⚠️ 保存用户配置偏好失败: {e}")
        
        super().closeEvent(event)