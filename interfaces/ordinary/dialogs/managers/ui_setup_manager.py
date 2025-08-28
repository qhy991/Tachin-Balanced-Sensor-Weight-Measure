#!/usr/bin/env python3
"""
UI设置管理器

负责创建和管理双校准比较对话框的用户界面组件
"""

import sys
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                             QPushButton, QSlider, QSpinBox, QGroupBox,
                             QScrollArea, QWidget, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt


class UISetupManager:
    """UI设置管理器"""

    def __init__(self, dialog):
        self.dialog = dialog
        self.labels = {}  # 存储所有创建的标签引用

    def setup_main_ui(self):
        """设置主用户界面"""
        try:
            print("🔧 开始设置双校准器比较对话框UI...")

            # 检查校准器状态
            self._check_calibration_status()

            # 设置窗口基本属性
            self.dialog.setWindowTitle("新版本校准器实时监控")
            self.dialog.setGeometry(100, 100, 1400, 800)

            # 创建主布局
            layout = QtWidgets.QVBoxLayout()

            # 添加标题
            title_label = self._create_title_label()
            layout.addWidget(title_label)

            # 创建控制面板
            control_layout = self._create_control_panel()
            layout.addLayout(control_layout)

            # 创建热力图显示区域
            heatmap_layout = self._create_heatmap_layout()
            layout.addLayout(heatmap_layout)

            # 创建统计信息显示区域
            stats_layout = self._create_statistics_layout()
            layout.addLayout(stats_layout)

            # 创建比较结果显示
            comparison_group = self._create_comparison_group()
            layout.addWidget(comparison_group)

            # 设置布局
            self.dialog.setLayout(layout)

            # 加载用户配置
            self._load_user_preferences()

            print("✅ 双校准器比较对话框UI设置完成")

        except Exception as e:
            print(f"❌ 设置双校准器比较对话框UI失败: {e}")
            import traceback
            traceback.print_exc()

    def _check_calibration_status(self):
        """检查校准器状态"""
        try:
            if hasattr(self.dialog.parent, 'calibration_manager'):
                print("✅ 找到calibration_manager")
                if hasattr(self.dialog.parent.calibration_manager, 'dual_calibration_mode'):
                    mode = '新版本校准' if self.dialog.parent.calibration_manager.dual_calibration_mode else '单校准器'
                    print(f"   校准模式: {mode}")
                else:
                    print("   校准模式: 未知")
                if hasattr(self.dialog.parent.calibration_manager, 'new_calibrator'):
                    print(f"   新版本校准器: {self.dialog.parent.calibration_manager.new_calibrator is not None}")
                else:
                    print("   新版本校准器: 未找到")
            else:
                print("⚠️ 未找到calibration_manager，将创建基本UI")
        except Exception as e:
            print(f"⚠️ 检查校准器状态时出错: {e}，继续创建UI")

    def _create_title_label(self):
        """创建标题标签"""
        title_label = QtWidgets.QLabel("新版本校准器实时监控")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        return title_label

    def _create_control_panel(self):
        """创建控制面板"""
        control_layout = QtWidgets.QHBoxLayout()

        # 开始/停止按钮
        self.dialog.button_start_stop = self._create_button(
            "开始比较", self.dialog.toggle_comparison,
            "background-color: #27ae60; color: white; font-weight: bold; padding: 8px;"
        )
        control_layout.addWidget(self.dialog.button_start_stop)

        # 去皮功能按钮
        self.dialog.button_taring = self._create_button(
            "执行去皮", self.dialog.perform_taring,
            "background-color: #f39c12; color: white; font-weight: bold; padding: 8px;"
        )
        control_layout.addWidget(self.dialog.button_taring)

        self.dialog.button_reset_taring = self._create_button(
            "重置去皮", self.dialog.reset_taring,
            "background-color: #e67e22; color: white; font-weight: bold; padding: 8px;"
        )
        control_layout.addWidget(self.dialog.button_reset_taring)

        # 区域识别阈值控制
        control_layout.addWidget(QtWidgets.QLabel("区域识别阈值:"))
        self.dialog.threshold_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.dialog.threshold_slider.setRange(50, 95)
        self.dialog.threshold_slider.setValue(80)
        self.dialog.threshold_slider.setToolTip("调整压力区域识别的阈值百分位数")
        self.dialog.threshold_slider.valueChanged.connect(self.dialog.on_threshold_changed)
        control_layout.addWidget(self.dialog.threshold_slider)

        self.dialog.threshold_label = QtWidgets.QLabel("80%")
        self.dialog.threshold_label.setStyleSheet("color: #2c3e50; font-weight: bold; min-width: 40px;")
        control_layout.addWidget(self.dialog.threshold_label)

        # 区域数量配置控制
        control_layout.addWidget(QtWidgets.QLabel("检测区域数量:"))
        self.dialog.region_count_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.dialog.region_count_slider.setRange(1, self.dialog.max_region_count)
        self.dialog.region_count_slider.setValue(self.dialog.default_region_count)
        self.dialog.region_count_slider.setToolTip(f"选择要检测的压力区域数量 (1-{self.dialog.max_region_count})")
        self.dialog.region_count_slider.valueChanged.connect(self.dialog.on_region_count_changed)
        control_layout.addWidget(self.dialog.region_count_slider)

        self.dialog.region_count_config_label = QtWidgets.QLabel(f"{self.dialog.default_region_count}")
        self.dialog.region_count_config_label.setStyleSheet("color: #e74c3c; font-weight: bold; min-width: 30px;")
        control_layout.addWidget(self.dialog.region_count_config_label)

        # 区域数量显示标签
        self.dialog.region_count_label = QtWidgets.QLabel("区域: 0")
        self.dialog.region_count_label.setStyleSheet("color: #e74c3c; font-weight: bold; min-width: 60px;")
        control_layout.addWidget(self.dialog.region_count_label)

        # 其他控制按钮
        buttons_config = [
            ("重新识别区域", self.dialog.manual_identify_regions, "#9b59b6"),
            ("保存截图", self.dialog.save_screenshot, "#3498db"),
            ("设置区域选取基准", self.dialog.set_baseline_for_region_selection, "#8e44ad"),
            ("重置区域选取基准", self.dialog.reset_baseline_for_region_selection, "#95a5a6"),
            ("关闭", self.dialog.close, "#e74c3c")
        ]

        for text, callback, color in buttons_config:
            button = self._create_button(text, callback, f"background-color: {color}; color: white; font-weight: bold; padding: 8px;")
            control_layout.addWidget(button)

        control_layout.addStretch()
        return control_layout

    def _create_heatmap_layout(self):
        """创建热力图显示区域"""
        heatmap_layout = QtWidgets.QHBoxLayout()

        # 原始数据热力图
        raw_group = self._create_heatmap_group("原始数据", "raw_canvas")
        heatmap_layout.addWidget(raw_group)

        # 新版本校准结果热力图
        new_group = self._create_heatmap_group("新版本校准", "new_canvas")
        heatmap_layout.addWidget(new_group)

        # 变化量数据热力图
        change_data_group = self._create_heatmap_group("去除基准后的变化量", "change_data_canvas")
        heatmap_layout.addWidget(change_data_group)

        # 区域校准值热力图
        region_calibration_group = self._create_heatmap_group("选中区域的新版本校准数据", "region_calibration_canvas")
        heatmap_layout.addWidget(region_calibration_group)

        # 压强热力图
        pressure_heatmap_group = self._create_heatmap_group("检测区域压强热力图", "pressure_heatmap_canvas")
        heatmap_layout.addWidget(pressure_heatmap_group)

        # 负值响应检测热力图
        negative_response_group = self._create_heatmap_group("负值响应检测", "negative_response_canvas")
        heatmap_layout.addWidget(negative_response_group)

        return heatmap_layout

    def _create_statistics_layout(self):
        """创建统计信息显示区域"""
        stats_layout = QtWidgets.QHBoxLayout()

        # 原始数据统计
        raw_stats_group = self._create_stats_group("原始数据统计", [
            'raw_mean_label', 'raw_std_label', 'raw_min_label', 'raw_max_label', 'raw_range_label'
        ], "#3498db")
        stats_layout.addWidget(raw_stats_group)

        # 新版本校准统计
        new_stats_group = self._create_stats_group("新版本校准统计", [
            'new_mean_label', 'new_std_label', 'new_min_label', 'new_max_label', 'new_range_label'
        ], "#e74c3c")
        stats_layout.addWidget(new_stats_group)

        # 变化量数据统计
        change_data_stats_group = self._create_stats_group("变化量数据统计", [
            'change_data_mean_label', 'change_data_std_label', 'change_data_min_label',
            'change_data_max_label', 'change_data_range_label'
        ], "#f39c12")
        stats_layout.addWidget(change_data_stats_group)

        # 区域校准值统计
        region_calibration_stats_group = self._create_stats_group("选中区域的新版本校准统计", [
            'region_calibration_mean_label', 'region_calibration_std_label', 'region_calibration_min_label',
            'region_calibration_max_label', 'region_calibration_range_label', 'region_calibration_sum_label'
        ], "#e67e22")
        stats_layout.addWidget(region_calibration_stats_group)

        # 压强热力图统计
        pressure_heatmap_stats_group = self._create_stats_group("检测区域压强统计", [
            'pressure_heatmap_mean_label', 'pressure_heatmap_max_label', 'pressure_heatmap_min_label',
            'pressure_heatmap_total_force_label', 'pressure_heatmap_regions_label'
        ], "#9b59b6")
        stats_layout.addWidget(pressure_heatmap_stats_group)

        # 区域1统计
        region1_stats_group = self._create_simple_stats_group("区域1统计", 'region1_stats_label', "#e67e22")
        stats_layout.addWidget(region1_stats_group)

        # 区域2统计
        region2_stats_group = self._create_simple_stats_group("区域2统计", 'region2_stats_label', "#9b59b6")
        stats_layout.addWidget(region2_stats_group)

        # 负值响应统计
        negative_response_stats_group = self._create_simple_stats_group("负值响应统计", 'negative_response_stats_label', "#e74c3c")
        stats_layout.addWidget(negative_response_stats_group)

        return stats_layout

    def _create_comparison_group(self):
        """创建比较结果显示"""
        comparison_group = QtWidgets.QGroupBox("比较结果")
        comparison_layout = QtWidgets.QVBoxLayout()
        self.dialog.comparison_label = QtWidgets.QLabel("等待比较数据...")
        self.dialog.comparison_label.setStyleSheet("font-family: monospace; font-size: 12px; color: #e74c3c;")
        comparison_layout.addWidget(self.dialog.comparison_label)
        comparison_group.setLayout(comparison_layout)
        return comparison_group

    def _create_button(self, text, callback, style):
        """创建按钮"""
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(style)
        return button

    def _create_heatmap_group(self, title, canvas_attr):
        """创建热力图组"""
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout()
        canvas = self.dialog.create_heatmap_canvas(title)
        setattr(self.dialog, canvas_attr, canvas)
        layout.addWidget(canvas)
        group.setLayout(layout)
        return group

    def _create_stats_group(self, title, label_attrs, color):
        """创建统计组"""
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout()

        for attr in label_attrs:
            label = QtWidgets.QLabel("等待数据...")
            label.setStyleSheet(f"font-family: monospace; font-size: 11px; color: {color};")
            setattr(self.dialog, attr, label)
            layout.addWidget(label)
            self.labels[attr] = label

        group.setLayout(layout)
        return group

    def _create_simple_stats_group(self, title, label_attr, color):
        """创建简单统计组（单个标签）"""
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("等待数据...")
        label.setStyleSheet(f"font-family: monospace; font-size: 11px; color: {color};")
        setattr(self.dialog, label_attr, label)
        layout.addWidget(label)
        self.labels[label_attr] = label
        group.setLayout(layout)
        return group

    def _load_user_preferences(self):
        """加载用户配置偏好"""
        try:
            self.dialog.load_user_preferences()
            print("💾 用户配置偏好已加载")
        except Exception as e:
            print(f"⚠️ 加载用户配置偏好失败: {e}")

    def get_labels(self):
        """获取所有标签引用"""
        return self.labels
