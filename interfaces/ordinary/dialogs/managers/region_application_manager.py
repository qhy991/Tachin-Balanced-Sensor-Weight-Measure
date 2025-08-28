#!/usr/bin/env python3
"""
区域应用管理类

负责将识别出的区域应用到所有热力图上
"""

import numpy as np
import traceback


class RegionApplicationManager:
    """区域应用管理器"""
    
    def __init__(self, heatmap_manager, region_renderer, statistics_manager):
        self.heatmap_manager = heatmap_manager
        self.region_renderer = region_renderer
        self.statistics_manager = statistics_manager
    
    def apply_regions_to_all_heatmaps(self, calibrated_regions, results):
        """🎯 统一管理：将校准区域应用到所有相关热力图上"""
        try:
            if not calibrated_regions:
                print("⚠️ 没有校准区域可应用")
                return
            
            print(f"🎯 开始将校准区域应用到所有热力图...")
            print(f"   区域数量: {len(calibrated_regions)}")
            print(f"   区域详情:")
            for i, region in enumerate(calibrated_regions):
                print(f"     区域 {i+1}: ID={region.get('id', 'N/A')}, "
                      f"中心={region.get('center', 'N/A')}, "
                      f"面积={region.get('area', 'N/A')}")
                if 'contour' in region:
                    print(f"       轮廓: 存在, 形状={region['contour'].shape if region['contour'] is not None else 'None'}")
                if 'contour_mask' in region:
                    print(f"       轮廓掩码: 存在, 形状={region['contour_mask'].shape}")
                if 'bbox' in region:
                    print(f"       边界框: {region['bbox']}")
            
            # 1. 在校准热力图上绘制区域（红色标记）
            if hasattr(self, 'new_canvas'):
                print(f"   🎨 开始在校准热力图上绘制区域...")
                new_fig = self.new_canvas.figure
                new_ax = new_fig.axes[0]
                print(f"     校准热力图画布: {self.new_canvas}")
                print(f"     校准热力图轴: {new_ax}")
                
                try:
                    self.region_renderer.draw_calibrated_regions_on_heatmap(new_ax, calibrated_regions, color='red', linewidth=3)
                    print(f"   ✅ 校准热力图区域标记完成（红色）")
                except Exception as e:
                    print(f"   ❌ 校准热力图区域标记失败: {e}")
                    import traceback
                    traceback.print_exc()
                
                # 更新画布
                try:
                    new_fig.canvas.draw()
                    print(f"     ✅ 校准热力图画布更新完成")
                except Exception as e:
                    print(f"     ❌ 校准热力图画布更新失败: {e}")
            else:
                print(f"   ⚠️ 校准热力图画布不存在")
            
            # 🆕 新增：在变化量热力图上绘制区域（如果存在变化量数据）
            if hasattr(self, 'change_data_canvas'):
                print(f"   🎨 开始检查变化量热力图...")
                if 'change_data' in results and 'data' in results['change_data']:
                    change_data = results['change_data']['data']
                    print(f"     变化量数据形状: {change_data.shape}")
                    print(f"     变化量数据范围: [{change_data.min():.2f}, {change_data.max():.2f}]")
                    
                    # 在变化量热力图上绘制区域（紫色标记）
                    try:
                        change_fig = self.change_data_canvas.figure
                        change_ax = change_fig.axes[0]
                        print(f"     变化量热力图画布: {self.change_data_canvas}")
                        print(f"     变化量热力图轴: {change_ax}")
                        
                        self.region_renderer.draw_calibrated_regions_on_heatmap(change_ax, calibrated_regions, color='purple', linewidth=2)
                        print(f"   ✅ 变化量热力图区域标记完成（紫色）")
                        
                        # 更新变化量热力图画布
                        change_fig.canvas.draw()
                        print(f"     变化量热力图画布更新完成")
                        
                    except Exception as e:
                        print(f"   ❌ 变化量热力图区域标记失败: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"   ⚠️ 变化量数据不可用，跳过变化量热力图区域标记")
                    if 'change_data' not in results:
                        print(f"     原因: 没有变化量数据")
                    elif 'data' not in results['change_data']:
                        print(f"     原因: 变化量数据中没有data字段")
            else:
                print(f"   ⚠️ 变化量热力图画布不存在")
            
            # 🆕 新增：在区域校准值热力图上绘制区域并显示校准值
            if hasattr(self, 'region_calibration_canvas'):
                print(f"   🎨 开始检查区域校准值热力图...")
                if 'new' in results and 'data' in results['new'] and calibrated_regions:
                    new_data = results['new']['data']
                    print(f"     新版本校准数据形状: {new_data.shape}")
                    print(f"     新版本校准数据范围: [{new_data.min():.2f}, {new_data.max():.2f}]")
                    
                    # 创建区域校准值数据（只显示选中区域的新版本校准值，其他区域设为0）
                    region_calibration_data = self._create_region_calibration_heatmap(new_data, calibrated_regions)
                    
                    # 更新区域校准值热力图
                    try:
                        region_cal_fig = self.region_calibration_canvas.figure
                        region_cal_ax = region_cal_fig.axes[0]
                        print(f"     区域校准值热力图画布: {self.region_calibration_canvas}")
                        print(f"     区域校准值热力图轴: {region_cal_ax}")
                        
                        # 更新热力图数据
                        self.heatmap_manager.update_single_heatmap(self.region_calibration_canvas, region_calibration_data, data_type='region_calibration')
                        
                        # 在区域校准值热力图上绘制区域轮廓（橙色标记）
                        self.region_renderer.draw_calibrated_regions_on_heatmap(region_cal_ax, calibrated_regions, color='orange', linewidth=2)
                        print(f"   ✅ 区域校准值热力图更新完成（橙色轮廓）")
                        print(f"     显示内容: 选中区域的新版本校准数据")
                        
                        # 更新区域校准值热力图画布
                        region_cal_fig.canvas.draw()
                        print(f"     区域校准值热力图画布更新完成")
                        
                        # 将区域校准值数据保存到results中，供统计管理器使用
                        if 'region_calibration' not in results:
                            results['region_calibration'] = {}
                        results['region_calibration']['data'] = region_calibration_data
                        results['region_calibration']['source'] = 'new_calibration'  # 🆕 标记数据来源
                        
                        print(f"   ✅ 区域校准值数据已保存到结果中（来源: 新版本校准）")
                        
                    except Exception as e:
                        print(f"   ❌ 区域校准值热力图更新失败: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"   ⚠️ 区域校准值数据不可用，跳过区域校准值热力图更新")
                    if 'new' not in results:
                        print(f"     原因: 没有新版本校准结果")
                    elif 'data' not in results['new']:
                        print(f"     原因: 新版本校准结果中没有data字段")
                    elif not calibrated_regions:
                        print(f"     原因: 没有检测到区域")
            else:
                print(f"   ⚠️ 区域校准值热力图画布不存在")
            
            # 🆕 新增：在压强热力图上绘制区域并显示压强值
            if hasattr(self, 'pressure_heatmap_canvas'):
                print(f"   🎨 开始检查压强热力图...")
                if calibrated_regions and 'new' in results and 'data' in results['new']:
                    # 🔧 修复：使用校准后的数据而不是原始数据
                    calibrated_data = results['new']['data']
                    print(f"     校准后数据形状: {calibrated_data.shape}")
                    print(f"     校准后数据范围: [{calibrated_data.min():.2f}, {calibrated_data.max():.2f}]")
                    
                    # 🔧 修复：创建压强热力图数据，使用校准后的数据
                    pressure_heatmap_data = self._create_pressure_heatmap_data(calibrated_regions, calibrated_data)
                    
                    # 更新压强热力图
                    try:
                        pressure_fig = self.pressure_heatmap_canvas.figure
                        pressure_ax = pressure_fig.axes[0]
                        print(f"     压强热力图画布: {self.pressure_heatmap_canvas}")
                        print(f"     压强热力图轴: {pressure_ax}")
                        
                        # 更新热力图数据
                        self.heatmap_manager.update_single_heatmap(self.pressure_heatmap_canvas, pressure_heatmap_data, data_type='pressure')
                        
                        # 在压强热力图上绘制区域轮廓（红色标记）
                        self.region_renderer.draw_calibrated_regions_on_heatmap(pressure_ax, calibrated_regions, color='red', linewidth=2)
                        print(f"   ✅ 压强热力图更新完成（红色轮廓）")
                        print(f"     显示内容: 检测区域的校准压强值 (kPa)")
                        
                        # 更新压强热力图画布
                        pressure_fig.canvas.draw()
                        print(f"     压强热力图画布更新完成")
                        
                        # 将压强热力图数据保存到results中，供统计管理器使用
                        if 'pressure_heatmap' not in results:
                            results['pressure_heatmap'] = {}
                        results['pressure_heatmap']['data'] = pressure_heatmap_data
                        results['pressure_heatmap']['pressure_stats'] = self._get_pressure_statistics(pressure_heatmap_data, calibrated_regions)
                        
                        print(f"   ✅ 压强热力图数据已保存到结果中")
                        
                    except Exception as e:
                        print(f"   ❌ 压强热力图更新失败: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"   ⚠️ 压强热力图数据不可用，跳过压强热力图更新")
                    if 'raw' not in results:
                        print(f"     原因: 没有原始数据")
                    elif 'data' not in results['raw']:
                        print(f"     原因: 原始数据中没有data字段")
                    elif not calibrated_regions:
                        print(f"     原因: 没有检测到区域")
            else:
                print(f"   ⚠️ 压强热力图画布不存在")
            
            # 4. 更新区域数量显示
            if hasattr(self, 'region_count_label'):
                region_count = len(calibrated_regions)
                if region_count == 1:
                    region_info = f"主区域: 1"
                    self.region_count_label.setStyleSheet("color: #27ae60; font-weight: bold; min-width: 60px;")
                elif region_count == 2:
                    region_info = f"主区域: 2"
                    self.region_count_label.setStyleSheet("color: #9b59b6; font-weight: bold; min-width: 60px;")
                else:
                    region_info = f"主区域: {region_count}"
                    self.region_count_label.setStyleSheet("color: #e74c3c; font-weight: bold; min-width: 60px;")
                
                self.region_count_label.setText(region_info)
                print(f"   ✅ 区域数量显示更新完成: {region_info}")
                
                # 🆕 新增：显示区域详细信息
                if region_count > 0:
                    print(f"   📊 区域详细信息:")
                    for i, region in enumerate(calibrated_regions):
                        print(f"     区域 {i+1}: ID={region.get('id', 'N/A')}, "
                              f"面积={region.get('area', 'N/A')}, "
                              f"中心={region.get('center', 'N/A')}")
            else:
                print(f"   ⚠️ 区域数量标签不存在")
            
            # 4. 将区域信息保存到结果中，供其他函数使用
            if 'calibrated_regions' not in results:
                results['calibrated_regions'] = {}
            results['calibrated_regions']['regions'] = calibrated_regions
            print(f"   ✅ 区域信息已保存到结果中")
            
            print(f"✅ 校准区域已成功应用到所有热力图")
            
        except Exception as e:
            print(f"❌ 应用校准区域到所有热力图失败: {e}")
            traceback.print_exc()
    
    def _create_combined_region_mask(self, regions, data_shape):
        """创建所有选中区域的组合掩码"""
        try:
            # 创建全零掩码
            combined_mask = np.zeros(data_shape, dtype=bool)
            
            for region in regions:
                if 'contour_mask' in region:
                    # 使用轮廓掩码
                    region_mask = region['contour_mask']
                    if region_mask.shape == data_shape:
                        combined_mask |= (region_mask == 1)
                elif 'mask' in region:
                    # 使用传统掩码
                    region_mask = region['mask']
                    if region_mask.shape == data_shape:
                        combined_mask |= region_mask
                else:
                    # 如果没有掩码，使用边界框创建简单掩码
                    if 'bbox' in region:
                        x1, y1, x2, y2 = region['bbox']
                        combined_mask[y1:y2, x1:x2] = True
            
            print(f"✅ 创建区域掩码完成：选中 {combined_mask.sum()} 个像素点")
            return combined_mask
            
        except Exception as e:
            print(f"❌ 创建区域掩码失败: {e}")
            # 返回全False掩码作为备用
            return np.zeros(data_shape, dtype=bool)
    
    def _create_region_calibration_heatmap(self, new_calibration_data, regions):
        """创建选中区域的新版本校准热力图（只显示选中区域的新版本校准值，其他区域设为0）"""
        try:
            # 创建全零数组
            region_calibration_data = np.zeros_like(new_calibration_data)
            
            print(f"     开始创建选中区域的新版本校准热力图...")
            print(f"       新版本校准数据形状: {new_calibration_data.shape}")
            print(f"       新版本校准数据范围: [{new_calibration_data.min():.2f}, {new_calibration_data.max():.2f}]")
            
            # 为每个选中区域填充新版本校准值
            for i, region in enumerate(regions):
                if 'contour_mask' in region:
                    # 使用轮廓掩码
                    region_mask = region['contour_mask']
                    if region_mask.shape == new_calibration_data.shape:
                        # 将选中区域的新版本校准值复制到结果中
                        region_calibration_data[region_mask == 1] = new_calibration_data[region_mask == 1]
                        print(f"       区域 {i+1}: 使用轮廓掩码，选中像素数: {(region_mask == 1).sum()}")
                elif 'mask' in region:
                    # 使用传统掩码
                    region_mask = region['mask']
                    if region_mask.shape == new_calibration_data.shape:
                        # 将选中区域的新版本校准值复制到结果中
                        region_calibration_data[region_mask] = new_calibration_data[region_mask]
                        print(f"       区域 {i+1}: 使用传统掩码，选中像素数: {region_mask.sum()}")
                else:
                    # 如果没有掩码，使用边界框创建简单掩码
                    if 'bbox' in region:
                        x1, y1, x2, y2 = region['bbox']
                        region_calibration_data[y1:y2, x1:x2] = new_calibration_data[y1:y2, x1:x2]
                        print(f"       区域 {i+1}: 使用边界框，选中像素数: {(y2-y1)*(x2-x1)}")
            
            # 计算统计信息
            selected_pixels = (region_calibration_data > 0).sum()
            total_pixels = region_calibration_data.size
            
            print(f"     选中区域的新版本校准热力图创建完成:")
            print(f"       选中像素数: {selected_pixels}")
            print(f"       总像素数: {total_pixels}")
            print(f"       选中比例: {selected_pixels/total_pixels*100:.1f}%")
            print(f"       区域新版本校准值范围: [{region_calibration_data[region_calibration_data > 0].min():.2f}, {region_calibration_data.max():.2f}]")
            
            return region_calibration_data
            
        except Exception as e:
            print(f"❌ 创建选中区域的新版本校准热力图失败: {e}")
            import traceback
            traceback.print_exc()
            # 返回全零数组作为备用
            return np.zeros_like(new_calibration_data)
    
    def _create_pressure_heatmap_data(self, calibrated_regions, raw_data):
        """创建检测区域的压强热力图数据（只显示检测区域的压强值，其他区域设为0）"""
        try:
            # 创建全零数组
            pressure_heatmap_data = np.zeros_like(raw_data, dtype=np.float32)
            
            print(f"     开始创建检测区域的压强热力图...")
            print(f"       原始数据形状: {raw_data.shape}")
            print(f"       原始数据范围: [{raw_data.min():.2f}, {raw_data.max():.2f}]")
            
            # 🔧 修复：统一使用真实的压强转换，避免模拟转换
            if hasattr(self, 'region_detector') and hasattr(self.region_detector, '_convert_to_pressure'):
                print(f"     🔧 使用真实的压强转换函数...")
                
                for i, region in enumerate(calibrated_regions):
                    if 'contour_mask' in region:
                        region_mask = region['contour_mask']
                        region_raw_data = raw_data * region_mask
                        
                        # 🔧 修复：使用真实的压强转换，而不是模拟转换
                        try:
                            # 尝试使用真实的压强转换
                            region_pressure = self.region_detector._convert_to_pressure(region_raw_data)
                            
                            # 🔧 新增：检查转换结果是否有效
                            if region_pressure is None:
                                print(f"       ⚠️ 压强转换返回None，使用校准后数据")
                                region_pressure = region_raw_data
                            elif np.any(region_pressure < 0):
                                print(f"       ⚠️ 压强转换包含负值，使用校准后数据")
                                region_pressure = region_raw_data
                            else:
                                print(f"       区域 {i+1}: 真实压强转换完成")
                                
                        except Exception as e:
                            print(f"       ⚠️ 真实压强转换失败: {e}")
                            # 如果真实转换失败，使用校准后的数据作为压强值
                            region_pressure = region_raw_data
                            print(f"       区域 {i+1}: 使用校准后数据作为压强值")
                        
                        # 填充压强数据
                        pressure_heatmap_data[region_mask == 1] = region_pressure[region_mask == 1]
                        
                        print(f"       区域 {i+1}: 原始值范围[{region_raw_data.min():.2f}, {region_raw_data.max():.2f}]")
                        print(f"       区域 {i+1}: 压强值范围[{region_pressure.min():.2f}, {region_pressure.max():.2f}] kPa")
                
                print(f"     ✅ 真实压强转换完成")
                return pressure_heatmap_data
                
            else:
                print(f"     ⚠️ 压强转换函数不可用，使用校准后数据")
                # 🔧 修复：不再使用模拟转换，直接使用校准后的数据
                for i, region in enumerate(calibrated_regions):
                    if 'contour_mask' in region:
                        region_mask = region['contour_mask']
                        region_raw_data = raw_data * region_mask
                        
                        # 🔧 修复：直接使用校准后的数据，避免模拟转换
                        pressure_heatmap_data[region_mask == 1] = region_raw_data[region_mask == 1]
                        
                        print(f"       区域 {i+1}: 使用校准后数据，范围[{region_raw_data.min():.2f}, {region_raw_data.max():.2f}]")
                
                return pressure_heatmap_data
            
        except Exception as e:
            print(f"❌ 创建检测区域的压强热力图失败: {e}")
            import traceback
            traceback.print_exc()
            # 返回全零数组作为备用
            return np.zeros_like(raw_data)
    
    def _fill_pressure_data_fallback(self, pressure_heatmap_data, calibrated_regions, raw_data):
        """备用方法：填充压强数据（当RegionDetector不可用时）"""
        try:
            print(f"       使用备用方法填充压强数据...")
            
            # 简单的备用方法：将原始数据作为压强值（仅用于显示）
            for i, region in enumerate(calibrated_regions):
                if 'contour_mask' in region:
                    region_mask = region['contour_mask']
                    if region_mask.shape == pressure_heatmap_data.shape:
                        # 将选中区域的原始数据作为压强值
                        pressure_heatmap_data[region_mask == 1] = raw_data[region_mask == 1]
                        print(f"         区域 {i+1}: 使用原始数据作为压强值，范围: [{raw_data[region_mask == 1].min():.2f}, {raw_data[region_mask == 1].max():.2f}]")
                elif 'bbox' in region:
                    x1, y1, x2, y2 = region['bbox']
                    pressure_heatmap_data[y1:y2, x1:x2] = raw_data[y1:y2, x1:x2]
                    print(f"         区域 {i+1}: 使用边界框，范围: [{raw_data[y1:y2, x1:x2].min():.2f}, {raw_data[y1:y2, x1:x2].max():.2f}]")
            
            print(f"       备用方法完成")
            
        except Exception as e:
            print(f"       备用方法失败: {e}")
    
    def _get_pressure_statistics(self, pressure_heatmap_data, calibrated_regions):
        """获取压强热力图的统计信息"""
        try:
            non_zero_data = pressure_heatmap_data[pressure_heatmap_data > 0]
            
            if len(non_zero_data) > 0:
                # 🆕 压强特有的统计信息
                stats = {
                    'mean_pressure': float(np.mean(non_zero_data)),
                    'max_pressure': float(np.max(non_zero_data)),
                    'min_pressure': float(np.min(non_zero_data)),
                    'total_force': float(np.sum(pressure_heatmap_data)),
                    'total_regions': len(calibrated_regions),
                    'pressure_range': float(np.max(non_zero_data) - np.min(non_zero_data))
                }
                
                print(f"     🔧 压强统计: 平均={stats['mean_pressure']:.2f} kPa, 最大={stats['max_pressure']:.2f} kPa")
            else:
                stats = {
                    'mean_pressure': 0.0,
                    'max_pressure': 0.0,
                    'min_pressure': 0.0,
                    'total_force': 0.0,
                    'total_regions': len(calibrated_regions),
                    'pressure_range': 0.0
                }
            
            return stats
            
        except Exception as e:
            print(f"❌ 获取压强统计信息失败: {e}")
            return {
                'mean_pressure': 0.0,
                'max_pressure': 0.0,
                'min_pressure': 0.0,
                'total_force': 0.0,
                'total_regions': len(calibrated_regions),
                'pressure_range': 0.0
            }
    
    def set_canvases(self, new_canvas, change_data_canvas, region_calibration_canvas, region_count_label, pressure_heatmap_canvas):
        """设置画布引用"""
        self.new_canvas = new_canvas
        self.change_data_canvas = change_data_canvas  # 🆕 新增：变化量画布
        self.region_calibration_canvas = region_calibration_canvas  # 🆕 新增：区域校准值画布
        self.region_count_label = region_count_label
        self.pressure_heatmap_canvas = pressure_heatmap_canvas  # 🆕 新增：压强热力图画布
