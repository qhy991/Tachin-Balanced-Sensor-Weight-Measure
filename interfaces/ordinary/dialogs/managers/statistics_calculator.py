#!/usr/bin/env python3
"""
统计计算器

负责计算和更新双校准比较对话框的各种统计信息
"""

import numpy as np
from PyQt5 import QtWidgets


class StatisticsCalculator:
    """统计计算器"""

    def __init__(self, dialog):
        self.dialog = dialog

    def update_statistics(self, results):
        """更新统计信息"""
        print("🔧 开始更新统计信息...")

        # 使用StatisticsManager更新所有统计信息
        self.dialog.statistics_manager.update_raw_statistics(results)
        print("   ✅ 原始数据统计更新完成")

        self.dialog.statistics_manager.update_new_statistics(results)
        print("   ✅ 新版本校准统计更新完成")

        self.dialog.statistics_manager.update_change_data_statistics(results)  # 🆕 新增：更新变化量统计
        print("   ✅ 变化量统计更新完成")

        self.dialog.statistics_manager.update_region_calibration_statistics(results)  # 🆕 新增：更新区域校准值统计
        print("   ✅ 区域校准值统计更新完成")

        # 🆕 新增：更新压强热力图统计
        self.dialog.statistics_manager.update_pressure_heatmap_statistics(results)
        print("   ✅ 压强热力图统计更新完成")

        # 🆕 新增：更新负值响应统计
        self._update_negative_response_statistics(results)
        print("   ✅ 负值响应统计更新完成")

        print("🎉 所有统计信息更新完成")

    def _update_negative_response_statistics(self, results):
        """更新负值响应统计信息"""
        try:
            if hasattr(self.dialog, 'negative_response_stats_label'):
                if 'negative_response' in results:
                    nr_info = results['negative_response']

                    if nr_info.get('has_negative', False):
                        count = nr_info['count']
                        min_val = nr_info['min_value']
                        max_val = nr_info['max_value']
                        mean_val = nr_info['mean_value']
                        std_val = nr_info['std_value']

                        text = f"""负值响应统计:
检测到: {count} 个负值点
均值: {mean_val:.2f}
标准差: {std_val:.2f}
最小值: {min_val:.2f}
最大值: {max_val:.2f}"""

                        # 分析负值点坐标分布
                        if 'coordinates' in nr_info and nr_info['coordinates']:
                            coords = nr_info['coordinates']
                            rows = [coord[0] for coord in coords]
                            cols = [coord[1] for coord in coords]

                            text += f"""
坐标范围:
行: {min(rows)}-{max(rows)}
列: {min(cols)}-{max(cols)}"""

                    else:
                        text = "负值响应统计:\n✅ 未检测到负值响应点"

                    self.dialog.negative_response_stats_label.setText(text)
                else:
                    self.dialog.negative_response_stats_label.setText("等待数据...")

        except Exception as e:
            print(f"⚠️ 更新负值响应统计失败: {e}")
            if hasattr(self.dialog, 'negative_response_stats_label'):
                self.dialog.negative_response_stats_label.setText("统计更新失败")

    def update_region_stats_labels(self, regions, results):
        """更新区域统计标签（优化版：合并显示，动态调整）"""
        try:
            if not regions:
                # 没有区域时，显示等待状态
                self._set_region_stats_labels_empty()
                return

            # 合并显示所有区域统计信息
            if hasattr(self.dialog, 'region1_stats_label'):
                combined_stats_text = self._generate_combined_region_stats_text(regions, results)
                self.dialog.region1_stats_label.setText(combined_stats_text)

                # 根据区域数量调整标签样式
                if len(regions) == 1:
                    self.dialog.region1_stats_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #27ae60;")
                else:
                    self.dialog.region1_stats_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #9b59b6;")

            # 隐藏第二个标签，避免冗余显示
            if hasattr(self.dialog, 'region2_stats_label'):
                if len(regions) <= 1:
                    self.dialog.region2_stats_label.setVisible(False)
                else:
                    self.dialog.region2_stats_label.setVisible(True)
                    self.dialog.region2_stats_label.setText("区域统计已合并显示")
                    self.dialog.region2_stats_label.setStyleSheet("font-family: monospace; font-size: 10px; color: #95a5a6;")

            print(f"✅ 区域统计标签更新完成，共 {len(regions)} 个区域")

        except Exception as e:
            print(f"⚠️ 更新区域统计标签失败: {e}")
            import traceback
            traceback.print_exc()

    def _set_region_stats_labels_empty(self):
        """设置区域统计标签为空状态"""
        if hasattr(self.dialog, 'region1_stats_label'):
            self.dialog.region1_stats_label.setText("等待区域数据...")
        if hasattr(self.dialog, 'region2_stats_label'):
            self.dialog.region2_stats_label.setText("等待区域数据...")

    def _generate_combined_region_stats_text(self, regions, results):
        """生成合并的区域统计文本（使用kPa单位显示压强信息）"""
        try:
            if not regions:
                return "等待区域数据..."

            # 根据区域数量生成不同的标题
            if len(regions) == 1:
                title = "区域统计 (1个区域)"
            else:
                title = f"区域统计 ({len(regions)}个区域)"

            combined_text = f"{title}\n"
            combined_text += "=" * 30 + "\n"

            # 逐个添加区域统计信息
            for i, region in enumerate(regions):
                region_stats = self._calculate_region_stats(region, results)

                # 区域标题
                combined_text += f"区域 {i+1}:\n"
                combined_text += f"  面积: {region_stats['area']} 像素\n"
                combined_text += f"  中心: ({region_stats['center_x']}, {region_stats['center_y']})\n"

                # 显示响应值信息
                if region_stats['avg_response'] > 0:
                    combined_text += f"  平均响应值: {region_stats['avg_response']:.2f}\n"
                    combined_text += f"  响应值范围: [{region_stats['min_response']:.2f}, {region_stats['max_response']:.2f}]\n"
                else:
                    combined_text += "  平均响应值: 未计算\n"

                # 使用kPa单位显示压强信息
                combined_text += f"  平均压强: {region_stats['avg_pressure']:.2f} kPa\n"
                combined_text += f"  最大压强: {region_stats['max_pressure']:.2f} kPa\n"
                combined_text += f"  压强密度: {region_stats['pressure_density']:.3f} kPa/像素\n"
                combined_text += f"  压强评分: {region_stats['pressure_score']:.2f}\n"
                combined_text += f"  紧凑度: {region_stats['compactness']:.3f}\n"

                # 添加说明：解释热力图和统计值的差异
                if region_stats['max_pressure'] > 50:  # 如果最大值超过50 kPa
                    combined_text += "  📊 注意：热力图显示范围已优化，实际最大值可能更高\n"

                # 如果不是最后一个区域，添加分隔线
                if i < len(regions) - 1:
                    combined_text += "  " + "-" * 20 + "\n"

            # 添加汇总信息
            if len(regions) > 1:
                combined_text += "\n汇总信息:\n"
                combined_text += "=" * 30 + "\n"

                # 计算所有区域的总面积
                total_area = sum(self._calculate_region_stats(r, results)['area'] for r in regions)
                combined_text += f"总检测面积: {total_area} 像素\n"

                # 计算所有区域的平均压强
                all_pressures = []
                for region in regions:
                    region_stats = self._calculate_region_stats(region, results)
                    if region_stats['avg_pressure'] > 0:
                        all_pressures.append(region_stats['avg_pressure'])

                if all_pressures:
                    avg_total_pressure = np.mean(all_pressures)
                    max_total_pressure = max(all_pressures)
                    combined_text += f"平均压强: {avg_total_pressure:.2f} kPa\n"
                    combined_text += f"最大压强: {max_total_pressure:.2f} kPa\n"

            return combined_text

        except Exception as e:
            print(f"⚠️ 生成合并区域统计文本失败: {e}")
            return f"区域统计生成失败: {str(e)}"

    def _calculate_region_stats(self, region, results):
        """计算单个区域的统计信息"""
        try:
            # 基础信息
            area = region.get('area', 0)
            center = region.get('center', (0, 0))
            center_x, center_y = center
            compactness = region.get('compactness', 0.0)

            # 压力强度信息
            avg_pressure = region.get('avg_pressure', 0.0)
            max_pressure = region.get('max_pressure', 0.0)
            pressure_density = region.get('pressure_density', 0.0)
            pressure_score = region.get('pressure_score', 0.0)

            # 计算区域的平均响应值
            avg_response = 0.0
            max_response = 0.0
            min_response = 0.0

            # 尝试从校准数据中获取响应值
            if 'new' in results and 'data' in results['new']:
                calibrated_data = results['new']['data']

                if 'contour_mask' in region:
                    contour_mask = region['contour_mask']
                    region_response_values = calibrated_data[contour_mask == 1]

                    if len(region_response_values) > 0:
                        avg_response = float(region_response_values.mean())
                        max_response = float(region_response_values.max())
                        min_response = float(region_response_values.min())

                        # 分析负响应值
                        negative_responses = region_response_values[region_response_values < 0]
                        if len(negative_responses) > 0:
                            print(f"   ⚠️ 发现 {len(negative_responses)} 个负响应值!")
                            print(f"      负响应值范围: [{negative_responses.min():.2f}, {negative_responses.max():.2f}]")
                            print(f"      负响应值占比: {len(negative_responses)/len(region_response_values)*100:.1f}%")

                            # 详细分析负响应值的原因
                            self.dialog._analyze_negative_responses(region, contour_mask, results, negative_responses)

            # 如果没有压力强度信息，尝试从压力数据计算
            if avg_pressure == 0.0 and 'new' in results and 'pressure_data' in results['new']:
                pressure_data = results['new']['pressure_data']

                if 'contour_mask' in region:
                    contour_mask = region['contour_mask']
                    region_pressures = pressure_data[contour_mask == 1]

                    if len(region_pressures) > 0:
                        avg_pressure = float(region_pressures.mean())
                        max_pressure = float(region_pressures.max())
                        pressure_density = float(np.sum(region_pressures) / area) if area > 0 else 0.0
                else:
                    # 使用边界框估算
                    bbox = region.get('bbox', (0, 0, 1, 1))
                    x1, y1, x2, y2 = bbox
                    region_pressures = pressure_data[y1:y2, x1:x2]
                    avg_pressure = float(region_pressures.mean())
                    max_pressure = float(region_pressures.max())
                    pressure_density = float(np.sum(region_pressures) / area) if area > 0 else 0.0

            # 计算压力评分
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
                'pressure_score': pressure_score,
                'avg_response': avg_response,
                'max_response': max_response,
                'min_response': min_response
            }

        except Exception as e:
            print(f"⚠️ 计算区域统计失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'area': 0, 'center_x': 0, 'center_y': 0, 'compactness': 0.0,
                'avg_pressure': 0.0, 'max_pressure': 0.0, 'pressure_density': 0.0, 'pressure_score': 0.0,
                'avg_response': 0.0, 'max_response': 0.0, 'min_response': 0.0
            }
