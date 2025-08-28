#!/usr/bin/env python3
"""
区域分析管理器

负责处理区域识别、分析和可视化的复杂逻辑
"""

import numpy as np
import cv2
from PyQt5 import QtWidgets


class RegionAnalysisManager:
    """区域分析管理器"""

    def __init__(self, dialog):
        self.dialog = dialog

    def identify_pressure_regions_morphological(self, pressure_data, threshold_percentile=80):
        """使用轮廓跟踪方法识别压力区域点"""
        try:
            print("🔍 开始轮廓跟踪压力区域识别...")
            print(f"   压力数据范围: [{pressure_data.min():.2f}N, {pressure_data.max():.2f}N]")
            # 1. 阈值分割：使用百分位数确定阈值
            threshold = np.percentile(pressure_data, threshold_percentile)
            print(f"   阈值 (第{threshold_percentile}百分位): {threshold:.2f}N")
            # 2. 二值化
            binary_mask = pressure_data > threshold
            print(f"   二值化后激活点数: {binary_mask.sum()}")

            # 3. 形态学操作：开运算去除噪声
            kernel_size = 2
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
                contour_area = cv2.contourArea(contour)
                if contour_area >= min_contour_area:
                    # 计算轮廓中心
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        center_x = int(M["m10"] / M["m00"])
                        center_y = int(M["m01"] / M["m00"])
                    else:
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
                        'contour': contour,
                        'contour_mask': contour_mask,
                        'perimeter': perimeter,
                        'compactness': compactness,
                        'method': 'contour_tracing'
                    }
                    filtered_regions.append(region_info)

                    print(f"   区域 {i+1}: 中心({center_x}, {center_y}), 面积{contour_area:.1f}, 周长{perimeter:.1f}, 紧凑度{compactness:.3f}")

            # 7. 按面积排序，选择最大的区域
            if filtered_regions:
                filtered_regions.sort(key=lambda x: x['area'], reverse=True)
                largest_region = filtered_regions[0]
                print("✅ 轮廓跟踪压力区域识别完成，选择面积最大的区域")
                print(f"   最大区域: ID={largest_region['id']}, 面积={largest_region['area']:.1f}, 紧凑度={largest_region['compactness']:.3f}")
                return [largest_region]
            else:
                print("⚠️ 未识别出有效的压力区域")
                return []

        except Exception as e:
            print(f"❌ 轮廓跟踪压力区域识别失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def identify_calibrated_regions(self, calibrated_data, threshold_percentile=80):
        """在校准后的数据上识别高响应区域，基于压力强度进行区域选取"""
        try:
            # 智能调整阈值百分位数，优化区域识别效果
            data_std = calibrated_data.std()
            data_range = calibrated_data.max() - calibrated_data.min()

            # 根据数据特性动态调整阈值
            if data_std > data_range * 0.2:
                adjusted_threshold = min(threshold_percentile, 85)
                print(f"🔧 数据变化较大，调整阈值: {threshold_percentile}% → {adjusted_threshold}%")
            else:
                adjusted_threshold = min(threshold_percentile, 75)
                print(f"🔧 数据变化较小，调整阈值: {threshold_percentile}% → {adjusted_threshold}%")

            print(f"   数据标准差: {data_std:.2f}, 数据范围: {data_range:.2f}")
            print(f"   最终使用阈值: {adjusted_threshold}%")
            max_regions = self.dialog.region_count_slider.value()

            # 获取区域识别结果
            regions = self.dialog.region_detector.identify_calibrated_regions(
                calibrated_data,
                adjusted_threshold,
                max_regions
            )

            # 区域质量评估和优化
            if regions:
                print("🔍 区域质量评估:")
                for i, region in enumerate(regions):
                    area = region.get('area', 0)
                    compactness = region.get('compactness', 0.0)

                    # 评估区域质量
                    if area > 200:
                        print(f"   ⚠️ 区域 {i+1}: 面积过大 ({area}像素)，建议降低阈值")
                    if compactness < 0.3:
                        print(f"   ⚠️ 区域 {i+1}: 紧凑度过低 ({compactness:.3f})，形状不规则")
                    if area < 10:
                        print(f"   ⚠️ 区域 {i+1}: 面积过小 ({area}像素)，可能是噪声")

                    # 质量评分
                    quality_score = min(1.0, (compactness * 0.4 + min(area, 100)/100 * 0.3 + (1.0 - max(area, 100)/500) * 0.3))
                    print(f"   📊 区域 {i+1} 质量评分: {quality_score:.3f}")

            return regions

        except Exception as e:
            print(f"❌ 识别校准区域失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def analyze_regions_pressure(self, pressure_data, calibrated_regions):
        """分析识别出的区域的压力值"""
        try:
            print("📊 开始分析识别区域的压力值...")

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

                print(f"   区域 {region['id']}: 平均压强 {region_pressure_info['avg_pressure']:.2f} kPa, "
                      f"范围 [{region_pressure_info['min_pressure']:.2f} kPa, {region_pressure_info['max_pressure']:.2f} kPa]")

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

                print(f"✅ 区域压强分析完成，{len(region_pressures)} 个区域")
                print(f"   整体平均压强: {overall_stats['avg_pressure']:.2f} kPa")
                print(f"   压强范围: [{overall_stats['min_pressure']:.2f} kPa, {overall_stats['max_pressure']:.2f} kPa]")
                return overall_stats
            else:
                print("⚠️ 没有区域可分析")
                return None

        except Exception as e:
            print(f"❌ 区域压力分析失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def manual_identify_regions(self):
        """手动重新识别校准区域"""
        try:
            if hasattr(self.dialog, 'new_canvas'):
                print("🔍 手动重新识别校准区域...")

                # 获取当前阈值
                threshold_percentile = self.dialog.threshold_slider.value()

                # 获取最新的校准数据
                raw_data = self.dialog.parent.calibration_handler._get_current_frame_data()
                calibration_results = self.dialog.parent.calibration_manager.apply_new_calibration(raw_data)

                if 'new' in calibration_results:
                    new_data = calibration_results['new']['data']

                    # 优先使用变化量数据进行区域检测
                    data_for_detection = None
                    detection_method = ""

                    if hasattr(self.dialog, 'baseline_calibrated_data') and self.dialog.baseline_calibrated_data is not None:
                        try:
                            # 优先使用未去皮数据计算变化量
                            if 'untared_data' in calibration_results['new']:
                                current_untared = calibration_results['new']['untared_data']
                                change_data = current_untared - self.dialog.baseline_calibrated_data
                                data_for_detection = change_data
                                detection_method = "未去皮变化量数据"
                                print("🔧 手动识别：使用未去皮变化量数据进行区域检测")
                            else:
                                change_data = new_data - self.dialog.baseline_calibrated_data
                                data_for_detection = change_data
                                detection_method = "去皮后变化量数据"
                                print("🔧 手动识别：使用去皮后变化量数据进行区域检测")
                        except Exception as e:
                            print(f"⚠️ 计算变化量失败，使用校准数据: {e}")
                            data_for_detection = new_data
                            detection_method = "校准数据"
                    else:
                        print("⚠️ 未设置基准数据，使用校准数据进行区域检测")
                        data_for_detection = new_data
                        detection_method = "校准数据"

                    # 重新识别区域
                    calibrated_regions = self.identify_calibrated_regions(data_for_detection, threshold_percentile)

                    # 更新校准热力图上的区域标记
                    if calibrated_regions:
                        new_fig = self.dialog.new_canvas.figure
                        new_ax = new_fig.axes[0]
                        self.dialog.draw_calibrated_regions_on_heatmap(new_ax, calibrated_regions, color='red', linewidth=3)
                        new_fig.canvas.draw()

                        # 显示识别结果
                        QtWidgets.QMessageBox.information(
                            self.dialog,
                            "区域识别完成",
                            f"成功识别出校准区域！\n"
                            f"检测方法: {detection_method}\n"
                            f"识别策略: 基于压力强度排序（优先识别按压强度最高的区域）\n"
                            f"用户配置区域数量: {self.dialog.region_count_slider.value()}个\n"
                            f"实际检测到区域: {len(calibrated_regions)}个\n"
                            f"阈值: {threshold_percentile}%\n"
                            f"区域已用不同颜色标记。\n\n"
                            f"💡 提示：系统现在会优先识别压力值最高的区域，"
                            f"而不是面积最大的区域，这样能更准确地找到实际的按压位置。"
                        )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self.dialog,
                            "识别失败",
                            f"未识别出有效的校准区域。\n"
                            f"检测方法: {detection_method}\n"
                            f"当前阈值: {threshold_percentile}%\n"
                            f"请尝试降低阈值或检查数据。"
                        )
                else:
                    QtWidgets.QMessageBox.warning(self.dialog, "提示", "无法获取校准数据。")
            else:
                QtWidgets.QMessageBox.warning(self.dialog, "提示", "请先启动监控功能获取校准数据。")

        except Exception as e:
            print(f"❌ 手动识别校准区域失败: {e}")
            QtWidgets.QMessageBox.critical(self.dialog, "错误", f"手动识别失败:\n{str(e)}")

    def draw_calibrated_regions_on_heatmap(self, ax, regions, color='red', linewidth=3):
        """在校准热力图上绘制识别出的区域（使用轮廓跟踪）"""
        self.dialog.region_renderer.draw_calibrated_regions_on_heatmap(ax, regions, color, linewidth)

    def _analyze_negative_responses(self, region, contour_mask, results, negative_responses):
        """详细分析负响应值的原因"""
        try:
            print("\n🔍 开始分析负响应值原因...")
            print("📊 负响应值统计:")
            print(f"      数量: {len(negative_responses)}")
            print(f"      范围: [{negative_responses.min():.2f}, {negative_responses.max():.2f}]")
            print(f"      均值: {negative_responses.mean():.2f}")
            # 1. 分析原始传感器数据
            if 'raw' in results and 'data' in results['raw']:
                raw_data = results['raw']['data']
                region_raw_values = raw_data[contour_mask == 1]

                # 找到负响应值对应的原始数据
                negative_mask = region_raw_values < 0
                if np.any(negative_mask):
                    negative_raw_values = region_raw_values[negative_mask]
                    print("\n   📡 原始传感器数据分析:")
                    print(f"      负响应值对应的原始值范围: [{negative_raw_values.min():.2f}, {negative_raw_values.max():.2f}]")
                    print(f"      负响应值对应的原始值均值: {negative_raw_values.mean():.2f}")
                    print(f"      整个区域的原始值范围: [{region_raw_values.min():.2f}, {region_raw_values.max():.2f}]")
                    print(f"      整个区域的原始值均值: {region_raw_values.mean():.2f}")
                    # 检查原始值是否也为负
                    negative_original_count = np.sum(negative_raw_values < 0)
                    if negative_original_count > 0:
                        print(f"      ⚠️ 发现 {negative_original_count} 个原始值也为负!")
                    else:
                        print("      ✅ 原始值都为正，负值来自校准过程")

            # 2. 分析去皮前的校准数据
            if 'new' in results and 'untared_data' in results['new']:
                untared_data = results['new']['untared_data']
                region_untared_values = untared_data[contour_mask == 1]

                # 找到负响应值对应的去皮前数据
                negative_mask = results['new']['data'][contour_mask == 1] < 0
                if np.any(negative_mask):
                    negative_untared_values = region_untared_values[negative_mask]

                    print("\n   🔧 去皮前校准数据分析:")
                    print(f"      负响应值对应的去皮前值范围: [{negative_untared_values.min():.2f}, {negative_untared_values.max():.2f}]")
                    print(f"      负响应值对应的去皮前值均值: {negative_untared_values.mean():.2f}")
                    print(f"      整个区域的去皮前值范围: [{region_untared_values.min():.2f}, {region_untared_values.max():.2f}]")
                    print(f"      整个区域的去皮前值均值: {region_untared_values.mean():.2f}")
                    # 检查去皮前是否已有负值
                    negative_untared_count = np.sum(negative_untared_values < 0)
                    if negative_untared_count > 0:
                        print(f"      ⚠️ 去皮前已有 {negative_untared_count} 个负值!")
                        print("      🔍 负值来自AI校准函数，需要检查校准模型")
                    else:
                        print("      ✅ 去皮前都为正，负值来自去皮操作")

            # 3. 分析去皮基准
            if hasattr(self.dialog, 'parent') and hasattr(self.dialog.parent, 'calibration_manager'):
                calibration_manager = self.dialog.parent.calibration_manager
                if hasattr(calibration_manager, 'new_calibrator'):
                    new_calibrator = calibration_manager.new_calibrator

                    print("\n   🎯 去皮基准分析:")
                    if hasattr(new_calibrator, 'get_baseline'):
                        try:
                            baseline = new_calibrator.get_baseline()
                            print(f"      去皮基准值: {baseline:.2f}")
                            # 计算去皮前后的差异
                            if 'untared_data' in results.get('new', {}):
                                untared_data = results['new']['untared_data']
                                region_untared_values = untared_data[contour_mask == 1]

                                # 找到负响应值对应的去皮前值
                                negative_mask = results['new']['data'][contour_mask == 1] < 0
                                if np.any(negative_mask):
                                    negative_untared_values = region_untared_values[negative_mask]
                                    print(f"      负响应值对应的去皮前值: {negative_untared_values}")
                                    print(f"      去皮操作: {negative_untared_values} - {baseline} = {negative_untared_values - baseline}")
                                    # 判断去皮基准是否合理
                                    if np.any(negative_untared_values < baseline):
                                        print("      ⚠️ 去皮基准过高！部分值去皮后变为负")
                                    else:
                                        print("      ✅ 去皮基准合理")
                        except Exception as e:
                            print(f"      ❌ 获取去皮基准失败: {e}")
                    else:
                        print("      ⚠️ 校准器没有get_baseline方法")
                else:
                    print("      ⚠️ 无法访问新版本校准器")

            # 4. 总结分析结果
            print("\n   📋 负响应值原因总结:")
            if 'new' in results and 'untared_data' in results['new']:
                untared_data = results['new']['untared_data']
                region_untared_values = untared_data[contour_mask == 1]
                negative_mask = results['new']['data'][contour_mask == 1] < 0
                if np.any(negative_mask):
                    negative_untared_values = region_untared_values[negative_mask]

                    if np.any(negative_untared_values < 0):
                        print("      🎯 主要原因: AI校准函数产生了负值")
                        print("      💡 建议: 检查校准模型的输出范围，确保非负输出")
                    else:
                        print("      🎯 主要原因: 去皮基准设置过高")
                        print("      💡 建议: 降低去皮基准，或使用动态基准")
            else:
                print("      🎯 主要原因: 无法确定（缺少去皮前数据）")
                print("      💡 建议: 检查数据流程，确保去皮前后数据可用")

        except Exception as e:
            print(f"   ❌ 负响应值分析失败: {e}")
            import traceback
            traceback.print_exc()