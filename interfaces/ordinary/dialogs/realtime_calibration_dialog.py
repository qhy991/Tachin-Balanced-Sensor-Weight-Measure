"""
实时校准对话框

显示AI校准前后的实时对比
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtWidgets, QtCore


class RealtimeCalibrationDialog(QtWidgets.QDialog):
    """实时校准前后对比对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("AI校准实时对比")
        self.setGeometry(200, 200, 1000, 600)
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 设置实时更新定时器
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_comparison)
        self.update_timer.start(500)  # 每500ms更新一次，减少CPU占用
        
        # 添加数据变化检测
        self._last_raw_data = None
        self._update_count = 0
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title = QtWidgets.QLabel("AI校准实时对比 - 校准前 vs 校准后")
        title.setStyleSheet("font-size: 16px; font-weight: bold; text-align: center;")
        layout.addWidget(title)
        
        # 创建两个热力图的布局
        heatmap_layout = QtWidgets.QHBoxLayout()
        
        # 左侧：校准前热力图
        self.raw_canvas = self.create_heatmap_canvas("校准前 - 原始数据")
        heatmap_layout.addWidget(self.raw_canvas)
        
        # 右侧：校准后热力图
        self.calibrated_canvas = self.create_heatmap_canvas("校准后 - AI校准数据")
        heatmap_layout.addWidget(self.calibrated_canvas)
        
        layout.addLayout(heatmap_layout)
        
        # 统计信息
        self.stats_label = QtWidgets.QLabel("统计信息加载中...")
        self.stats_label.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px; padding: 10px;")
        layout.addWidget(self.stats_label)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        # 强制刷新按钮
        refresh_btn = QtWidgets.QPushButton("强制刷新")
        refresh_btn.clicked.connect(self.force_refresh)
        button_layout.addWidget(refresh_btn)
        
        # 保存截图按钮
        save_btn = QtWidgets.QPushButton("保存截图")
        save_btn.clicked.connect(self.save_screenshot)
        button_layout.addWidget(save_btn)
        
        # 关闭按钮
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def create_heatmap_canvas(self, title):
        """创建热力图画布"""
        # 创建matplotlib图形
        fig = plt.figure(figsize=(6, 5))
        ax = fig.add_subplot(111)
        
        # 设置中文字体
        try:
            # 设置matplotlib中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            
            # 设置标题字体
            ax.set_title(title, fontsize=12, fontfamily='SimHei')
        except Exception as e:
            print(f"⚠️ 设置热力图中文字体失败: {e}")
            ax.set_title(title, fontsize=12)
        
        # 创建初始热力图（空数据）
        im = ax.imshow(np.zeros((64, 64)), cmap='viridis', aspect='equal')
        plt.colorbar(im, ax=ax, shrink=0.8)
        
        # 将matplotlib图形转换为Qt widget
        canvas = FigureCanvas(fig)
        canvas.setMinimumSize(400, 300)
        
        return canvas
        
    def update_comparison(self):
        """更新对比数据"""
        try:
            # 获取当前数据
            raw_data = self.parent.get_current_frame_data()
            
            # 检查数据是否真的在变化
            if hasattr(self, '_last_raw_data'):
                if np.array_equal(raw_data, self._last_raw_data):
                    return
            self._last_raw_data = raw_data.copy()
            
            # 应用AI校准
            if self.parent.calibration_coeffs is not None:
                calibrated_data = self.parent.apply_ai_calibration(raw_data)
            
                self._update_count += 1
                print(f"🔄 更新AI校准对比数据 #{self._update_count}")
                
                # 更新热力图
                self.update_heatmaps(raw_data, calibrated_data)
                
                # 更新统计信息
                self.update_statistics(raw_data, calibrated_data)
            else:
                self.stats_label.setText("AI校准模型未加载")
                
        except Exception as e:
            print(f"❌ 更新AI校准对比失败: {e}")
    
    def update_heatmaps(self, raw_data, calibrated_data):
        """更新热力图"""
        try:
            # 更新原始数据热力图
            raw_fig = self.raw_canvas.figure
            raw_ax = raw_fig.axes[0]
            raw_im = raw_ax.images[0]
            raw_im.set_array(raw_data)
            raw_im.set_clim(raw_data.min(), raw_data.max())
            raw_fig.canvas.draw()
            
            # 更新校准后热力图
            cal_fig = self.calibrated_canvas.figure
            cal_ax = cal_fig.axes[0]
            cal_im = cal_ax.images[0]
            cal_im.set_array(calibrated_data)
            
            # 使用百分位数范围避免异常值
            cal_data_flat = calibrated_data.flatten()
            cal_vmin = np.percentile(cal_data_flat, 1)
            cal_vmax = np.percentile(cal_data_flat, 99)
            cal_im.set_clim(cal_vmin, cal_vmax)
            cal_fig.canvas.draw()
            
        except Exception as e:
            print(f"❌ 更新热力图失败: {e}")
    
    def update_statistics(self, raw_data, calibrated_data):
        """更新统计信息"""
        try:
            raw_mean = raw_data.mean()
            raw_std = raw_data.std()
            raw_min = raw_data.min()
            raw_max = raw_data.max()
            raw_range = raw_data.max() - raw_data.min()
            
            cal_mean = calibrated_data.mean()
            cal_std = calibrated_data.std()
            cal_min = calibrated_data.min()
            cal_max = calibrated_data.max()
            cal_range = calibrated_data.max() - calibrated_data.min()
            
            # 计算改善程度
            std_improvement = (raw_std - cal_std) / raw_std * 100 if raw_std > 0 else 0
            
            stats_text = f"""实时统计信息 (第{self._update_count}帧):

校准前 - 原始数据:
  均值: {raw_mean:.2f}
  标准差: {raw_std:.2f}
  最小值: {raw_min:.2f}
  最大值: {raw_max:.2f}
  范围: {raw_range:.2f}

校准后 - AI校准数据:
  均值: {cal_mean:.2f}
  标准差: {cal_std:.2f}
  最小值: {cal_min:.2f}
  最大值: {cal_max:.2f}
  范围: {cal_range:.2f}

改善效果:
  标准差改善: {std_improvement:+.1f}%
  {'✅ 校准有效' if std_improvement > 0 else '⚠️ 校准效果不佳'}"""
            
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            print(f"❌ 更新统计信息失败: {e}")
    
    def force_refresh(self):
        """强制刷新"""
        self._last_raw_data = None
        self.update_comparison()
    
    def save_screenshot(self):
        """保存截图"""
        try:
            filename = f"AI校准对比_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.grab().save(filename)
            print(f"✅ 截图已保存: {filename}")
            QtWidgets.QMessageBox.information(self, "保存成功", f"截图已保存为: {filename}")
        except Exception as e:
            print(f"❌ 保存截图失败: {e}")
            QtWidgets.QMessageBox.critical(self, "保存失败", f"保存截图失败:\n{str(e)}")
            
    def closeEvent(self, event):
        """关闭事件"""
        self.update_timer.stop()
        event.accept()



