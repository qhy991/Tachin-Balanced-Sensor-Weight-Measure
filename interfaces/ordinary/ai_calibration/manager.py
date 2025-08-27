"""
AI校准管理器

负责管理AI校准的加载、应用和信息显示
"""

import os
import torch
import numpy as np
from PyQt5 import QtWidgets
from .adapter import AICalibrationAdapter


class AICalibrationManager:
    """AI校准管理器 - 仅支持新版本校准"""
    
    def __init__(self, parent_window):
        self.parent = parent_window
        self.calibration_coeffs = None
        self.device = torch.device("cpu")
        self.calibration_data_mean = None
        self.calibration_data_std = None
        self.calibration_format = None
        
        # 🆕 修改：只保留新版本校准器，去除双校准模式
        self.dual_calibration_mode = False  # 不再需要双校准模式
        self.new_calibrator = None  # 新版本校准器
        
        # 去皮功能相关属性
        self.zero_offset = None  # 零点偏移量
        self.taring_enabled = False  # 是否启用去皮功能
        self.zero_offset_matrix = None  # 逐点去皮基准矩阵
        
        self.setup_calibration()
    
    def setup_calibration(self):
        """设置AI校准功能"""
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            print("AI校准将使用GPU加速")
        else:
            self.device = torch.device("cpu")
            print("AI校准将使用CPU")
    
    def load_ai_calibration(self):
        """加载AI校准模型"""
        try:
            # 尝试从当前目录加载
            current_dir = os.getcwd()
            coeffs_path = os.path.join(current_dir, 'calibration_package.pt')

            if not os.path.exists(coeffs_path):
                # 如果不存在，尝试从其他可能路径加载
                possible_paths = [
                    'calibration_package.pt',
                    '../calibration_package.pt',
                    '../../calibration_package.pt',
                    'data-0815/../calibration_package.pt',
                    # 兼容旧版本文件名
                    'calibration_coeffs.pt',
                    '../calibration_coeffs.pt'
                ]

                for path in possible_paths:
                    if os.path.exists(path):
                        coeffs_path = path
                        break

            if os.path.exists(coeffs_path):
                # 加载校准包
                calibration_package = torch.load(coeffs_path)
                
                # 检查是新版本还是旧版本格式
                if isinstance(calibration_package, dict) and 'coeffs' in calibration_package:
                    # 新版本格式：calibration_package.pt
                    self.calibration_coeffs = calibration_package['coeffs'].to(self.device)
                    self.calibration_data_mean = calibration_package['data_mean'].to(self.device)
                    self.calibration_data_std = calibration_package['data_std'].to(self.device)
                    self.calibration_format = 'new'
                    print(f"✅ 新版本AI校准包加载成功: {coeffs_path}")
                    print(f"   系数形状: {self.calibration_coeffs.shape}")
                    print(f"   数据均值: {self.calibration_data_mean.shape}")
                    print(f"   数据标准差: {self.calibration_data_std.shape}")
                else:
                    # 旧版本格式：calibration_coeffs.pt
                    self.calibration_coeffs = calibration_package.to(self.device)
                    self.calibration_data_mean = None
                    self.calibration_data_std = None
                    self.calibration_format = 'old'
                    print(f"✅ 旧版本AI校准模型加载成功: {coeffs_path}")
                print(f"   模型形状: {self.calibration_coeffs.shape}")

                # 显示成功消息
                format_text = "新版本校准包" if self.calibration_format == 'new' else "旧版本校准模型"
                QtWidgets.QMessageBox.information(self.parent, "成功",
                    f"{format_text}已加载!\n路径: {coeffs_path}\n形状: {self.calibration_coeffs.shape}")

            else:
                QtWidgets.QMessageBox.warning(self.parent, "文件未找到",
                    f"未找到校准文件: calibration_package.pt 或 calibration_coeffs.pt\n请先运行校准训练脚本。")
                return False

        except Exception as e:
            QtWidgets.QMessageBox.critical(self.parent, "加载失败", f"加载AI校准模型失败:\n{str(e)}")
            return False

        return True
    
    def apply_ai_calibration(self, raw_data_64x64):
        """应用AI校准到64x64原始数据"""
        if self.calibration_coeffs is None:
            return raw_data_64x64

        try:
            # 将数据转换为tensor
            raw_tensor = torch.from_numpy(raw_data_64x64).float().to(self.device)

            if self.calibration_format == 'new':
                # 新版本校准流程：标准化 → 校准 → 逆标准化
                print(f"🔧 新版本校准流程开始...")
                print(f"   原始数据范围: [{raw_tensor.min():.2f}, {raw_tensor.max():.2f}]")
                print(f"   数据均值范围: [{self.calibration_data_mean.min():.2f}, {self.calibration_data_mean.max():.2f}]")
                print(f"   数据标准差范围: [{self.calibration_data_std.min():.2f}, {self.calibration_data_std.max():.2f}]")
                
                # 1. 对新数据应用相同的标准化
                scaled_tensor = (raw_tensor - self.calibration_data_mean) / self.calibration_data_std
                print(f"   标准化后范围: [{scaled_tensor.min():.2f}, {scaled_tensor.max():.2f}]")
                
                # 2. 在标准化数据上应用校准函数
                x_flat = scaled_tensor.view(-1)
                x_poly = x_flat.unsqueeze(-1).pow(torch.arange(2, -1, -1, device=self.device))
                
                calibrated_flat_scaled = torch.sum(x_poly * self.calibration_coeffs, dim=1)
                print(f"   校准后标准化范围: [{calibrated_flat_scaled.min():.2f}, {calibrated_flat_scaled.max():.2f}]")
                
                # 3. 将结果逆变换回原始数据量级
                calibrated_flat_rescaled = calibrated_flat_scaled * self.calibration_data_std + self.calibration_data_mean
                calibrated_tensor = calibrated_flat_rescaled.view(64, 64)
                print(f"   逆变换后范围: [{calibrated_tensor.min():.2f}, {calibrated_tensor.max():.2f}]")
                
                # 转换为numpy数组并返回
                calibrated_data = calibrated_tensor.cpu().numpy()
                print(f"✅ 新版本校准完成，最终范围: [{calibrated_data.min():.2f}, {calibrated_data.max():.2f}]")
                return calibrated_data

            else:
                # 旧版本校准流程：直接应用二次多项式
                # 展平数据
                raw_flat = raw_tensor.view(-1)

                # 应用校准函数：y = a*x² + b*x + c
                x = raw_flat
                a = self.calibration_coeffs[:, 0]  # 二次项系数
                b = self.calibration_coeffs[:, 1]  # 一次项系数
                c = self.calibration_coeffs[:, 2]  # 常数项

                calibrated_flat = a * x**2 + b * x + c

                # 恢复形状
                calibrated_tensor = calibrated_flat.view(64, 64)

                # 转换为numpy数组
                calibrated_data = calibrated_tensor.cpu().numpy()

                # 添加数据范围限制，避免校准后数据过于极端
                raw_range = raw_data_64x64.max() - raw_data_64x64.min()
                if raw_range > 0:
                    # 限制校准后数据的范围不超过原始数据的5倍
                    max_allowed_range = raw_range * 5
                    calibrated_range = calibrated_data.max() - calibrated_data.min()
                    
                    if calibrated_range > max_allowed_range:
                        print(f"⚠️ 校准后数据范围过大: {calibrated_range:.1f} > {max_allowed_range:.1f}")
                        print(f"   原始范围: {raw_range:.1f}, 校准后范围: {calibrated_range:.1f}")
                        print(f"   将限制校准后数据范围")
                        
                        # 显示校准系数信息（调试用）
                        coeffs_cpu = self.calibration_coeffs.cpu()
                        print(f"   校准系数范围:")
                        print(f"     a: [{coeffs_cpu[:, 0].min():.4f}, {coeffs_cpu[:, 0].max():.4f}]")
                        print(f"     b: [{coeffs_cpu[:, 1].min():.4f}, {coeffs_cpu[:, 1].max():.4f}]")
                        print(f"     c: [{coeffs_cpu[:, 2].min():.4f}, {coeffs_cpu[:, 2].max():.4f}]")
                    
                    # 将校准后数据限制在合理范围内
                    calibrated_mean = calibrated_data.mean()
                    calibrated_data = np.clip(calibrated_data, 
                                           calibrated_mean - max_allowed_range/2,
                                           calibrated_mean + max_allowed_range/2)

                # 滤除负值：将负值替换为0
                negative_mask = calibrated_data < 0
                if negative_mask.any():
                    negative_count = negative_mask.sum()
                    print(f"⚠️ 检测到 {negative_count} 个负值，将其替换为0")
                    calibrated_data[negative_mask] = 0

                # 零点校正：如果原始数据接近0，校准后也应该接近0
                zero_threshold = 5.0  # 认为小于5的原始值为"无按压"
                zero_mask = raw_data_64x64 < zero_threshold
                
                if zero_mask.any():
                    zero_count = zero_mask.sum()
                    print(f"🔧 零点校正: 检测到 {zero_count} 个接近零的点，将其校准值限制在合理范围内")
                    
                    # 对于接近零的原始数据，校准后的值不应该过大
                    max_allowed_zero_value = 10.0  # 允许的最大零点值
                    calibrated_data[zero_mask] = np.clip(calibrated_data[zero_mask], 0, max_allowed_zero_value)

                # 应用去皮校正
                calibrated_data = self.apply_taring_correction(calibrated_data)

                return calibrated_data

        except Exception as e:
            print(f"AI校准应用失败: {e}")
            return raw_data_64x64
    
    def load_new_calibrator(self):
        """加载新版本校准器"""
        try:
            print("🔧 开始加载新版本校准器...")
            
            # 查找新版本校准文件
            new_cal_file = None
            possible_paths = [
                'calibration_package.pt',
                '../calibration_package.pt',
                '../../calibration_package.pt',
                'data-0815/../calibration_package.pt'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    new_cal_file = path
                    break
            
            if not new_cal_file:
                QtWidgets.QMessageBox.warning(self.parent, "文件未找到",
                    "未找到新版本校准文件。\n请确保存在以下文件：\n• calibration_package.pt (新版本)")
                return False
            
            # 加载新版本校准器
            print(f"🔧 加载新版本校准器: {new_cal_file}")
            self.new_calibrator = AICalibrationAdapter()
            if self.new_calibrator.load_calibration(new_cal_file):
                print("✅ 新版本校准器加载成功")
            else:
                print("❌ 新版本校准器加载失败")
                self.new_calibrator = None
                return False
            
            # 启用新版本校准模式
            self.dual_calibration_mode = False  # 不再需要双校准模式
            
            # 显示加载成功信息
            new_info = self.new_calibrator.get_info()
            success_text = "新版本校准器加载成功!\n\n"
            success_text += f"新版本校准器:\n"
            success_text += f"  格式: {new_info['calibration_format']}\n"
            success_text += f"  系数形状: {new_info['coeffs_shape']}\n"
            success_text += "\n现在可以使用新版本校准功能！"
            
            QtWidgets.QMessageBox.information(self.parent, "加载成功", success_text)
            print("✅ 新版本校准器加载完成")
            
            return True
            
        except Exception as e:
            print(f"❌ 加载新版本校准器失败: {e}")
            QtWidgets.QMessageBox.critical(self.parent, "加载失败", f"加载新版本校准器失败:\n{str(e)}")
            return False
    
    def apply_new_calibration(self, raw_data_64x64):
        """应用新版本校准器校准并返回结果"""
        if not self.new_calibrator:
            return None
        
        try:
            results = {}
            
            # 🔧 使用原始零点修正逻辑：先对原始数据进行零点校正
            if self.taring_enabled and hasattr(self, 'zero_offset_matrix') and self.zero_offset_matrix is not None:
                # 使用原始零点修正逻辑：对原始数据进行零点校正
                # 注意：这里需要根据zero_offset_matrix的类型来决定如何应用
                if hasattr(self, 'zero_offset_matrix') and self.zero_offset_matrix is not None:
                    # 检查zero_offset_matrix是否与原始数据形状匹配
                    if self.zero_offset_matrix.shape == raw_data_64x64.shape:
                        # 如果zero_offset_matrix是原始数据的零点偏移，直接减去
                        raw_data_corrected = raw_data_64x64 - self.zero_offset_matrix
                        print(f"🔧 原始数据零点校正完成:")
                        print(f"   校正前范围: [{raw_data_64x64.min():.2f}, {raw_data_64x64.max():.2f}]")
                        print(f"   校正后范围: [{raw_data_corrected.min():.2f}, {raw_data_corrected.max():.2f}]")
                        print(f"   零点偏移矩阵范围: [{self.zero_offset_matrix.min():.2f}, {self.zero_offset_matrix.max():.2f}]")
                        
                        # 🆕 新增：将去皮后的原始数据也包含在结果中，让用户能看到去皮效果
                        results['raw'] = {
                            'data': raw_data_corrected,  # 显示去皮后的原始数据
                            'mean': float(raw_data_corrected.mean()),
                            'std': float(raw_data_corrected.std()),
                            'min': float(raw_data_corrected.min()),
                            'max': float(raw_data_corrected.max()),
                            'range': float(raw_data_corrected.max() - raw_data_corrected.min()),
                            'taring_applied': True,  # 标记已应用去皮
                            'original_range': [float(raw_data_64x64.min()), float(raw_data_64x64.max())]  # 保存原始范围
                        }
                        
                        print(f"✅ 去皮后的原始数据已添加到结果中，用户可以看到去皮效果")
                        
                    else:
                        # 如果形状不匹配，使用原始数据
                        raw_data_corrected = raw_data_64x64
                        print(f"⚠️ 零点偏移矩阵形状不匹配，使用原始数据")
                        
                        # 仍然返回原始数据，但标记未应用去皮
                        results['raw'] = {
                            'data': raw_data_64x64,
                            'mean': float(raw_data_64x64.mean()),
                            'std': float(raw_data_64x64.std()),
                            'min': float(raw_data_64x64.min()),
                            'max': float(raw_data_64x64.max()),
                            'range': float(raw_data_64x64.max() - raw_data_64x64.min()),
                            'taring_applied': False
                        }
                else:
                    raw_data_corrected = raw_data_64x64
                    print(f"⚠️ 零点偏移矩阵未设置，使用原始数据")
                    
                    # 返回原始数据，标记未应用去皮
                    results['raw'] = {
                        'data': raw_data_64x64,
                        'mean': float(raw_data_64x64.mean()),
                        'std': float(raw_data_64x64.std()),
                        'min': float(raw_data_64x64.min()),
                        'max': float(raw_data_64x64.max()),
                        'range': float(raw_data_64x64.max() - raw_data_64x64.min()),
                        'taring_applied': False
                    }
            else:
                raw_data_corrected = raw_data_64x64
                print(f"⚠️ 零点校正功能未启用，使用原始数据")
                
                # 返回原始数据，标记未应用去皮
                results['raw'] = {
                    'data': raw_data_64x64,
                    'mean': float(raw_data_64x64.mean()),
                    'std': float(raw_data_64x64.std()),
                    'min': float(raw_data_64x64.min()),
                    'max': float(raw_data_64x64.max()),
                    'range': float(raw_data_64x64.max() - raw_data_64x64.min()),
                    'taring_applied': False
                }
            
            # 应用新版本校准器（使用零点校正后的原始数据）
            new_calibrated = self.new_calibrator.apply_calibration(raw_data_corrected)
            results['new'] = {
                'data': new_calibrated,
                'mean': float(new_calibrated.mean()),
                'std': float(new_calibrated.std()),
                'min': float(new_calibrated.min()),
                'max': float(new_calibrated.max()),
                'range': float(new_calibrated.max() - new_calibrated.min())
            }
            
            # 🆕 新增：生成压力数据
            try:
                if hasattr(self.new_calibrator, 'convert_to_pressure') and callable(getattr(self.new_calibrator, 'convert_to_pressure')):
                    # 尝试转换为压力数据
                    pressure_data = self.new_calibrator.convert_to_pressure(new_calibrated)
                    
                    # 检查转换是否成功（如果返回的是原始数据，说明转换失败）
                    if pressure_data is not None and not np.array_equal(pressure_data, new_calibrated):
                        results['new']['pressure_data'] = pressure_data
                        print(f"✅ 压力数据生成成功:")
                        print(f"   压力范围: [{pressure_data.min():.2f}N, {pressure_data.max():.2f}N]")
                        print(f"   压力均值: {pressure_data.mean():.2f}N")
                    else:
                        print(f"⚠️ 压力转换失败，使用校准后数据作为压力数据")
                        # 如果没有压力转换，使用校准后的数据作为压力数据
                        results['new']['pressure_data'] = new_calibrated
                else:
                    print(f"⚠️ 新版本校准器不支持压力转换，使用校准后数据作为压力数据")
                    # 使用校准后的数据作为压力数据
                    results['new']['pressure_data'] = new_calibrated
                    
            except Exception as e:
                print(f"⚠️ 压力数据生成失败: {e}")
                # 使用校准后的数据作为压力数据
                results['new']['pressure_data'] = new_calibrated
            
            # 如果有压力数据，也包含在结果中
            if hasattr(self.new_calibrator, 'pressure_data') and self.new_calibrator.pressure_data is not None:
                results['new']['pressure_data'] = self.new_calibrator.pressure_data
            
            print(f"✅ 新版本校准完成:")
            print(f"   原始数据范围: [{raw_data_64x64.min():.2f}, {raw_data_64x64.max():.2f}]")
            print(f"   校准后数据范围: [{new_calibrated.min():.2f}, {new_calibrated.max():.2f}]")
            print(f"   校准后数据均值: {new_calibrated.mean():.2f}")
            print(f"   校准后数据标准差: {new_calibrated.std():.2f}")
            
            # 🆕 新增：确保raw键始终存在
            if 'raw' not in results:
                print(f"⚠️ 警告：results中缺少raw键，添加默认值")
                results['raw'] = {
                    'data': raw_data_64x64,
                    'mean': float(raw_data_64x64.mean()),
                    'std': float(raw_data_64x64.std()),
                    'min': float(raw_data_64x64.min()),
                    'max': float(raw_data_64x64.max()),
                    'range': float(raw_data_64x64.max() - raw_data_64x64.min()),
                    'taring_applied': False
                }
            
            print(f"✅ 最终结果检查：results包含的键: {list(results.keys())}")
            if 'raw' in results:
                print(f"   raw数据形状: {results['raw']['data'].shape}")
                print(f"   raw数据范围: [{results['raw']['data'].min():.2f}, {results['raw']['data'].max():.2f}]")
            
            return results
            
        except Exception as e:
            print(f"❌ 应用新版本校准失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_calibration_info(self):
        """获取校准信息"""
        info = {
            'calibration_coeffs': self.calibration_coeffs is not None,
            'calibration_format': self.calibration_format,
            'device': str(self.device),
            'dual_calibration_mode': self.dual_calibration_mode,
            'new_calibrator': None,
            'taring_enabled': self.taring_enabled,
            'zero_offset': self.zero_offset is not None,
            'zero_offset_matrix': self.zero_offset_matrix is not None
        }
        
        # 添加新版本校准器信息
        if self.new_calibrator is not None:
            info['new_calibrator'] = self.new_calibrator.get_info()
        
        return info
    
    def apply_taring_correction(self, calibrated_data):
        """应用去皮校正（逐点去皮）"""
        if self.taring_enabled and hasattr(self, 'zero_offset_matrix') and self.zero_offset_matrix is not None:
            print(f"🔧 应用逐点去皮校正:")
            print(f"   校正前均值: {calibrated_data.mean():.2f}")
            print(f"   校正前范围: [{calibrated_data.min():.2f}, {calibrated_data.max():.2f}]")

            # 逐点减去基准矩阵
            corrected_data = calibrated_data - self.zero_offset_matrix

            print(f"   基准矩阵均值: {self.zero_offset_matrix.mean():.2f}")
            print(f"   基准矩阵范围: [{self.zero_offset_matrix.min():.2f}, {self.zero_offset_matrix.max():.2f}]")
            print(f"   校正后均值: {corrected_data.mean():.2f}")
            print(f"   校正后范围: [{corrected_data.min():.2f}, {corrected_data.max():.2f}]")

            return corrected_data
        else:
            print(f"⚠️ 逐点去皮功能未启用或基准矩阵未设置")
            print(f"   taring_enabled: {getattr(self, 'taring_enabled', False)}")
            print(f"   zero_offset_matrix: {getattr(self, 'zero_offset_matrix', None)}")
        return calibrated_data

    def apply_pressure_taring_correction(self, pressure_data):
        """应用压力数据的去皮校正"""
        if self.taring_enabled and hasattr(self, 'zero_offset_matrix') and self.zero_offset_matrix is not None:
            # 检查新版本校准器是否有压力转换功能
            if self.new_calibrator is not None:
                try:
                    # 🔧 修复：动态计算压力基准，避免使用固定缓存值
                    # 每次重新计算基准压力，确保响应数据变化
                    pressure_flat = pressure_data.flatten()
                    baseline_percentile = 10  # 使用第10百分位数作为基准
                    pressure_baseline = np.percentile(pressure_flat, baseline_percentile)
                    
                    # 可选：保存基准压力用于调试，但不用于计算
                    if not hasattr(self, 'baseline_pressure_history'):
                        self.baseline_pressure_history = []
                    self.baseline_pressure_history.append(pressure_baseline)
                    
                    print(f"🔧 动态计算压力基准 (第{baseline_percentile}百分位数): {pressure_baseline:.2f}N")
                    if len(self.baseline_pressure_history) > 1:
                        last_baseline = self.baseline_pressure_history[-2]
                        change = pressure_baseline - last_baseline
                        print(f"   基准压力变化: {last_baseline:.2f}N → {pressure_baseline:.2f}N (变化: {change:+.2f}N)")

                    print(f"🔧 应用压力去皮校正:")
                    print(f"   压力校正前均值: {pressure_data.mean():.2f}N")
                    print(f"   压力校正前范围: [{pressure_data.min():.2f}N, {pressure_data.max():.2f}N]")

                    # 逐点减去压力基准
                    corrected_pressure = pressure_data - pressure_baseline

                    print(f"   压力基准: {pressure_baseline:.2f}N")
                    print(f"   压力校正后均值: {corrected_pressure.mean():.2f}N")
                    print(f"   压力校正后范围: [{corrected_pressure.min():.2f}N, {corrected_pressure.max():.2f}N]")

                    return corrected_pressure

                except Exception as e:
                    print(f"⚠️ 压力去皮校正失败: {e}")
                    return pressure_data
            else:
                print(f"⚠️ 新版本校准器未设置，无法进行压力去皮")
                return pressure_data
        else:
            print(f"⚠️ 去皮功能未启用或基准矩阵未设置，无法进行压力去皮")
            return pressure_data

    def get_calibrator(self):
        """获取校准器实例"""
        # 🆕 修改：只返回新版本校准器
        if self.new_calibrator is not None:
            return self.new_calibrator
        else:
            print("⚠️ 新版本校准器未加载")
            return None

    def has_calibrator(self):
        """检查是否有可用的校准器"""
        # 🆕 修改：只检查新版本校准器
        return (self.new_calibrator is not None)

    def clear_calibrators(self):
        """清除所有校准器"""
        # 🆕 修改：只清除新版本校准器
        self.new_calibrator = None
        self.dual_calibration_mode = False
        print("✅ 新版本校准器已清除")
    
    # 🆕 兼容性方法：为了保持向后兼容
    def load_dual_calibrators(self):
        """兼容性方法：加载双校准器（现在只加载新版本校准器）"""
        print("⚠️ 兼容性调用：load_dual_calibrators -> load_new_calibrator")
        return self.load_new_calibrator()
    
    def apply_dual_calibration(self, raw_data_64x64):
        """兼容性方法：应用双校准器校准（现在只应用新版本校准器）"""
        print("⚠️ 兼容性调用：apply_dual_calibration -> apply_new_calibration")
        return self.apply_new_calibration(raw_data_64x64)
    
    def get_dual_calibration_info(self):
        """兼容性方法：获取双校准器信息（现在只获取新版本校准器信息）"""
        print("⚠️ 兼容性调用：get_dual_calibration_info -> get_calibration_info")
        return self.get_calibration_info()
