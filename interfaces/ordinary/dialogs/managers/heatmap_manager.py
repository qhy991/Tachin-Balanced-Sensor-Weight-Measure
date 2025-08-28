#!/usr/bin/env python3
"""
热力图管理类

负责所有热力图的创建、更新和渲染
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtWidgets
import traceback


class HeatmapManager:
    """热力图管理器"""
    
    def __init__(self):
        self._pressure_patches = []  # 保存压力区域的图形元素
        
    def create_heatmap_canvas(self, title):
        """创建热力图画布"""
        try:
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
            
        except Exception as e:
            print(f"❌ 创建热力图画布失败: {e}")
            traceback.print_exc()
            return None
    
    def update_single_heatmap(self, canvas, data, data_type=None):
        """更新单个热力图"""
        try:
            fig = canvas.figure
            ax = fig.axes[0]
            im = ax.images[0]
            
            # 更新数据
            im.set_array(data)
            
            # 🆕 新增：根据数据类型选择合适的颜色范围策略
            if data_type == 'region_calibration':
                # 区域校准值热力图：使用新版本校准数据的实际范围
                # 由于大部分区域为0，只考虑非零区域的数据范围
                non_zero_data = data[data > 0]
                if len(non_zero_data) > 0:
                    # 使用非零数据的实际范围，稍微扩展一点以便观察
                    data_min = float(non_zero_data.min())
                    data_max = float(non_zero_data.max())
                    data_range = data_max - data_min
                    
                    # 扩展范围以便更好地观察选中区域
                    margin = data_range * 0.1  # 10%的边距
                    vmin = max(0, data_min - margin)  # 确保最小值不小于0
                    vmax = data_max + margin
                    
                    print(f"🎨 区域校准值热力图颜色范围: [{vmin:.2f}, {vmax:.2f}]")
                    print(f"   非零数据范围: [{data_min:.2f}, {data_max:.2f}]")
                    print(f"   扩展边距: {margin:.2f}")
                else:
                    # 没有非零数据，使用默认范围
                    vmin = 0
                    vmax = 1
                    print(f"⚠️ 区域校准值热力图没有非零数据，使用默认范围 [0, 1]")
            
            elif data_type == 'pressure':
                # 压强热力图：使用检测区域的压强值范围，确保与区域统计一致
                non_zero_data = data[data > 0]
                if len(non_zero_data) > 0:
                    # 使用非零压强数据的实际范围，稍微扩展一点以便观察
                    data_min = float(non_zero_data.min())
                    data_max = float(non_zero_data.max())
                    data_range = data_max - data_min
                    
                    # 🔧 修复：限制最大显示范围，避免异常值影响可视化
                    # 使用95%分位数作为上限，避免极端值
                    data_95_percentile = float(np.percentile(non_zero_data, 95))
                    
                    # 扩展范围以便更好地观察压强分布
                    margin = data_range * 0.1  # 10%的边距
                    vmin = max(0, data_min - margin)  # 确保最小值不小于0（压强不能为负）
                    
                    # 使用95%分位数和实际最大值的较小值，确保可视化合理
                    vmax = min(data_max + margin, data_95_percentile * 1.2)
                    
                    print(f"🎨 压强热力图颜色范围: [{vmin:.2f}, {vmax:.2f}] kPa")
                    print(f"   非零压强范围: [{data_min:.2f}, {data_max:.2f}] kPa")
                    print(f"   95%分位数: {data_95_percentile:.2f} kPa")
                    print(f"   扩展边距: {margin:.2f} kPa")
                    print(f"   ⚠️ 注意：热力图显示范围已限制，实际最大值 {data_max:.2f} kPa")
                else:
                    # 没有非零数据，使用默认范围
                    vmin = 0
                    vmax = 1
                    print(f"⚠️ 压强热力图没有非零数据，使用默认范围 [0, 1] kPa")
            
            else:
                # 其他热力图：使用原有的智能颜色范围计算
                data_flat = data.flatten()
                
                # 计算数据的实际范围
                data_min = float(data.min())
                data_max = float(data.max())
                data_range = data_max - data_min
                
                # 根据数据范围选择合适的颜色映射策略
                if data_range < 1e-6:  # 数据几乎为0
                    vmin = -0.1
                    vmax = 0.1
                    print(f"⚠️ 数据范围过小 ({data_range:.6f})，使用默认范围 [-0.1, 0.1]")
                elif data_range < 1.0:  # 数据范围很小
                    # 使用数据均值±范围/2，确保能看到变化
                    data_mean = float(data.mean())
                    half_range = max(data_range / 2, 0.1)  # 最小范围0.1
                    vmin = data_mean - half_range
                    vmax = data_mean + half_range
                    print(f"🔧 数据范围较小 ({data_range:.6f})，使用均值±范围/2: [{vmin:.6f}, {vmax:.6f}]")
                else:
                    # 正常情况：使用更保守的百分位数，确保颜色范围合理
                    vmin = np.percentile(data_flat, 5)   # 从1%改为5%
                    vmax = np.percentile(data_flat, 95)  # 从99%改为95%
                    
                    # 确保颜色范围不会太窄
                    min_range = data_range * 0.3  # 最小范围是数据范围的30%
                    if (vmax - vmin) < min_range:
                        center = (vmax + vmin) / 2
                        vmin = center - min_range / 2
                        vmax = center + min_range / 2
                        print(f"🔧 调整颜色范围以确保可见性: [{vmin:.6f}, {vmax:.6f}]")
            
            # 设置颜色范围
            im.set_clim(vmin, vmax)
            
            # 强制刷新画布
            fig.canvas.draw()
            
            print(f"✅ 热力图更新完成，颜色范围: [{vmin:.6f}, {vmax:.6f}]")
            
        except Exception as e:
            print(f"❌ 更新热力图失败: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_pressure_patches(self):
        """清除压力区域标记"""
        try:
            for patch in self._pressure_patches:
                try:
                    patch.remove()
                except Exception:
                    pass
            self._pressure_patches.clear()
            print(f"✅ 压力区域标记已清除")
        except Exception as e:
            print(f"❌ 清除压力区域标记失败: {e}")
    
    def get_pressure_patches(self):
        """获取压力区域标记列表"""
        return self._pressure_patches
    
    def add_pressure_patch(self, patch):
        """添加压力区域标记"""
        self._pressure_patches.append(patch)