# class RealtimeCalibrationDialog(QtWidgets.QDialog):
    """实时校准前后对比对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("AI校准实时对比")
        self.setGeometry(200, 200, 1000, 600)
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 设置实时更新定时器
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_comparison)
        self.update_timer.start(500)  # 每500ms更新一次，减少CPU占用
        
        # 添加数据变化检测
        self._last_raw_data = None
        self._update_count = 0
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title = QtWidgets.QLabel("AI校准实时对比 - 校准前 vs 校准后")
        title.setStyleSheet("font-size: 16px; font-weight: bold; text-align: center;")
        layout.addWidget(title)
        
        # 创建两个热力图的布局
        heatmap_layout = QtWidgets.QHBoxLayout()
        
        # 左侧：校准前热力图
        self.raw_canvas = self.create_heatmap_canvas("校准前 - 原始数据")
        heatmap_layout.addWidget(self.raw_canvas)
        
        # 右侧：校准后热力图
        self.calibrated_canvas = self.create_heatmap_canvas("校准后 - AI校准数据")
        heatmap_layout.addWidget(self.calibrated_canvas)
        
        layout.addLayout(heatmap_layout)
        
        # 统计信息
        self.stats_label = QtWidgets.QLabel("统计信息加载中...")
        self.stats_label.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px; padding: 10px;")
        layout.addWidget(self.stats_label)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        # 强制刷新按钮
        refresh_btn = QtWidgets.QPushButton("强制刷新")
        refresh_btn.clicked.connect(self.force_refresh)
        button_layout.addWidget(refresh_btn)
        
        # 保存截图按钮
        save_btn = QtWidgets.QPushButton("保存截图")
        save_btn.clicked.connect(self.save_screenshot)
        button_layout.addWidget(save_btn)
        
        # 关闭按钮
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def create_heatmap_canvas(self, title):
        """创建热力图画布"""
        # 创建matplotlib图形
        fig = plt.figure(figsize=(6, 5))
        ax = fig.add_subplot(111)
        
        # 设置中文字体
        try:
            # 设置matplotlib中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            
            # 设置标题字体
            ax.set_title(title, fontsize=12, fontfamily='SimHei')
        except Exception as e:
            print(f"⚠️ 设置热力图中文字体失败: {e}")
            ax.set_title(title, fontsize=12)
        
        # 创建初始热力图（空数据）
        im = ax.imshow(np.zeros((64, 64)), cmap='viridis', aspect='equal')
        plt.colorbar(im, ax=ax, shrink=0.8)
        
        # 将matplotlib图形转换为Qt widget
        canvas = FigureCanvas(fig)
        canvas.setMinimumSize(400, 300)
        
        return canvas
        
    def update_comparison(self):
        """更新对比数据"""
        try:
            # 获取当前数据
            raw_data = self.parent.get_current_frame_data()
            
            # 检查数据是否真的在变化
            if hasattr(self, '_last_raw_data'):
                if np.array_equal(raw_data, self._last_raw_data):
                    return
            self._last_raw_data = raw_data.copy()
            
            # 应用AI校准
            if self.parent.calibration_coeffs is not None:
                calibrated_data = self.parent.apply_ai_calibration(raw_data)
            
                self._update_count += 1
                print(f"🔄 更新AI校准对比数据 #{self._update_count}")
                
                # 更新热力图
                self.update_heatmaps(raw_data, calibrated_data)
                
                # 更新统计信息
                self.update_statistics(raw_data, calibrated_data)
            else:
                self.stats_label.setText("AI校准模型未加载")
                
        except Exception as e:
            print(f"❌ 更新AI校准对比失败: {e}")
    
    def update_heatmaps(self, raw_data, calibrated_data):
        """更新热力图"""
        try:
            # 更新原始数据热力图
            raw_fig = self.raw_canvas.figure
            raw_ax = raw_fig.axes[0]
            raw_im = raw_ax.images[0]
            raw_im.set_array(raw_data)
            raw_im.set_clim(raw_data.min(), raw_data.max())
            raw_fig.canvas.draw()
            
            # 更新校准后热力图
            cal_fig = self.calibrated_canvas.figure
            cal_ax = cal_fig.axes[0]
            cal_im = cal_ax.images[0]
            cal_im.set_array(calibrated_data)
            
            # 使用百分位数范围避免异常值
            cal_data_flat = calibrated_data.flatten()
            cal_vmin = np.percentile(cal_data_flat, 1)
            cal_vmax = np.percentile(cal_data_flat, 99)
            cal_im.set_clim(cal_vmin, cal_vmax)
            cal_fig.canvas.draw()
            
        except Exception as e:
            print(f"❌ 更新热力图失败: {e}")
    
    def update_statistics(self, raw_data, calibrated_data):
        """更新统计信息"""
        try:
            raw_mean = raw_data.mean()
            raw_std = raw_data.std()
            raw_min = raw_data.min()
            raw_max = raw_data.max()
            raw_range = raw_data.max() - raw_data.min()
            
            cal_mean = calibrated_data.mean()
            cal_std = calibrated_data.std()
            cal_min = calibrated_data.min()
            cal_max = calibrated_data.max()
            cal_range = calibrated_data.max() - calibrated_data.min()
            
            # 计算改善程度
            std_improvement = (raw_std - cal_std) / raw_std * 100 if raw_std > 0 else 0
            
            stats_text = f"""实时统计信息 (第{self._update_count}帧):

