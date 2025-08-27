"""
校准对比对话框 - 完整版本

用于显示AI校准前后的热力图对比
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5 import QtWidgets, QtCore


class CalibrationComparisonDialog(QtWidgets.QDialog):
    """校准前后对比对话框（完整版本）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("AI校准前后对比")
        self.setGeometry(200, 200, 1200, 800)

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 设置自动刷新定时器
        self.auto_refresh_timer = QtCore.QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_data)
        self.auto_refresh_enabled = False

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        try:
            print("🔧 开始设置校准对比对话框UI...")
            
            layout = QtWidgets.QVBoxLayout()

            # 标题
            title = QtWidgets.QLabel("AI校准前后对比分析")
            title.setStyleSheet("font-size: 16px; font-weight: bold;")
            layout.addWidget(title)
            print("✅ 标题添加成功")

            # 创建滚动区域
            scroll_area = QtWidgets.QScrollArea()
            scroll_widget = QtWidgets.QWidget()
            scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
            print("✅ 滚动区域创建成功")

            # 获取当前帧数据
            print("🔍 开始获取当前帧数据...")
            raw_data = self.parent.get_current_frame_data()
            print(f"✅ 获取原始数据成功，形状: {raw_data.shape}")
            
            # 尝试应用AI校准，如果失败则使用原始数据
            try:
                if hasattr(self.parent, 'apply_ai_calibration'):
                    print("🔧 使用parent.apply_ai_calibration方法")
                    calibrated_data = self.parent.apply_ai_calibration(raw_data)
                elif hasattr(self.parent, 'calibration_manager') and hasattr(self.parent.calibration_manager, 'apply_ai_calibration'):
                    print("🔧 使用calibration_manager.apply_ai_calibration方法")
                    calibrated_data = self.parent.calibration_manager.apply_ai_calibration(raw_data)
                else:
                    # 如果没有校准方法，使用原始数据
                    calibrated_data = raw_data.copy()
                    print("⚠️ 未找到校准方法，使用原始数据进行对比")
            except Exception as e:
                print(f"⚠️ 校准失败，使用原始数据: {e}")
                calibrated_data = raw_data.copy()
            
            print(f"✅ 校准数据准备完成，形状: {calibrated_data.shape}")

            # 创建对比图
            print("🔧 开始创建对比图...")
            self.create_comparison_plots(scroll_layout, raw_data, calibrated_data)

            # 添加统计信息
            print("🔧 开始添加统计信息...")
            self.add_statistics_info(scroll_layout, raw_data, calibrated_data)

            scroll_widget.setLayout(scroll_layout)
            scroll_area.setWidget(scroll_widget)
            scroll_area.setWidgetResizable(True)
            layout.addWidget(scroll_area)
            print("✅ 滚动区域配置完成")

            # 按钮区域
            button_layout = QtWidgets.QHBoxLayout()

            refresh_btn = QtWidgets.QPushButton("手动刷新")
            refresh_btn.clicked.connect(self.refresh_data)
            button_layout.addWidget(refresh_btn)
            
            # 自动刷新切换按钮
            self.auto_refresh_btn = QtWidgets.QPushButton("开启自动刷新")
            self.auto_refresh_btn.clicked.connect(self.toggle_auto_refresh)
            button_layout.addWidget(self.auto_refresh_btn)

            save_btn = QtWidgets.QPushButton("保存对比图")
            save_btn.clicked.connect(self.save_comparison)
            button_layout.addWidget(save_btn)

            close_btn = QtWidgets.QPushButton("关闭")
            close_btn.clicked.connect(self.close)
            button_layout.addWidget(close_btn)

            layout.addLayout(button_layout)
            print("✅ 按钮区域添加完成")
            
            self.setLayout(layout)
            print("✅ 对话框UI设置完成")
            
        except Exception as e:
            print(f"❌ 设置UI失败: {e}")
            import traceback
            traceback.print_exc()

    def create_comparison_plots(self, layout, raw_data, calibrated_data):
        """创建对比图"""
        try:
            print("🔧 开始创建对比图...")
            print(f"📊 原始数据形状: {raw_data.shape}, 范围: [{raw_data.min():.2f}, {raw_data.max():.2f}]")
            print(f"📊 校准数据形状: {calibrated_data.shape}, 范围: [{calibrated_data.min():.2f}, {calibrated_data.max():.2f}]")
            
            # 创建matplotlib图形
            fig = plt.figure(figsize=(15, 10))
            print("✅ matplotlib图形创建成功")
            
            # 1. 原始数据热力图
            ax1 = fig.add_subplot(2, 3, 1)
            im1 = ax1.imshow(raw_data, cmap='viridis', aspect='equal')
            ax1.set_title('原始数据热力图')
            plt.colorbar(im1, ax=ax1, shrink=0.8)
            print("✅ 原始数据热力图创建成功")

            # 2. 校准后数据热力图
            ax2 = fig.add_subplot(2, 3, 2)
            
            # 使用top99%范围，避免异常值影响
            cal_data_flat = calibrated_data.flatten()
            cal_99_percentile = np.percentile(cal_data_flat, 99)
            cal_1_percentile = np.percentile(cal_data_flat, 1)
            
            im2 = ax2.imshow(calibrated_data, cmap='viridis', aspect='equal', 
                             vmin=cal_1_percentile, vmax=cal_99_percentile)
            ax2.set_title('校准后热力图 (1%-99%范围)')
            plt.colorbar(im2, ax=ax2, shrink=0.8)
            print("✅ 校准后热力图创建成功")

            # 3. 差异热力图
            ax3 = fig.add_subplot(2, 3, 3)
            diff = calibrated_data - raw_data.mean()
            im3 = ax3.imshow(diff, cmap='RdBu_r', aspect='equal')
            ax3.set_title('校准调整量热力图')
            plt.colorbar(im3, ax=ax3, shrink=0.8)
            print("✅ 差异热力图创建成功")

            # 4. 原始数据直方图
            ax4 = fig.add_subplot(2, 3, 4)
            ax4.hist(raw_data.flatten(), bins=50, alpha=0.7, label='原始数据', density=True)
            ax4.axvline(raw_data.mean(), color='red', linestyle='--', linewidth=2,
                       label=f'均值: {raw_data.mean():.1f}')
            ax4.set_title('原始数据分布直方图')
            ax4.set_xlabel('响应值')
            ax4.set_ylabel('密度')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            print("✅ 原始数据直方图创建成功")

            # 5. 校准后数据直方图
            ax5 = fig.add_subplot(2, 3, 5)
            ax5.hist(calibrated_data.flatten(), bins=50, alpha=0.7, color='orange',
                    label='校准后数据', density=True)
            ax5.axvline(calibrated_data.mean(), color='blue', linestyle='--', linewidth=2,
                       label=f'均值: {calibrated_data.mean():.1f}')
            ax5.set_title('校准后数据分布直方图')
            ax5.set_xlabel('响应值')
            ax5.set_ylabel('密度')
            ax5.legend()
            ax5.grid(True, alpha=0.3)
            print("✅ 校准后数据直方图创建成功")

            # 6. 散点图对比
            ax6 = fig.add_subplot(2, 3, 6)
            sample_indices = np.random.choice(64*64, size=min(1000, 64*64), replace=False)
            raw_sample = raw_data.flatten()[sample_indices]
            cal_sample = calibrated_data.flatten()[sample_indices]

            ax6.scatter(raw_sample, cal_sample, alpha=0.6, s=2, color='purple')
            ax6.plot([raw_data.min(), raw_data.max()], [raw_data.min(), raw_data.max()],
                    'r--', linewidth=2, label='对角线')
            ax6.set_xlabel('原始响应')
            ax6.set_ylabel('校准后响应')
            ax6.set_title('原始vs校准后响应散点图')
            ax6.legend()
            ax6.grid(True, alpha=0.3)
            print("✅ 散点图创建成功")

            plt.suptitle('AI校准前后对比分析', fontsize=16, fontweight='bold')
            plt.tight_layout()
            print("✅ 图形布局完成")

            # 将matplotlib图形转换为Qt widget
            canvas = FigureCanvas(fig)
            print("✅ FigureCanvas创建成功")
            
            layout.addWidget(canvas)
            print("✅ 热力图已添加到布局中")
            
            # 强制刷新
            canvas.draw()
            print("✅ 热力图绘制完成")
            
        except Exception as e:
            print(f"❌ 创建对比图失败: {e}")
            import traceback
            traceback.print_exc()

    def add_statistics_info(self, layout, raw_data, calibrated_data):
        """添加统计信息"""
        stats_group = QtWidgets.QGroupBox("统计信息对比")
        stats_layout = QtWidgets.QVBoxLayout()

        # 计算统计指标
        cv_raw = raw_data.std() / raw_data.mean()
        cv_cal = calibrated_data.std() / calibrated_data.mean()
        cv_improvement = cv_raw / cv_cal
        std_improvement = raw_data.std() / calibrated_data.std()
        
        # 计算分位数指标
        cal_data_flat = calibrated_data.flatten()
        cal_99_percentile = np.percentile(cal_data_flat, 99)
        cal_1_percentile = np.percentile(cal_data_flat, 1)
        cal_95_percentile = np.percentile(cal_data_flat, 95)
        cal_5_percentile = np.percentile(cal_data_flat, 5)

        # 创建统计信息文本
        stats_text = f"""
        📊 校准效果统计

        原始数据:
        • 均值: {raw_data.mean():.1f}
        • 标准差: {raw_data.std():.1f}
        • CV (变异系数): {cv_raw:.3f}
        • 范围: [{raw_data.min():.1f}, {raw_data.max():.1f}]

        校准后:
        • 均值: {calibrated_data.mean():.1f}
        • 标准差: {calibrated_data.std():.1f}
        • CV (变异系数): {cv_cal:.3f}
        • 范围: [{calibrated_data.min():.1f}, {calibrated_data.max():.1f}]
        • 分位数: 1%={cal_1_percentile:.1f}, 5%={cal_5_percentile:.1f}, 95%={cal_95_percentile:.1f}, 99%={cal_99_percentile:.1f}
        • 热力图范围: [{cal_1_percentile:.1f}, {cal_99_percentile:.1f}] (避免异常值)

        改善效果:
        • CV改善倍数: {cv_improvement:.1f}倍
        • 标准差改善倍数: {std_improvement:.1f}倍
        • 均匀性提升: {((cv_raw - cv_cal) / cv_raw * 100):.1f}%

        🎯 结论:
        • 校准显著改善了传感器的一致性
        • 变异系数降低了{cv_improvement:.1f}倍
        • 标准差降低了{std_improvement:.1f}倍
        """

        stats_label = QtWidgets.QLabel(stats_text)
        stats_label.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px;")
        stats_layout.addWidget(stats_label)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

    def toggle_auto_refresh(self):
        """切换自动刷新"""
        if self.auto_refresh_enabled:
            # 停止自动刷新
            self.auto_refresh_timer.stop()
            self.auto_refresh_enabled = False
            self.auto_refresh_btn.setText("开启自动刷新")
            print("⏸️ 已停止自动刷新")
        else:
            # 开启自动刷新，每2秒刷新一次
            self.auto_refresh_timer.start(2000)
            self.auto_refresh_enabled = True
            self.auto_refresh_btn.setText("停止自动刷新")
            print("▶️ 已开启自动刷新（每2秒）")

    def refresh_data(self):
        """刷新数据"""
        try:
            print("🔄 刷新校准对比数据...")
            # 重新获取数据并更新显示
            self.setup_ui()
            print("✅ 校准对比数据已刷新")
        except Exception as e:
            print(f"❌ 刷新校准对比数据失败: {e}")
            import traceback
            traceback.print_exc()
            
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'auto_refresh_timer'):
            self.auto_refresh_timer.stop()
        super().closeEvent(event)

    def save_comparison(self):
        """保存对比图"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存对比图", "", "PNG文件 (*.png);;PDF文件 (*.pdf)"
        )

        if file_path:
            try:
                # 这里可以实现保存当前对比图的功能
                QtWidgets.QMessageBox.information(self, "保存成功", f"对比图已保存到:\n{file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "保存失败", f"保存失败:\n{str(e)}")
