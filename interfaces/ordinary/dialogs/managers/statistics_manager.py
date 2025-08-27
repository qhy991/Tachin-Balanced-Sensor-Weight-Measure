#!/usr/bin/env python3
"""
统计信息管理类

负责所有统计数据的计算和显示
"""

import numpy as np
import traceback


class StatisticsManager:
    """统计信息管理器"""
    
    def __init__(self):
        self.raw_labels = {}
        self.new_labels = {}
        self.change_data_labels = {}  # 🆕 新增：变化量标签
        self.region_calibration_labels = {} # 🆕 新增：区域校准值标签
        
        # 🆕 新增：压强热力图统计标签
        self.pressure_heatmap_labels = {}
    
    def setup_raw_labels(self, labels_dict):
        """设置原始数据标签"""
        self.raw_labels = labels_dict
    
    def setup_new_labels(self, labels_dict):
        """设置新版本校准标签"""
        self.new_labels = labels_dict
    
    def setup_change_data_labels(self, labels_dict):
        """设置变化量数据标签"""
        self.change_data_labels = labels_dict
    
    def setup_region_calibration_labels(self, labels_dict):
        """设置区域校准值标签"""
        self.region_calibration_labels = labels_dict
    
    def setup_pressure_heatmap_labels(self, labels_dict):
        """设置压强热力图统计标签"""
        self.pressure_heatmap_labels = labels_dict
    
    def update_raw_statistics(self, results):
        """更新原始数据统计"""
        try:
            if 'raw' not in results:
                print("⚠️ 没有原始数据，跳过原始数据统计更新")
                self._clear_raw_labels()
                return
            
            raw_data = results['raw']['data']
            raw_mean = results['raw']['mean']
            raw_std = results['raw']['std']
            raw_min = results['raw']['min']
            raw_max = results['raw']['max']
            raw_range = results['raw']['range']
            
            # 检查去皮状态并显示
            taring_applied = results['raw'].get('taring_applied', False)
            if taring_applied:
                # 去皮已应用，显示去皮后的数据
                self._update_raw_labels_with_taring(raw_mean, raw_std, raw_min, raw_max, raw_range)
                
                # 显示去皮效果信息
                if 'original_range' in results['raw']:
                    original_min, original_max = results['raw']['original_range']
                    print(f"✅ 去皮效果显示:")
                    print(f"   去皮前范围: [{original_min:.2f}, {original_max:.2f}]")
                    print(f"   去皮后范围: [{raw_min:.2f}, {raw_max:.2f}]")
                    print(f"   去皮效果: 数据已归零")
            else:
                # 去皮未应用，显示原始数据
                self._update_raw_labels_without_taring(raw_mean, raw_std, raw_min, raw_max, raw_range)
            
            print(f"✅ 原始数据统计更新完成，去皮状态: {'已应用' if taring_applied else '未应用'}")
            
        except Exception as e:
            print(f"❌ 更新原始数据统计失败: {e}")
            traceback.print_exc()
    
    def update_new_statistics(self, results):
        """更新新版本校准统计"""
        try:
            if 'new' not in results:
                print("⚠️ 没有新版本校准数据，跳过新版本校准统计更新")
                return
            
            new_data = results['new']['data']
            new_mean = results['new']['mean']
            new_std = results['new']['std']
            new_min = results['new']['min']
            new_max = results['new']['max']
            new_range = results['new']['range']
            
            # 检查是否基于去皮后的数据
            if 'raw' in results and results['raw'].get('taring_applied', False):
                self._update_new_labels_with_taring(new_mean, new_std, new_min, new_max, new_range)
            else:
                self._update_new_labels_without_taring(new_mean, new_std, new_min, new_max, new_range)
            
            print(f"✅ 新版本校准统计更新完成")
            
        except Exception as e:
            print(f"❌ 更新新版本校准统计失败: {e}")
            traceback.print_exc()
    
    def _clear_raw_labels(self):
        """清空原始数据标签"""
        for label in self.raw_labels.values():
            if hasattr(label, 'setText'):
                label.setText("均值: 无数据")
    
    def _update_raw_labels_with_taring(self, mean, std, min_val, max_val, range_val):
        """更新去皮后的原始数据标签"""
        if 'mean' in self.raw_labels:
            self.raw_labels['mean'].setText(f"均值: {mean:.2f} (已去皮)")
        if 'std' in self.raw_labels:
            self.raw_labels['std'].setText(f"标准差: {std:.2f} (已去皮)")
        if 'min' in self.raw_labels:
            self.raw_labels['min'].setText(f"最小值: {min_val:.2f} (已去皮)")
        if 'max' in self.raw_labels:
            self.raw_labels['max'].setText(f"最大值: {max_val:.2f} (已去皮)")
        if 'range' in self.raw_labels:
            self.raw_labels['range'].setText(f"范围: {range_val:.2f} (已去皮)")
    
    def _update_raw_labels_without_taring(self, mean, std, min_val, max_val, range_val):
        """更新去皮前的原始数据标签"""
        if 'mean' in self.raw_labels:
            self.raw_labels['mean'].setText(f"均值: {mean:.2f}")
        if 'std' in self.raw_labels:
            self.raw_labels['std'].setText(f"标准差: {std:.2f}")
        if 'min' in self.raw_labels:
            self.raw_labels['min'].setText(f"最小值: {min_val:.2f}")
        if 'max' in self.raw_labels:
            self.raw_labels['max'].setText(f"最大值: {max_val:.2f}")
        if 'range' in self.raw_labels:
            self.raw_labels['range'].setText(f"范围: {range_val:.2f}")
    
    def _update_new_labels_with_taring(self, mean, std, min_val, max_val, range_val):
        """更新基于去皮数据的新版本校准标签"""
        if 'mean' in self.new_labels:
            self.new_labels['mean'].setText(f"均值: {mean:.2f} (基于去皮数据)")
        if 'std' in self.new_labels:
            self.new_labels['std'].setText(f"标准差: {std:.2f} (基于去皮数据)")
        if 'min' in self.new_labels:
            self.new_labels['min'].setText(f"最小值: {min_val:.2f} (基于去皮数据)")
        if 'max' in self.new_labels:
            self.new_labels['max'].setText(f"最大值: {max_val:.2f} (基于去皮数据)")
        if 'range' in self.new_labels:
            self.new_labels['range'].setText(f"范围: {range_val:.2f} (基于去皮数据)")
    
    def _update_new_labels_without_taring(self, mean, std, min_val, max_val, range_val):
        """更新基于原始数据的新版本校准标签"""
        if 'mean' in self.new_labels:
            self.new_labels['mean'].setText(f"均值: {mean:.2f}")
        if 'std' in self.new_labels:
            self.new_labels['std'].setText(f"标准差: {std:.2f}")
        if 'min' in self.new_labels:
            self.new_labels['min'].setText(f"最小值: {min_val:.2f}")
        if 'max' in self.new_labels:
            self.new_labels['max'].setText(f"最大值: {max_val:.2f}")
        if 'range' in self.new_labels:
            self.new_labels['range'].setText(f"范围: {range_val:.2f}")
    
    def update_change_data_statistics(self, results):
        """更新变化量数据统计"""
        try:
            if 'change_data' not in results or 'data' not in results['change_data']:
                print("⚠️ 没有变化量数据，跳过变化量统计更新")
                self._clear_change_data_labels()
                return
            
            change_data = results['change_data']['data']
            
            # 计算变化量统计信息
            change_mean = float(change_data.mean())
            change_std = float(change_data.std())
            change_min = float(change_data.min())
            change_max = float(change_data.max())
            change_range = float(change_data.max() - change_data.min())
            
            # 更新变化量标签
            self._update_change_data_labels(change_mean, change_std, change_min, change_max, change_range)
            
            print(f"✅ 变化量数据统计更新完成:")
            print(f"   变化量范围: [{change_min:.2f}, {change_max:.2f}]")
            print(f"   变化量均值: {change_mean:.2f}")
            print(f"   变化量标准差: {change_std:.2f}")
            
        except Exception as e:
            print(f"❌ 更新变化量数据统计失败: {e}")
            traceback.print_exc()
    
    def update_region_calibration_statistics(self, results):
        """更新选中区域的新版本校准统计"""
        try:
            if 'region_calibration' not in results or 'data' not in results['region_calibration']:
                print("⚠️ 没有区域校准值数据，跳过区域校准值统计更新")
                self._clear_region_calibration_labels()
                return
            
            region_calibration_data = results['region_calibration']['data']
            data_source = results['region_calibration'].get('source', 'unknown')
            
            print(f"✅ 开始更新选中区域的新版本校准统计...")
            print(f"   数据来源: {data_source}")
            
            # 计算区域校准值统计信息
            region_mean = float(region_calibration_data.mean())
            region_std = float(region_calibration_data.std())
            region_min = float(region_calibration_data.min())
            region_max = float(region_calibration_data.max())
            region_range = float(region_max - region_min)
            region_sum = float(region_calibration_data.sum())
            
            # 更新区域校准值标签
            self._update_region_calibration_labels(region_mean, region_std, region_min, region_max, region_range, region_sum)
            
            print(f"✅ 选中区域的新版本校准统计更新完成:")
            print(f"   数据来源: {data_source}")
            print(f"   区域校准值范围: [{region_min:.2f}, {region_max:.2f}]")
            print(f"   区域校准值均值: {region_mean:.2f}")
            print(f"   区域校准值标准差: {region_std:.2f}")
            print(f"   区域校准值总和: {region_sum:.2f}")
            
        except Exception as e:
            print(f"❌ 更新选中区域的新版本校准统计失败: {e}")
            traceback.print_exc()
    
    def _update_change_data_labels(self, mean, std, min_val, max_val, range_val):
        """更新变化量数据标签"""
        if 'mean' in self.change_data_labels:
            self.change_data_labels['mean'].setText(f"均值: {mean:.2f}")
        if 'std' in self.change_data_labels:
            self.change_data_labels['std'].setText(f"标准差: {std:.2f}")
        if 'min' in self.change_data_labels:
            self.change_data_labels['min'].setText(f"最小值: {min_val:.2f}")
        if 'max' in self.change_data_labels:
            self.change_data_labels['max'].setText(f"最大值: {max_val:.2f}")
        if 'range' in self.change_data_labels:
            self.change_data_labels['range'].setText(f"范围: {range_val:.2f}")
    
    def _update_region_calibration_labels(self, mean, std, min_val, max_val, range_val, sum_val):
        """更新区域校准值数据标签"""
        if 'mean' in self.region_calibration_labels:
            self.region_calibration_labels['mean'].setText(f"均值: {mean:.2f}")
        if 'std' in self.region_calibration_labels:
            self.region_calibration_labels['std'].setText(f"标准差: {std:.2f}")
        if 'min' in self.region_calibration_labels:
            self.region_calibration_labels['min'].setText(f"最小值: {min_val:.2f}")
        if 'max' in self.region_calibration_labels:
            self.region_calibration_labels['max'].setText(f"最大值: {max_val:.2f}")
        if 'range' in self.region_calibration_labels:
            self.region_calibration_labels['range'].setText(f"范围: {range_val:.2f}")
        if 'sum' in self.region_calibration_labels:
            self.region_calibration_labels['sum'].setText(f"总和: {sum_val:.2f}")
    
    def _clear_change_data_labels(self):
        """清空变化量数据标签"""
        if 'mean' in self.change_data_labels:
            self.change_data_labels['mean'].setText("均值: 等待数据...")
        if 'std' in self.change_data_labels:
            self.change_data_labels['std'].setText("标准差: 等待数据...")
        if 'min' in self.change_data_labels:
            self.change_data_labels['min'].setText("最小值: 等待数据...")
        if 'max' in self.change_data_labels:
            self.change_data_labels['max'].setText("最大值: 等待数据...")
        if 'range' in self.change_data_labels:
            self.change_data_labels['range'].setText("范围: 等待数据...")
    
    def _clear_region_calibration_labels(self):
        """清空区域校准值数据标签"""
        if 'mean' in self.region_calibration_labels:
            self.region_calibration_labels['mean'].setText("均值: 等待数据...")
        if 'std' in self.region_calibration_labels:
            self.region_calibration_labels['std'].setText("标准差: 等待数据...")
        if 'min' in self.region_calibration_labels:
            self.region_calibration_labels['min'].setText("最小值: 等待数据...")
        if 'max' in self.region_calibration_labels:
            self.region_calibration_labels['max'].setText("最大值: 等待数据...")
        if 'range' in self.region_calibration_labels:
            self.region_calibration_labels['range'].setText("范围: 等待数据...")
        if 'sum' in self.region_calibration_labels:
            self.region_calibration_labels['sum'].setText("总和: 等待数据...")
    
    def update_pressure_heatmap_statistics(self, results):
        """更新压强热力图统计"""
        try:
            if 'pressure_heatmap' not in results:
                print("⚠️ 没有压强热力图数据，跳过压强统计更新")
                self._clear_pressure_heatmap_labels()
                return
            
            pressure_data = results['pressure_heatmap']['data']
            pressure_stats = results['pressure_heatmap'].get('pressure_stats', {})
            
            print(f"🔧 更新压强热力图统计")
            
            # 从pressure_stats获取数据，如果没有则计算
            if pressure_stats:
                mean_pressure = pressure_stats.get('mean_pressure', 0.0)
                max_pressure = pressure_stats.get('max_pressure', 0.0)
                min_pressure = pressure_stats.get('min_pressure', 0.0)
                total_force = pressure_stats.get('total_force', 0.0)
                regions_count = pressure_stats.get('total_regions', 0)
            else:
                # 如果没有pressure_stats，从数据计算
                non_zero_data = pressure_data[pressure_data > 0]
                if len(non_zero_data) > 0:
                    mean_pressure = np.mean(non_zero_data)
                    max_pressure = np.max(non_zero_data)
                    min_pressure = np.min(non_zero_data)
                    total_force = np.sum(pressure_data)
                    regions_count = len(np.unique(pressure_data[pressure_data > 0]))
                else:
                    mean_pressure = max_pressure = min_pressure = total_force = 0.0
                    regions_count = 0
            
            # 更新标签
            self._update_pressure_heatmap_labels(mean_pressure, max_pressure, min_pressure, total_force, regions_count)
            
            print(f"✅ 压强热力图统计更新完成")
            
        except Exception as e:
            print(f"❌ 更新压强热力图统计失败: {e}")
            traceback.print_exc()
    
    def _update_pressure_heatmap_labels(self, mean_pressure, max_pressure, min_pressure, total_force, regions_count):
        """更新压强热力图统计标签"""
        try:
            if 'mean' in self.pressure_heatmap_labels:
                self.pressure_heatmap_labels['mean'].setText(f"平均压强: {mean_pressure:.2f} N")
            if 'max' in self.pressure_heatmap_labels:
                self.pressure_heatmap_labels['max'].setText(f"最大压强: {max_pressure:.2f} N")
            if 'min' in self.pressure_heatmap_labels:
                self.pressure_heatmap_labels['min'].setText(f"最小压强: {min_pressure:.2f} N")
            if 'total_force' in self.pressure_heatmap_labels:
                self.pressure_heatmap_labels['total_force'].setText(f"总力: {total_force:.2f} N")
            if 'regions' in self.pressure_heatmap_labels:
                self.pressure_heatmap_labels['regions'].setText(f"检测区域数: {regions_count}")
            
            print(f"🔧 压强标签更新: 平均={mean_pressure:.2f}N, 最大={max_pressure:.2f}N")
            
        except Exception as e:
            print(f"❌ 更新压强标签失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _clear_pressure_heatmap_labels(self):
        """清空压强热力图统计标签"""
        if 'mean' in self.pressure_heatmap_labels:
            self.pressure_heatmap_labels['mean'].setText("平均压强: 等待数据...")
        if 'max' in self.pressure_heatmap_labels:
            self.pressure_heatmap_labels['max'].setText("最大压强: 等待数据...")
        if 'min' in self.pressure_heatmap_labels:
            self.pressure_heatmap_labels['min'].setText("最小压强: 等待数据...")
        if 'total_force' in self.pressure_heatmap_labels:
            self.pressure_heatmap_labels['total_force'].setText("总力: 等待数据...")
        if 'regions' in self.pressure_heatmap_labels:
            self.pressure_heatmap_labels['regions'].setText("检测区域数: 等待数据...")