校准前 - 原始数据:
  均值: {raw_mean:.2f}
  标准差: {raw_std:.2f}
  最小值: {raw_min:.2f}
  最大值: {raw_max:.2f}
  范围: {raw_range:.2f}

校准后 - AI校准数据:
  均值: {cal_mean:.2f}
  标准差: {cal_std:.2f}
  最小值: {cal_min:.2f}
  最大值: {cal_max:.2f}
  范围: {cal_range:.2f}

改善效果:
  标准差改善: {std_improvement:+.1f}%
  {'✅ 校准有效' if std_improvement > 0 else '⚠️ 校准效果不佳'}"""
            
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            print(f"❌ 更新统计信息失败: {e}")
    
    def force_refresh(self):
        """强制刷新"""
        self._last_raw_data = None
        self.update_comparison()
    
    def save_screenshot(self):
        """保存截图"""
        try:
            filename = f"AI校准对比_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.grab().save(filename)
            print(f"✅ 截图已保存: {filename}")
            QtWidgets.QMessageBox.information(self, "保存成功", f"截图已保存为: {filename}")
        except Exception as e:
            print(f"❌ 保存截图失败: {e}")
            QtWidgets.QMessageBox.critical(self, "保存失败", f"保存截图失败:\n{str(e)}")
            
    def closeEvent(self, event):
        """关闭事件"""
        self.update_timer.stop()
        event.accept()

# ==================== 双校准器实时比较对话框 ====================



# ==================== 原有校准对比对话框 ====================
