#!/usr/bin/env python3
"""
区域绘制类

负责在热力图上绘制识别出的区域
"""

import numpy as np
from matplotlib.patches import Circle, Rectangle
import traceback


class RegionRenderer:
    """区域渲染器"""
    
    def __init__(self, heatmap_manager):
        self.heatmap_manager = heatmap_manager
        self._last_pressure_data = None  # 保存最后的压力数据用于显示
    
    def set_pressure_data(self, pressure_data):
        """设置压力数据用于显示"""
        self._last_pressure_data = pressure_data
    
    def draw_calibrated_regions_on_heatmap(self, ax, regions, color='red', linewidth=3):
        """在校准热力图上绘制识别出的区域（使用轮廓跟踪）"""
        try:
            print(f"🎨 draw_calibrated_regions_on_heatmap 开始执行...")
            print(f"   输入参数: ax={ax}, regions数量={len(regions)}, color={color}, linewidth={linewidth}")
            print(f"   画布类型: {type(ax)}")
            print(f"   画布ID: {id(ax)}")
            
            # 清除之前的区域标记
            print(f"🧹 清除 {len(self.heatmap_manager.get_pressure_patches())} 个旧的校准区域标记")
            self.heatmap_manager.clear_pressure_patches()

            # 清除所有文本标签
            texts_to_remove = []
            for text in ax.texts:
                texts_to_remove.append(text)
            for text in texts_to_remove:
                try:
                    text.remove()
                except Exception:
                    pass

            # 绘制新的区域标记
            print(f"🎨 开始绘制 {len(regions)} 个区域...")
            for i, region in enumerate(regions):
                print(f"   绘制区域 {i+1}: ID={region.get('id', 'N/A')}")
                # print(f"     区域信息: {region}")
                
                # 为不同区域使用不同颜色
                region_color = self._get_region_color(i)
                print(f"     区域 {i+1} 使用颜色: {region_color}")
                
                if 'contour' in region and region['contour'] is not None:
                    print(f"     使用轮廓跟踪方法绘制")
                    # 使用轮廓跟踪方法绘制
                    self._draw_contour_region(ax, region, region_color, linewidth)
                else:
                    print(f"     使用边界框方法绘制（回退）")
                    # 回退到原来的边界框方法
                    self._draw_bbox_region(ax, region, region_color, linewidth)

            print(f"✅ 在校准热力图上绘制了 {len(regions)} 个区域标记")
            print(f"   使用轮廓跟踪方法 + {color}色标记")
            print(f"   当前_pressure_patches数量: {len(self.heatmap_manager.get_pressure_patches())}")

        except Exception as e:
            print(f"❌ 绘制校准区域标记失败: {e}")
            traceback.print_exc()
    
    def draw_pressure_regions_on_heatmap(self, ax, regions, color='red', linewidth=3):
        """在热力图上绘制识别出的压力区域"""
        try:
            print(f"🎨 draw_pressure_regions_on_heatmap 开始执行...")
            print(f"   颜色: {color}, 线宽: {linewidth}")
            
            # 清除之前的压力区域标记
            print(f"🧹 清除 {len(self.heatmap_manager.get_pressure_patches())} 个旧的压力区域标记")
            self.heatmap_manager.clear_pressure_patches()
            
            # 清除所有文本标签
            texts_to_remove = []
            for text in ax.texts:
                texts_to_remove.append(text)
            for text in texts_to_remove:
                try:
                    text.remove()
                except Exception:
                    pass
            
            # 强制使用轮廓绘制方法，确保所有图表显示一致
            print(f"🎨 开始绘制 {len(regions)} 个区域，强制使用轮廓方法...")
            for i, region in enumerate(regions):
                print(f"   绘制区域 {i+1}: ID={region.get('id', 'N/A')}")
                print(f"     区域完整信息: {region}")
                print(f"     轮廓存在: {'contour' in region}")
                print(f"     轮廓掩码存在: {'contour_mask' in region}")
                print(f"     轮廓值: {region.get('contour', 'None')}")
                print(f"     轮廓掩码值: {region.get('contour_mask', 'None')}")
                
                # 为不同区域使用不同颜色
                region_color = self._get_region_color(i)
                print(f"     区域 {i+1} 使用颜色: {region_color}")
                
                # 优先使用轮廓绘制，如果没有轮廓则创建轮廓
                if 'contour' in region and region['contour'] is not None:
                    print(f"     使用现有轮廓绘制")
                    self._draw_contour_region(ax, region, region_color, linewidth)
                elif 'contour_mask' in region and region['contour_mask'] is not None:
                    print(f"     从轮廓掩码创建轮廓并绘制")
                    # 从轮廓掩码创建轮廓
                    contour = self._create_contour_from_mask(region['contour_mask'])
                    if contour is not None:
                        # 临时添加轮廓信息
                        region_copy = region.copy()
                        region_copy['contour'] = contour
                        print(f"     轮廓创建成功，开始绘制")
                        self._draw_contour_region(ax, region_copy, region_color, linewidth)
                    else:
                        print(f"     轮廓创建失败，使用边界框方法")
                        self._draw_bbox_region(ax, region, region_color, linewidth)
                else:
                    print(f"     没有轮廓信息，使用边界框方法")
                    self._draw_bbox_region(ax, region, region_color, linewidth)
            
            print(f"✅ 在热力图上绘制了 {len(regions)} 个区域标记")
            print(f"   使用{color}色轮廓线 + 黄色虚线矩形标记")
            
        except Exception as e:
            print(f"❌ 绘制压力区域标记失败: {e}")
            traceback.print_exc()
    
    def _get_region_color(self, index):
        """获取区域颜色"""
        colors = ['red', 'orange', 'blue', 'green', 'purple', 'brown', 'pink', 'cyan', 'magenta', 'lime']
        if index < len(colors):
            return colors[index]
        return 'red'  # 默认颜色
    
    def _draw_contour_region(self, ax, region, color, linewidth):
        """绘制轮廓区域"""
        try:
            contour = region['contour']
            center_x, center_y = region['center']

            # 绘制轮廓线
            contour_points = contour.reshape(-1, 2)
            line, = ax.plot(contour_points[:, 0], contour_points[:, 1],
                           color=color, linewidth=linewidth, alpha=0.8)
            self.heatmap_manager.add_pressure_patch(line)

            # 添加区域标签
            text1 = ax.text(center_x, center_y, f'{region["id"]}',
                           color=color, fontsize=12, fontweight='bold',
                           ha='center', va='center',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))

            # 根据颜色判断显示什么数值
            if color == 'blue':
                # 蓝色圈（压力图）：显示压力值
                if self._last_pressure_data is not None:
                    region_mask = region['contour_mask']
                    region_pressure_values = self._last_pressure_data[region_mask == 1]
                    avg_pressure = region_pressure_values.mean()
                    value_text = f'{avg_pressure:.1f}N'
                    print(f"   区域 {region['id']}: 平均压力 {avg_pressure:.1f}N")
                else:
                    value_text = f'P{region["id"]}'
            else:
                # 红色圈（校准图）：显示校准值
                # 🆕 修复：智能获取校准值，兼容不同的区域数据结构
                if 'avg_calibrated' in region:
                    value_text = f'{region["avg_calibrated"]:.1f}'
                elif 'simple_score' in region:
                    value_text = f'{region["simple_score"]:.1f}'
                elif 'area' in region:
                    value_text = f'{region["area"]:.0f}'
                else:
                    value_text = f'R{region["id"]}'

            text2 = ax.text(center_x, center_y + 15, value_text,
                           color=color, fontsize=10, fontweight='bold',
                           ha='center', va='bottom',
                           bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))

            # 添加区域信息标签
            info_text = f'面积: {region["area"]}\n紧凑度: {region["compactness"]:.3f}'
            text3 = ax.text(center_x + 20, center_y, info_text,
                           color=color, fontsize=8, alpha=0.7,
                           ha='left', va='center',
                           bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.6))
            
            print(f"     轮廓区域绘制完成，只显示轮廓线，不显示边界框")

        except Exception as e:
            print(f"❌ 绘制轮廓区域失败: {e}")
            # 回退到边界框方法
            self._draw_bbox_region(ax, region, color, linewidth)

    def _draw_bbox_region(self, ax, region, color, linewidth):
        """绘制边界框区域（回退方法）"""
        try:
            center_x, center_y = region['center']
            min_x, min_y, max_x, max_y = region['bbox']

            # 计算矩形参数
            width = max_x - min_x + 1
            height = max_y - min_y + 1

            # 确保最小尺寸
            width = max(width, 3)
            height = max(height, 3)

            # 🆕 修复：使用矩形而不是椭圆
            from matplotlib.patches import Rectangle
            rectangle = Rectangle(
                xy=(min_x, min_y),
                width=width,
                height=height,
                fill=False,
                edgecolor=color,
                linewidth=linewidth,
                linestyle='-',
                alpha=0.8
            )
            ax.add_patch(rectangle)
            self.heatmap_manager.add_pressure_patch(rectangle)

            # 添加区域标签
            text1 = ax.text(center_x, center_y, f'{region["id"]}',
                           color=color, fontsize=12, fontweight='bold',
                           ha='center', va='center',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))

            # 添加数值标签
            if color == 'blue':
                if self._last_pressure_data is not None:
                    # 智能处理不同的mask键名
                    if 'contour_mask' in region:
                        region_mask = region['contour_mask']
                    elif 'mask' in region:
                        region_mask = region['mask']
                    else:
                        print(f"⚠️ 区域 {region.get('id', 'unknown')} 缺少mask信息")
                        value_text = f'P{region["id"]}'
                        # 跳过这个区域的处理
                        avg_pressure = 0  # 设置默认值
                        value_text = f'P{region["id"]}'

                    region_pressure_values = self._last_pressure_data[region_mask]
                    avg_pressure = region_pressure_values.mean()
                    value_text = f'{avg_pressure:.1f}N'
                else:
                    value_text = f'P{region["id"]}'
            else:
                # 🆕 修复：智能获取校准值，兼容不同的区域数据结构
                if 'avg_calibrated' in region:
                    value_text = f'{region["avg_calibrated"]:.1f}'
                elif 'simple_score' in region:
                    value_text = f'{region["simple_score"]:.1f}'
                elif 'area' in region:
                    value_text = f'{region["area"]:.0f}'
                else:
                    value_text = f'R{region["id"]}'

            text2 = ax.text(center_x, center_y + height/2 + 8, value_text,
                           color=color, fontsize=10, fontweight='bold',
                           ha='center', va='bottom',
                           bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
            
            print(f"     边界框区域绘制完成，显示矩形边界框")

        except Exception as e:
            print(f"❌ 绘制边界框区域失败: {e}")
    
    def _create_contour_from_mask(self, contour_mask):
        """从轮廓掩码创建轮廓"""
        try:
            if contour_mask is None:
                return None
            
            # 确保掩码是uint8类型
            mask_uint8 = contour_mask.astype(np.uint8)
            
            # 使用OpenCV查找轮廓
            import cv2
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # 返回最大的轮廓
                largest_contour = max(contours, key=cv2.contourArea)
                print(f"     从掩码创建轮廓成功，轮廓点数: {len(largest_contour)}")
                return largest_contour
            else:
                print(f"     从掩码创建轮廓失败：没有找到轮廓")
                return None
                
        except Exception as e:
            print(f"     从掩码创建轮廓异常: {e}")
            return None
