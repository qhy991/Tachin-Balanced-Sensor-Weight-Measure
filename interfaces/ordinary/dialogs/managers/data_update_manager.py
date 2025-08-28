#!/usr/bin/env python3
"""
数据更新管理器

负责处理双校准比较对话框的数据更新逻辑
"""

import numpy as np
import cv2
from PyQt5 import QtWidgets


class DataUpdateManager:
    """数据更新管理器"""

    def __init__(self, dialog):
        self.dialog = dialog
        self._update_count = 0
        self._last_raw_data = None
        self._zero_data_count = 0
        self._no_change_count = 0

    def update_comparison(self):
        """更新比较数据"""
        try:
            # 获取当前数据
            raw_data = self._get_current_raw_data()

            # 检查数据变化
            if not self._should_update_data(raw_data):
                return

            self._last_raw_data = raw_data.copy()

            # 应用双校准器
            calibration_results = self._apply_dual_calibration(raw_data)

            if calibration_results is None:
                print("⚠️ 双校准器应用失败，跳过更新")
                return

            self._update_count += 1
            print(f"🔄 更新双校准器比较数据 #{self._update_count}")

            # 更新热力图
            self.update_heatmaps(calibration_results)

            # 更新统计信息
            self.dialog.update_statistics(calibration_results)

            # 更新比较结果
            self.dialog.update_comparison_results(calibration_results)

        except Exception as e:
            print(f"❌ 更新双校准器比较失败: {e}")
            import traceback
            traceback.print_exc()

    def _get_current_raw_data(self):
        """获取当前原始数据"""
        if hasattr(self.dialog.parent, 'calibration_handler'):
            return self.dialog.parent.calibration_handler._get_current_frame_data()
        else:
            return self.dialog.parent.get_current_frame_data()

    def _should_update_data(self, raw_data):
        """判断是否应该更新数据"""
        if self._last_raw_data is None:
            print("🔄 首次运行，初始化数据")
            return True

        # 检查数据是否全为零
        if np.all(raw_data == 0):
            print("⚠️ 检测到原始数据全为零，可能传感器未连接或数据采集异常")
            self._zero_data_count += 1

            # 每5次零数据时强制更新一次
            if self._zero_data_count % 5 != 0:
                return False
            else:
                print(f"📊 数据为零，强制更新校准结果 #{self._update_count + 1}")
                return True

        # 检查数据是否有变化
        data_diff = np.abs(raw_data - self._last_raw_data)
        max_diff = np.max(data_diff)

        # 如果绝对变化小于阈值，认为数据基本不变
        if max_diff < 1.0:
            self._no_change_count += 1

            # 每8次无变化时强制更新一次
            if self._no_change_count % 8 != 0:
                return False
            else:
                print(f"📊 数据变化很小，强制更新校准结果 #{self._update_count + 1}")
                return True
        else:
            # 数据有变化，重置计数器
            self._no_change_count = 0
            self._zero_data_count = 0
            print(f"🔄 检测到数据变化，最大变化: {max_diff:.4f}")
            return True

    def _apply_dual_calibration(self, raw_data):
        """应用双校准器"""
        if hasattr(self.dialog.parent, 'calibration_manager'):
            return self.dialog.parent.calibration_manager.apply_dual_calibration(raw_data)
        else:
            return self.dialog.parent.apply_dual_calibration(raw_data)

    def update_heatmaps(self, results):
        """更新热力图"""
        try:
            print(f"🔄 更新双校准器比较数据 #{self._update_count}")

            # 检查是否有必要的数据
            if 'raw' not in results:
                print("⚠️ 没有原始数据，跳过热力图更新")
                return

            # 第一步：更新原始数据热力图
            if 'raw' in results and hasattr(self.dialog, 'raw_canvas'):
                raw_data = results['raw']['data']
                self.dialog.update_single_heatmap(self.dialog.raw_canvas, raw_data)
                print(f"✅ 原始数据热力图更新完成，数据范围: [{raw_data.min():.2f}, {raw_data.max():.2f}]")

            # 第二步：更新新版本校准热力图
            if 'new' in results and hasattr(self.dialog, 'new_canvas'):
                new_data = results['new']['data']
                self.dialog.update_single_heatmap(self.dialog.new_canvas, new_data)
                print(f"✅ 新版本校准热力图更新完成，数据范围: [{new_data.min():.2f}, {new_data.max():.2f}]")

                # 更新变化量数据热力图
                change_data = self._calculate_change_data(results, new_data)
                if change_data is not None:
                    self._update_change_data_heatmap(change_data, results)

                # 识别校准区域
                calibrated_regions = self._identify_calibrated_regions(results, new_data, change_data)
                if calibrated_regions:
                    self._handle_calibrated_regions(calibrated_regions, results)

            # 第四步：负值响应检测和可视化
            if hasattr(self.dialog, 'negative_response_canvas') and 'new' in results:
                self._update_negative_response_heatmap(results)

            # 第五步：将校准区域应用到所有热力图
            calibrated_regions = results.get('calibrated_regions', {}).get('regions', [])
            if calibrated_regions:
                self.dialog._apply_regions_to_all_heatmaps(calibrated_regions, results)

        except Exception as e:
            print(f"❌ 更新热力图失败: {e}")
            import traceback
            traceback.print_exc()

    def _calculate_change_data(self, results, new_data):
        """计算变化量数据"""
        if not hasattr(self.dialog, 'baseline_calibrated_data') or self.dialog.baseline_calibrated_data is None:
            return None

        try:
            # 获取当前去皮后的校准数据
            current_raw = self._get_current_raw_data()
            current_calibration_results = self.dialog.parent.calibration_manager.apply_dual_calibration(current_raw)

            if 'new' in current_calibration_results and 'data' in current_calibration_results['new']:
                current_calibrated_data = current_calibration_results['new']['data']
                change_data = current_calibrated_data - self.dialog.baseline_calibrated_data

                print(f"   🔧 变化量计算详情:")
                print(f"     基准数据范围: [{self.dialog.baseline_calibrated_data.min():.2f}, {self.dialog.baseline_calibrated_data.max():.2f}]")
                print(f"     当前数据范围: [{current_calibrated_data.min():.2f}, {current_calibrated_data.max():.2f}]")
                print(f"     变化量范围: [{change_data.min():.2f}, {change_data.max():.2f}]")
                print(f"     变化量均值: {change_data.mean():.2f}")

                return change_data
            else:
                print("   ❌ 无法获取当前校准数据，无法计算变化量")
                return None

        except Exception as e:
            print(f"⚠️ 计算变化量失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _update_change_data_heatmap(self, change_data, results):
        """更新变化量数据热力图"""
        try:
            if hasattr(self.dialog, 'change_data_canvas'):
                self.dialog.update_single_heatmap(self.dialog.change_data_canvas, change_data)

                # 将变化量数据添加到results中
                if 'change_data' not in results:
                    results['change_data'] = {}
                results['change_data']['data'] = change_data

                print(f"✅ 变化量数据热力图更新完成:")
                print(f"   变化量范围: [{change_data.min():.2f}, {change_data.max():.2f}]")
                print(f"   变化量均值: {change_data.mean():.2f}")

        except Exception as e:
            print(f"⚠️ 更新变化量数据热力图失败: {e}")
            import traceback
            traceback.print_exc()

    def _identify_calibrated_regions(self, results, new_data, change_data):
        """识别校准区域"""
        try:
            print("🔍 开始识别校准区域...")
            threshold_percentile = self.dialog.threshold_slider.value()

            # 优先使用变化量数据进行区域检测
            if change_data is not None:
                print("   🎯 使用变化量数据进行区域检测")
                data_for_detection = change_data
                detection_method = "变化量数据"
            else:
                print("   ⚠️ 变化量数据不可用，使用校准数据进行区域检测")
                data_for_detection = new_data
                detection_method = "校准数据"

            calibrated_regions = self.dialog.identify_calibrated_regions(data_for_detection, threshold_percentile)

            if calibrated_regions:
                print(f"✅ 识别到 {len(calibrated_regions)} 个校准区域（基于{detection_method}）")
                # 更新区域数量显示
                if hasattr(self.dialog, 'region_count_label'):
                    self.dialog.region_count_label.setText(f"主区域: {len(calibrated_regions)}")
                    self.dialog.region_count_label.setStyleSheet("color: #27ae60; font-weight: bold; min-width: 60px;")

                # 将区域信息添加到results中
                if 'calibrated_regions' not in results:
                    results['calibrated_regions'] = {}
                results['calibrated_regions']['regions'] = calibrated_regions

                return calibrated_regions
            else:
                print("⚠️ 未识别到校准区域")
                # 更新区域数量显示
                if hasattr(self.dialog, 'region_count_label'):
                    self.dialog.region_count_label.setText("主区域: 0")
                    self.dialog.region_count_label.setStyleSheet("color: #e74c3c; font-weight: bold; min-width: 60px;")

                return []

        except Exception as e:
            print(f"⚠️ 区域识别失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _handle_calibrated_regions(self, calibrated_regions, results):
        """处理识别到的校准区域"""
        try:
            # 在校准热力图上绘制区域
            new_fig = self.dialog.new_canvas.figure
            new_ax = new_fig.axes[0]
            self.dialog.draw_calibrated_regions_on_heatmap(new_ax, calibrated_regions, color='red', linewidth=3)
            new_fig.canvas.draw()

            # 更新区域统计标签
            self.dialog._update_region_stats_labels(calibrated_regions, results)

            print("✅ 校准区域绘制完成")

        except Exception as e:
            print(f"⚠️ 处理校准区域失败: {e}")
            import traceback
            traceback.print_exc()

    def _update_negative_response_heatmap(self, results):
        """更新负值响应热力图"""
        try:
            calibrated_data = results['new']['data']
            negative_mask = calibrated_data < 0
            negative_count = np.sum(negative_mask)

            # 创建负值响应热力图数据
            negative_response_data = np.zeros_like(calibrated_data)
            negative_response_data[negative_mask] = calibrated_data[negative_mask]

            # 更新负值响应热力图
            self.dialog.update_single_heatmap(self.dialog.negative_response_canvas, negative_response_data)

            # 清除之前的标记
            ax = self.dialog.negative_response_canvas.figure.axes[0]
            self.dialog._clear_negative_response_markers(ax)

            # 保存负值响应信息到results
            if 'negative_response' not in results:
                results['negative_response'] = {}

            if negative_count > 0:
                negative_values = calibrated_data[negative_mask]
                negative_coords = np.where(negative_mask)

                results['negative_response'].update({
                    'has_negative': True,
                    'count': int(negative_count),
                    'data': negative_response_data.copy(),
                    'values': negative_values.tolist(),
                    'coordinates': list(zip(negative_coords[0], negative_coords[1])),
                    'min_value': float(negative_values.min()),
                    'max_value': float(negative_values.max()),
                    'mean_value': float(negative_values.mean()),
                    'std_value': float(negative_values.std())
                })

                # 在负值响应热力图上标记负值点
                self.dialog.draw_negative_response_points(ax,
                                                        negative_coords[0], negative_coords[1],
                                                        calibrated_data[negative_mask])

                print(f"🔴 检测到 {negative_count} 个负值响应点!")
                print(f"   负值范围: [{negative_values.min():.2f}, {negative_values.max():.2f}]")
                print(f"   负值均值: {negative_values.mean():.2f}")

                # 打印负值响应点的坐标
                print(f"🔍 准备打印坐标信息...")
                self._print_negative_response_coordinates(negative_coords, negative_values)
            else:
                results['negative_response'].update({
                    'has_negative': False,
                    'count': 0,
                    'data': negative_response_data.copy()
                })
                print("✅ 未检测到负值响应点")

            # 更新画布
            self.dialog.negative_response_canvas.figure.canvas.draw()

        except Exception as e:
            print(f"⚠️ 负值响应检测失败: {e}")
            import traceback
            traceback.print_exc()

    def _print_negative_response_coordinates(self, negative_coords, negative_values):
        """打印负值响应点的坐标信息"""
        print(f"🔧 开始执行坐标打印方法...")
        print(f"   negative_coords 类型: {type(negative_coords)}")
        print(f"   negative_values 类型: {type(negative_values)}")
        print(f"   negative_coords 长度: {len(negative_coords) if hasattr(negative_coords, '__len__') else 'N/A'}")
        print(f"   negative_values 长度: {len(negative_values) if hasattr(negative_values, '__len__') else 'N/A'}")

        try:
            print(f"🔧 进入坐标打印方法...")
            rows, cols = negative_coords
            print(f"   解包后 - rows 长度: {len(rows)}, cols 长度: {len(cols)}")

            coords_and_values = list(zip(rows, cols, negative_values))
            print(f"   组合后 - coords_and_values 长度: {len(coords_and_values)}")

            print(f"\n📍 负值响应点坐标详情:")
            print(f"   总计 {len(coords_and_values)} 个负值点")

            # 简化版本：只打印前5个点
            print(f"   📊 所有负值响应点:")
            for i in range( len(coords_and_values)):
                row, col, value = coords_and_values[i]
                print(f"      {i+1}. 坐标({row}, {col}) 值: {value:.3f}")

            print("✅ 坐标打印方法执行完成")

        except Exception as e:
            print(f"⚠️ 打印负值响应点坐标失败: {e}")
            print(f"   错误类型: {type(e).__name__}")
            import traceback
            print(f"   完整错误信息:")
            traceback.print_exc()
