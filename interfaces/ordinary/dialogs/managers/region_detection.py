#!/usr/bin/env python3
"""
区域检测管理类

负责识别和检测压力传感器上的区域，特别针对圆柱形物体进行优化
支持torch校准包的压强映射
"""

import numpy as np
import cv2
import traceback
import os

# 尝试导入torch（可选）
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch未安装，无法使用torch校准包")


class RegionDetector:
    """区域检测器（简化版：直接区域检测 + 校准映射支持）"""
    
    def __init__(self):
        self.baseline_data = None
        self.baseline_set = False
        self.calibration_mapping = None  # 🆕 新增：校准映射
        self.calibration_applied = False  # 🆕 新增：校准是否已应用
        
        # 🆕 新增：torch校准包相关
        self.calibration_package = None
        self.calibration_coeffs = None
        self.data_mean = None
        self.data_std = None
        self.conversion_poly_coeffs = None
        self.calibration_type = None  # 'torch_package', 'function', 'array', 'model'
    
    def load_torch_calibration_package(self, package_path):
        """加载torch校准包（你的calibration_package.pt文件）"""
        try:
            if not TORCH_AVAILABLE:
                print("❌ PyTorch未安装，无法加载校准包")
                return False
            
            if not os.path.exists(package_path):
                print(f"❌ 校准包文件不存在: {package_path}")
                return False
            
            print(f"🔧 加载torch校准包: {package_path}")
            
            # 加载校准包
            self.calibration_package = torch.load(package_path, weights_only=False)
            
            # 提取校准参数
            self.calibration_coeffs = self.calibration_package['coeffs']  # [4096, 3]
            self.data_mean = self.calibration_package['data_mean']        # 标准化均值
            self.data_std = self.calibration_package['data_std']          # 标准化标准差
            self.conversion_poly_coeffs = self.calibration_package['conversion_poly_coeffs']  # 二次多项式系数
            
            # 设置校准类型
            self.calibration_type = 'torch_package'
            self.calibration_applied = True
            
            print(f"✅ torch校准包加载成功")
            print(f"   校准系数形状: {self.calibration_coeffs.shape}")
            print(f"   数据均值: {self.data_mean.item():.2f}")
            print(f"   数据标准差: {self.data_std.item():.2f}")
            print(f"   转换多项式系数: {self.conversion_poly_coeffs}")
            
            return True
            
        except Exception as e:
            print(f"❌ 加载torch校准包失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def set_calibration_mapping(self, calibration_mapping):
        """设置校准映射（响应值到压强的转换关系）"""
        try:
            self.calibration_mapping = calibration_mapping
            self.calibration_applied = True
            
            # 判断校准类型
            if hasattr(calibration_mapping, '__call__'):
                self.calibration_type = 'function'
            elif hasattr(calibration_mapping, 'predict'):
                self.calibration_type = 'model'
            elif isinstance(calibration_mapping, np.ndarray):
                self.calibration_type = 'array'
            else:
                self.calibration_type = 'unknown'
            
            print(f"✅ 校准映射设置成功")
            print(f"   校准类型: {self.calibration_type}")
            if hasattr(calibration_mapping, 'shape'):
                print(f"   校准映射形状: {calibration_mapping.shape}")
            elif hasattr(calibration_mapping, '__len__'):
                print(f"   校准映射长度: {len(calibration_mapping)}")
            else:
                print(f"   校准映射类型: {type(calibration_mapping)}")
        except Exception as e:
            print(f"❌ 设置校准映射失败: {e}")
    
    def apply_calibration_to_data(self, raw_data):
        """将校准映射应用到原始数据，转换为校准后的压强数据"""
        try:
            # 🆕 优先使用torch校准包
            if self.calibration_type == 'torch_package' and self.calibration_applied:
                return self._apply_torch_calibration(raw_data)
            
            # 其他校准方式
            if self.calibration_mapping is None:
                print("⚠️ 没有校准映射，返回原始数据")
                return raw_data
            
            print(f"🔧 应用校准映射到数据...")
            print(f"   原始数据形状: {raw_data.shape}")
            print(f"   原始数据范围: [{raw_data.min():.2f}, {raw_data.max():.2f}]")
            
            # 应用校准映射
            if hasattr(self.calibration_mapping, '__call__'):
                # 如果校准映射是函数
                calibrated_data = self.calibration_mapping(raw_data)
            elif hasattr(self.calibration_mapping, 'predict'):
                # 如果校准映射是sklearn模型
                calibrated_data = self.calibration_mapping.predict(raw_data.reshape(-1, 1)).reshape(raw_data.shape)
            elif isinstance(self.calibration_mapping, np.ndarray):
                # 如果校准映射是数组（查找表）
                if self.calibration_mapping.shape == raw_data.shape:
                    calibrated_data = raw_data * self.calibration_mapping
                else:
                    # 插值应用校准映射
                    calibrated_data = self._apply_lookup_calibration(raw_data)
            else:
                print("⚠️ 未知的校准映射类型，返回原始数据")
                return raw_data
            
            print(f"   校准后数据形状: {calibrated_data.shape}")
            print(f"   校准后数据范围: [{calibrated_data.min():.2f}, {calibrated_data.max():.2f}]")
            print(f"   ✅ 校准映射应用成功")
            
            return calibrated_data
            
        except Exception as e:
            print(f"❌ 应用校准映射失败: {e}")
            return raw_data
    
    def _apply_torch_calibration(self, raw_data):
        """应用torch校准包进行校准"""
        try:
            print(f"🔧 应用torch校准包到数据...")
            print(f"   原始数据形状: {raw_data.shape}")
            print(f"   原始数据范围: [{raw_data.min():.2f}, {raw_data.max():.2f}]")
            
            # 步骤1：数据标准化
            raw_data_tensor = torch.from_numpy(raw_data).float()
            scaled_data = (raw_data_tensor - self.data_mean) / self.data_std
            
            # 步骤2：应用多项式校准系数
            H, W = raw_data.shape
            scaled_data_flat = scaled_data.reshape(-1)  # [4096]
            
            # 创建多项式特征 [4096, 3]
            powers = torch.arange(2, -1, -1)  # [2, 1, 0]
            scaled_data_poly = scaled_data_flat.unsqueeze(-1).pow(powers)  # [4096, 3]
            
            # 应用校准系数
            calibrated_scaled = torch.sum(scaled_data_poly * self.calibration_coeffs, dim=1)  # [4096]
            
            # 步骤3：逆标准化
            calibrated_data = calibrated_scaled * self.data_std + self.data_mean
            
            # 步骤4：转换为压强值（牛顿）
            calibrated_data_numpy = calibrated_data.detach().numpy()
            pressure_data = self._convert_to_pressure(calibrated_data_numpy)
            
            # 重塑回原始形状
            pressure_data = pressure_data.reshape(H, W)
            
            print(f"   校准后数据形状: {pressure_data.shape}")
            print(f"   校准后数据范围: [{pressure_data.min():.2f}, {pressure_data.max():.2f}] N")
            print(f"   ✅ torch校准包应用成功")
            
            return pressure_data
            
        except Exception as e:
            print(f"❌ 应用torch校准包失败: {e}")
            import traceback
            traceback.print_exc()
            return raw_data
    
    def _convert_to_pressure(self, calibrated_values):
        """将校准后的值转换为压强值（牛顿）"""
        try:
            # 使用二次多项式系数转换
            # Pressure_N = a * V^2 + b * V + c
            a, b, c = self.conversion_poly_coeffs
            
            # 向量化计算
            pressure_values = a * (calibrated_values ** 2) + b * calibrated_values + c
            
            return pressure_values
            
        except Exception as e:
            print(f"❌ 压强转换失败: {e}")
            return calibrated_values
    
    def set_baseline_data(self, baseline_data):
        """设置基准数据"""
        try:
            self.baseline_data = baseline_data.copy()
            self.baseline_set = True
            print(f"✅ 基准数据设置成功，数据形状: {baseline_data.shape}")
        except Exception as e:
            print(f"❌ 设置基准数据失败: {e}")
    
    def reset_baseline_data(self):
        """重置基准数据"""
        self.baseline_data = None
        self.baseline_set = False
        print("✅ 基准数据已重置")
    
    def _apply_lookup_calibration(self, raw_data):
        """应用查找表校准映射"""
        try:
            # 创建校准后的数据数组
            calibrated_data = np.zeros_like(raw_data, dtype=np.float32)
            
            # 获取原始数据的唯一值
            unique_values = np.unique(raw_data)
            print(f"     原始数据唯一值数量: {len(unique_values)}")
            
            # 对每个像素应用校准映射
            for i in range(raw_data.shape[0]):
                for j in range(raw_data.shape[1]):
                    raw_value = raw_data[i, j]
                    
                    # 查找最接近的校准值
                    if hasattr(self.calibration_mapping, 'shape') and len(self.calibration_mapping.shape) == 2:
                        # 二维查找表
                        calibrated_data[i, j] = self._interpolate_2d_lookup(raw_value, i, j)
                    else:
                        # 一维查找表
                        calibrated_data[i, j] = self._interpolate_1d_lookup(raw_value)
            
            return calibrated_data
            
        except Exception as e:
            print(f"     ❌ 查找表校准失败: {e}")
            return raw_data
    
    def _interpolate_1d_lookup(self, raw_value):
        """一维查找表插值"""
        try:
            # 这里需要根据实际的校准映射格式实现
            # 暂时返回原始值
            return raw_value
        except Exception:
            return raw_value
    
    def _interpolate_2d_lookup(self, raw_value, i, j):
        """二维查找表插值"""
        try:
            # 这里需要根据实际的校准映射格式实现
            # 暂时返回原始值
            return raw_value
        except Exception:
            return raw_value
    
    def identify_calibrated_regions(self, data, threshold_percentile=80, max_regions=2, use_calibration=False):
        """识别校准后的数据中的高响应区域（改进版：结合边缘检测和智能阈值）"""
        try:
            print(f"🔍 开始识别校准区域（改进版算法）...")
            print(f"   数据范围: [{data.min():.2f}, {data.max():.2f}]")
            print(f"   阈值百分位: {threshold_percentile}%")
            print(f"   最大区域数: {max_regions}")
            
            # 🔧 改进1：智能阈值调整
            data_std = data.std()
            data_range = data.max() - data.min()
            
            # 根据数据特性动态调整阈值
            if data_std > data_range * 0.3:
                # 数据变化大时，使用更严格的阈值
                adjusted_threshold = min(threshold_percentile, 90)
                print(f"   🔧 数据变化较大，调整阈值: {threshold_percentile}% → {adjusted_threshold}%")
            else:
                # 数据变化小时，使用更宽松的阈值
                adjusted_threshold = min(threshold_percentile, 75)
                print(f"   🔧 数据变化较小，调整阈值: {threshold_percentile}% → {adjusted_threshold}%")
            
            # 1. 改进的阈值分割
            threshold = np.percentile(data, adjusted_threshold)
            print(f"   最终压力阈值: {threshold:.2f}")
            
            # 2. 二值化：识别高于阈值的压力区域
            binary_mask = data > threshold
            print(f"   初始激活点数: {binary_mask.sum()}")
            
            # 🔧 改进2：边缘检测预处理
            # 使用Sobel算子检测边缘
            sobel_x = cv2.Sobel(data.astype(np.float32), cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(data.astype(np.float32), cv2.CV_64F, 0, 1, ksize=3)
            edge_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
            
            # 边缘强度阈值
            edge_threshold = np.percentile(edge_magnitude, 70)
            edge_mask = edge_magnitude > edge_threshold
            
            print(f"   边缘检测完成，边缘点数: {edge_mask.sum()}")
            
            # 3. 改进的形态学操作：更精细的控制
            # 使用更小的核，避免过度连接
            kernel_size = 2  # 从3x3改为2x2
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            
            # 开运算：去除小噪声
            opened_mask = cv2.morphologyEx(binary_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
            print(f"   开运算后激活点数: {opened_mask.sum()}")
            
            # 闭运算：填充小孔，但使用更小的核
            closed_mask = cv2.morphologyEx(opened_mask, cv2.MORPH_CLOSE, kernel)
            print(f"   闭运算后激活点数: {closed_mask.sum()}")
            
            # 🔧 改进3：结合边缘信息优化掩码
            # 在边缘附近保留更多细节
            refined_mask = closed_mask.copy()
            refined_mask[edge_mask] = closed_mask[edge_mask]  # 边缘区域保持原状
            
            # 4. 轮廓检测
            contours, hierarchy = cv2.findContours(refined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                print("⚠️ 未找到任何轮廓")
                return []
            
            print(f"   找到轮廓数量: {len(contours)}")
            
            # 5. 🔧 改进4：更智能的区域评分系统
            region_candidates = []
            for i, contour in enumerate(contours):
                try:
                    # 计算基本特征
                    area = cv2.contourArea(contour)
                    if area < 3:  # 降低最小面积要求
                        continue
                    
                    # 计算轮廓的几何特性
                    perimeter = cv2.arcLength(contour, True)
                    compactness = (4 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0
                    
                    # 过滤掉过于不规则的区域
                    if compactness < 0.1:  # 紧凑度阈值
                        print(f"     ⚠️ 轮廓 {i+1}: 紧凑度过低 ({compactness:.3f})，跳过")
                        continue
                    
                    # 🎯 计算区域内的压力统计
                    contour_mask = np.zeros_like(refined_mask)
                    cv2.fillPoly(contour_mask, [contour], 1)
                    
                    region_data = data * contour_mask
                    region_pressure_values = region_data[contour_mask == 1]
                    
                    if len(region_pressure_values) > 0:
                        avg_pressure = np.mean(region_pressure_values)
                        max_pressure = np.max(region_pressure_values)
                        pressure_density = np.sum(region_pressure_values) / area
                        
                        # 🔧 改进的评分系统：综合考虑多个因素
                        # 压力强度 + 区域质量 + 紧凑度
                        pressure_score = (avg_pressure * 0.35 + max_pressure * 0.35 + pressure_density * 0.15)
                        quality_score = compactness * 0.15  # 紧凑度贡献
                        
                        total_score = pressure_score + quality_score
                        
                        # 创建区域候选
                        region_candidate = {
                            'contour': contour,
                            'area': area,
                            'avg_pressure': avg_pressure,
                            'max_pressure': max_pressure,
                            'pressure_density': pressure_density,
                            'pressure_score': pressure_score,
                            'compactness': compactness,
                            'quality_score': quality_score,
                            'total_score': total_score,  # 🆕 综合评分
                            'contour_mask': contour_mask,
                            'index': i
                        }
                        region_candidates.append(region_candidate)
                        
                        print(f"     轮廓 {i+1}: 面积={area:.1f}, 紧凑度={compactness:.3f}, "
                              f"平均压力={avg_pressure:.2f}, 最大压力={max_pressure:.2f}, "
                              f"压力密度={pressure_density:.2f}, 综合评分={total_score:.2f}")
                    else:
                        print(f"     ⚠️ 轮廓 {i+1}: 无法计算压力值")
                        
                except Exception as e:
                    print(f"     ⚠️ 分析轮廓 {i+1} 时出错: {e}")
                    continue
            
            if not region_candidates:
                print("⚠️ 没有有效的区域候选")
                return []
            
            # 🔧 改进5：按综合评分排序
            region_candidates.sort(key=lambda x: x['total_score'], reverse=True)
            print(f"   📊 区域按综合评分排序完成")
            
            # 选择前N个综合评分最高的区域
            selected_regions = region_candidates[:max_regions]
            
            # 转换为标准区域格式
            calibrated_regions = []
            for i, candidate in enumerate(selected_regions):
                try:
                    region = self._create_pressure_based_region_from_candidate(candidate, data, i+1)
                    if region:
                        calibrated_regions.append(region)
                        print(f"   ✅ 选择区域 {i+1}: 面积={candidate['area']:.1f}, "
                              f"紧凑度={candidate['compactness']:.3f}, "
                              f"平均压力={candidate['avg_pressure']:.2f}, "
                              f"综合评分={candidate['total_score']:.2f}")
                except Exception as e:
                    print(f"   ❌ 创建区域 {i+1} 时出错: {e}")
                    continue
            
            print(f"✅ 改进版区域识别完成，选择了 {len(calibrated_regions)} 个区域")
            print(f"   📊 检测基于综合评分排序，平衡压力强度和区域质量")
            
            return calibrated_regions
            
        except Exception as e:
            print(f"❌ 识别校准区域失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def convert_regions_to_pressure(self, regions, raw_data):
        """将检测到的区域转换为压强值（独立功能）"""
        try:
            if not regions:
                print("⚠️ 没有区域数据，无法进行压强转换")
                return []
            
            if not self.calibration_applied:
                print("⚠️ 校准包未加载，无法进行压强转换")
                return []
            
            print(f"🔧 开始将检测到的区域转换为压强值...")
            print(f"   区域数量: {len(regions)}")
            
            pressure_regions = []
            for i, region in enumerate(regions):
                try:
                    # 提取区域内的原始数据
                    region_mask = region['contour_mask']
                    region_raw_data = raw_data * region_mask
                    
                    # 应用校准转换为压强值
                    region_pressure_data = self._apply_torch_calibration(region_raw_data)
                    
                    # 计算区域内的压强统计信息
                    region_pressure_values = region_pressure_data[region_mask > 0]
                    if len(region_pressure_values) > 0:
                        pressure_stats = {
                            'mean_pressure': np.mean(region_pressure_values),
                            'max_pressure': np.max(region_pressure_values),
                            'min_pressure': np.min(region_pressure_values),
                            'std_pressure': np.std(region_pressure_values),
                            'total_force': np.sum(region_pressure_values)
                        }
                    else:
                        pressure_stats = {
                            'mean_pressure': 0.0,
                            'max_pressure': 0.0,
                            'min_pressure': 0.0,
                            'std_pressure': 0.0,
                            'total_force': 0.0
                        }
                    
                    # 创建压强区域信息
                    pressure_region = {
                        'id': region['id'],
                        'contour': region['contour'],
                        'contour_mask': region['contour_mask'],
                        'area': region['area'],
                        'center': region['center'],
                        'bbox': region['bbox'],
                        'compactness': region['compactness'],
                        'cylindrical_score': region['cylindrical_score'],
                        'pressure_data': region_pressure_data,  # 整个区域的压强数据
                        'pressure_stats': pressure_stats,      # 压强统计信息
                        'raw_data': region_raw_data           # 原始区域数据
                    }
                    
                    pressure_regions.append(pressure_region)
                    
                    print(f"   ✅ 区域 {i+1} 压强转换完成:")
                    print(f"      平均压强: {pressure_stats['mean_pressure']:.2f} N")
                    print(f"      最大压强: {pressure_stats['max_pressure']:.2f} N")
                    print(f"      最小压强: {pressure_stats['min_pressure']:.2f} N")
                    print(f"      总力: {pressure_stats['total_force']:.2f} N")
                    
                except Exception as e:
                    print(f"   ❌ 区域 {i+1} 压强转换失败: {e}")
                    continue
            
            print(f"✅ 区域压强转换完成，共转换 {len(pressure_regions)} 个区域")
            return pressure_regions
            
        except Exception as e:
            print(f"❌ 区域压强转换失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_region_pressure_summary(self, pressure_regions):
        """获取区域压强汇总信息"""
        try:
            if not pressure_regions:
                return None
            
            print(f"📊 区域压强汇总信息:")
            
            summary = {
                'total_regions': len(pressure_regions),
                'total_force': 0.0,
                'max_pressure': 0.0,
                'min_pressure': float('inf'),
                'region_details': []
            }
            
            for region in pressure_regions:
                stats = region['pressure_stats']
                summary['total_force'] += stats['total_force']
                summary['max_pressure'] = max(summary['max_pressure'], stats['max_pressure'])
                summary['min_pressure'] = min(summary['min_pressure'], stats['min_pressure'])
                
                region_detail = {
                    'id': region['id'],
                    'area': region['area'],
                    'mean_pressure': stats['mean_pressure'],
                    'max_pressure': stats['max_pressure'],
                    'total_force': stats['total_force']
                }
                summary['region_details'].append(region_detail)
                
                print(f"   区域 {region['id']}: 面积={region['area']:.1f}, "
                      f"平均压强={stats['mean_pressure']:.2f}N, "
                      f"总力={stats['total_force']:.2f}N")
            
            print(f"   总计: {summary['total_regions']} 个区域, "
                  f"总力={summary['total_force']:.2f}N, "
                  f"压强范围=[{summary['min_pressure']:.2f}, {summary['max_pressure']:.2f}]N")
            
            return summary
            
        except Exception as e:
            print(f"❌ 获取压强汇总信息失败: {e}")
            return None
    
    def create_pressure_heatmap(self, pressure_regions, raw_data_shape=(64, 64)):
        """创建校准后的压强热力图"""
        try:
            if not pressure_regions:
                print("⚠️ 没有压强区域数据，无法创建热力图")
                return None
            
            print(f"🔧 创建校准后的压强热力图...")
            print(f"   区域数量: {len(pressure_regions)}")
            print(f"   热力图尺寸: {raw_data_shape}")
            
            # 创建压强热力图（只显示检测到的区域）
            pressure_heatmap = np.zeros(raw_data_shape, dtype=np.float32)
            
            # 创建完整压强热力图（显示所有区域的压强数据）
            full_pressure_heatmap = np.zeros(raw_data_shape, dtype=np.float32)
            
            # 创建区域标识热力图（用不同颜色标识不同区域）
            region_identifier_heatmap = np.zeros(raw_data_shape, dtype=np.float32)
            
            for i, region in enumerate(pressure_regions):
                try:
                    region_id = region['id']
                    region_mask = region['contour_mask']
                    pressure_data = region['pressure_data']
                    
                    # 更新压强热力图（只显示检测到的区域）
                    pressure_heatmap += pressure_data
                    
                    # 更新完整压强热力图
                    full_pressure_heatmap += pressure_data
                    
                    # 更新区域标识热力图（用区域ID标识）
                    region_identifier_heatmap += region_mask * region_id
                    
                    print(f"   ✅ 区域 {region_id} 压强数据已添加到热力图")
                    
                except Exception as e:
                    print(f"   ❌ 区域 {i+1} 压强数据添加失败: {e}")
                    continue
            
            # 创建热力图信息字典
            heatmap_info = {
                'pressure_heatmap': pressure_heatmap,           # 压强热力图
                'full_pressure_heatmap': full_pressure_heatmap, # 完整压强热力图
                'region_identifier_heatmap': region_identifier_heatmap, # 区域标识热力图
                'pressure_stats': {
                    'min_pressure': np.min(pressure_heatmap[pressure_heatmap > 0]) if np.any(pressure_heatmap > 0) else 0.0,
                    'max_pressure': np.max(pressure_heatmap) if np.any(pressure_heatmap > 0) else 0.0,
                    'mean_pressure': np.mean(pressure_heatmap[pressure_heatmap > 0]) if np.any(pressure_heatmap > 0) else 0.0,
                    'total_force': np.sum(pressure_heatmap)
                }
            }
            
            print(f"✅ 压强热力图创建完成")
            print(f"   压强范围: [{heatmap_info['pressure_stats']['min_pressure']:.2f}, {heatmap_info['pressure_stats']['max_pressure']:.2f}] N")
            print(f"   平均压强: {heatmap_info['pressure_stats']['mean_pressure']:.2f} N")
            print(f"   总力: {heatmap_info['pressure_stats']['total_force']:.2f} N")
            
            return heatmap_info
            
        except Exception as e:
            print(f"❌ 创建压强热力图失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_pressure_heatmap_data(self, pressure_regions, heatmap_type='pressure'):
        """获取指定类型的压强热力图数据"""
        try:
            if not pressure_regions:
                return None
            
            # 创建热力图
            heatmap_info = self.create_pressure_heatmap(pressure_regions)
            if not heatmap_info:
                return None
            
            # 根据类型返回对应的热力图数据
            if heatmap_type == 'pressure':
                return heatmap_info['pressure_heatmap']
            elif heatmap_type == 'full_pressure':
                return heatmap_info['full_pressure_heatmap']
            elif heatmap_type == 'region_identifier':
                return heatmap_info['region_identifier_heatmap']
            else:
                print(f"⚠️ 未知的热力图类型: {heatmap_type}")
                return heatmap_info['pressure_heatmap']
                
        except Exception as e:
            print(f"❌ 获取压强热力图数据失败: {e}")
            return None
    
    def _simple_mask_cleanup(self, binary_mask):
        """简化的掩码清理（去除复杂的形态学优化）"""
        try:
            # 🆕 简化：只做基本的噪点去除，不做复杂的形态学操作
            # 1. 去除小面积噪点（使用连通组件分析）
            from scipy import ndimage
            
            # 标记连通组件
            labeled_mask, num_features = ndimage.label(binary_mask)
            
            # 计算每个组件的面积
            component_sizes = ndimage.sum(binary_mask, labeled_mask, range(1, num_features + 1))
            
            # 创建清理后的掩码
            cleaned_mask = np.zeros_like(binary_mask)
            
            # 只保留面积大于阈值的组件
            min_area = 3  # 最小面积阈值
            for i, size in enumerate(component_sizes):
                if size >= min_area:
                    cleaned_mask[labeled_mask == i + 1] = True
            
            print(f"     掩码清理完成：去除小面积噪点，保留 {np.sum(cleaned_mask)} 个有效像素")
            return cleaned_mask.astype(bool)
            
        except ImportError:
            # 如果没有scipy，使用简单的OpenCV方法
            print(f"     ⚠️ scipy未安装，使用OpenCV基本清理")
            try:
                # 简单的开运算去除小噪点
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                cleaned_mask = cv2.morphologyEx(binary_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
                print(f"     掩码清理完成：使用OpenCV基本清理")
                return cleaned_mask.astype(bool)
            except Exception as e:
                print(f"     ⚠️ OpenCV清理失败: {e}")
                return binary_mask
        except Exception as e:
            print(f"     ⚠️ 掩码清理失败: {e}")
            return binary_mask

    def _create_pressure_based_region_from_candidate(self, candidate, data, region_id):
        """从候选区域创建基于压力强度的标准区域格式"""
        try:
            contour = candidate['contour']
            area = candidate['area']
            avg_pressure = candidate['avg_pressure']
            max_pressure = candidate['max_pressure']
            pressure_density = candidate['pressure_density']
            pressure_score = candidate['pressure_score']
            contour_mask = candidate['contour_mask']
            
            # 计算轮廓中心
            M = cv2.moments(contour)
            if M["m00"] != 0:
                center_x = int(M["m10"] / M["m00"])
                center_y = int(M["m01"] / M["m00"])
            else:
                # 如果矩计算失败，使用轮廓的边界框中心
                x, y, w, h = cv2.boundingRect(contour)
                center_x = int(x + w/2)
                center_y = int(y + h/2)
            
            # 计算边界框
            x, y, w, h = cv2.boundingRect(contour)
            bbox = (x, y, x + w, y + h)
            
            # 计算轮廓周长和紧凑度
            perimeter = cv2.arcLength(contour, True)
            compactness = (area * 4 * np.pi) / (perimeter ** 2) if perimeter > 0 else 0
            
            # 创建标准区域格式
            region = {
                'id': region_id,
                'center': (center_x, center_y),
                'bbox': bbox,
                'area': int(area),
                'contour': contour,
                'contour_mask': contour_mask,
                'perimeter': perimeter,
                'compactness': compactness,
                'method': 'pressure_based_detection',
                
                # 🆕 新增：压力相关的统计信息
                'avg_pressure': avg_pressure,
                'max_pressure': max_pressure,
                'pressure_density': pressure_density,
                'pressure_score': pressure_score,
                
                # 兼容性：保留原有字段
                'mask': contour_mask,  # 为了兼容现有代码
                'avg_response': avg_pressure,  # 为了兼容现有代码
                'max_response': max_pressure   # 为了兼容现有代码
            }
            
            return region
            
        except Exception as e:
            print(f"   ❌ 创建压力强度区域失败: {e}")
            return None



