"""
AI校准适配器

负责加载和应用AI校准模型
"""

import os
import torch
import numpy as np


class AICalibrationAdapter:
    """AI校准适配器"""

    def __init__(self):
        self.coeffs = None
        self.data_mean = None
        self.data_std = None
        self.device = None
        self.is_loaded = False
        self.calibration_format = None
        # 新增：压力关系分析相关属性
        self.conversion_poly_coeffs = None
        self.pressure_range = None
        self.calibration_pressures = None

    def load_calibration(self, filepath):
        """加载AI校准模型"""
        try:
            if not os.path.exists(filepath):
                print(f"❌ AI校准文件不存在: {filepath}")
                return False

            # 加载校准包
            try:
                # 首先尝试使用 weights_only=False 加载（兼容旧版本）
                calibration_package = torch.load(filepath, weights_only=False)
            except Exception as e:
                print(f"⚠️ 使用 weights_only=False 加载失败: {e}")
                try:
                    # 如果失败，尝试使用 weights_only=True 加载
                    calibration_package = torch.load(filepath, weights_only=True)
                except Exception as e2:
                    print(f"❌ 使用 weights_only=True 加载也失败: {e2}")
                    raise e
            
            # 检查是新版本还是旧版本格式
            if isinstance(calibration_package, dict) and 'coeffs' in calibration_package:
                # 新版本格式：calibration_package.pt
                self.coeffs = calibration_package['coeffs']
                self.data_mean = calibration_package['data_mean']
                self.data_std = calibration_package['data_std']
                
                # 检查是否包含压力关系数据
                if 'conversion_poly_coeffs' in calibration_package:
                    self.conversion_poly_coeffs = calibration_package['conversion_poly_coeffs']
                    print(f"✅ 压力转换多项式系数加载成功: {self.conversion_poly_coeffs}")
                    
                    # 如果有压力数据，也加载
                    if 'calibration_pressures' in calibration_package:
                        self.calibration_pressures = calibration_package['calibration_pressures']
                        self.pressure_range = [float(self.calibration_pressures.min()), float(self.calibration_pressures.max())]
                        print(f"✅ 校准压力范围: {self.pressure_range[0]:.2f}N - {self.pressure_range[1]:.2f}N")
                
                self.calibration_format = 'new'
                print(f"✅ 新版本AI校准包加载成功，形状: {self.coeffs.shape}")
            else:
                # 旧版本格式：calibration_coeffs.pt
                self.coeffs = calibration_package
                self.data_mean = None
                self.data_std = None
                self.calibration_format = 'old'
                print(f"✅ 旧版本AI校准模型加载成功，形状: {self.coeffs.shape}")

            # 设置设备
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                print("✅ 使用GPU进行AI校准")
            else:
                self.device = torch.device("cpu")
                print("✅ 使用CPU进行AI校准")

            # 将系数移到指定设备
            self.coeffs = self.coeffs.to(self.device)
            if self.data_mean is not None:
                self.data_mean = self.data_mean.to(self.device)
            if self.data_std is not None:
                self.data_std = self.data_std.to(self.device)
                
            self.is_loaded = True
            return True

        except Exception as e:
            print(f"❌ 加载AI校准模型失败: {e}")
            return False

    def apply_calibration(self, raw_data):
        """应用AI校准到原始数据"""
        if not self.is_loaded or self.coeffs is None:
            return raw_data

        try:
            # 确保输入是64x64数组
            if raw_data.shape != (64, 64):
                print(f"⚠️ 输入数据形状错误: {raw_data.shape}，期望 (64, 64)")
                return raw_data

            # 转换为PyTorch张量
            raw_tensor = torch.from_numpy(raw_data).float().to(self.device)

            if self.calibration_format == 'new':
                # 新版本校准流程：标准化 → 校准 → 逆标准化
                print(f"🔧 新版本校准流程开始...")
                print(f"   原始数据范围: [{raw_tensor.min():.2f}, {raw_tensor.max():.2f}]")
                print(f"   数据均值范围: [{self.data_mean.min():.2f}, {self.data_mean.max():.2f}]")
                print(f"   数据标准差范围: [{self.data_std.min():.2f}, {self.data_std.max():.2f}]")
                
                # 1. 对新数据应用相同的标准化
                scaled_tensor = (raw_tensor - self.data_mean) / self.data_std
                print(f"   标准化后范围: [{scaled_tensor.min():.2f}, {scaled_tensor.max():.2f}]")
                
                # 2. 在标准化数据上应用校准函数
                x_flat = scaled_tensor.view(-1)
                x_poly = x_flat.unsqueeze(-1).pow(torch.arange(2, -1, -1, device=self.device))
                
                calibrated_flat_scaled = torch.sum(x_poly * self.coeffs, dim=1)
                print(f"   校准后标准化范围: [{calibrated_flat_scaled.min():.2f}, {calibrated_flat_scaled.max():.2f}]")
                
                # 3. 将结果逆变换回原始数据量级
                calibrated_flat_rescaled = calibrated_flat_scaled * self.data_std + self.data_mean
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

                # 应用校准函数：y = a*x^2 + b*x + c
                x = raw_flat
                a = self.coeffs[:, 0]  # 二次项系数
                b = self.coeffs[:, 1]  # 一次项系数
                c = self.coeffs[:, 2]  # 常数项

                # 并行计算校准
                calibrated_flat = a * x**2 + b * x + c

                # 恢复为64x64矩阵
                calibrated_tensor = calibrated_flat.view(64, 64)

                # 转换为numpy数组
                calibrated_data = calibrated_tensor.cpu().numpy()

                return calibrated_data

        except Exception as e:
            print(f"⚠️ AI校准应用失败: {e}")
            return raw_data

    def get_info(self):
        """获取AI校准信息"""
        if not self.is_loaded:
            return None

        info = {
            'is_loaded': True,
            'calibration_format': self.calibration_format,
            'coeffs_shape': self.coeffs.shape if self.coeffs is not None else None,
            'device': str(self.device),
            'coeffs_range': {
                'a': [float(self.coeffs[:, 0].min()), float(self.coeffs[:, 0].max())],
                'b': [float(self.coeffs[:, 1].min()), float(self.coeffs[:, 1].max())],
                'c': [float(self.coeffs[:, 2].min()), float(self.coeffs[:, 2].max())]
            } if self.coeffs is not None else None
        }
        
        if self.calibration_format == 'new':
            info['data_mean_range'] = [float(self.data_mean.min()), float(self.data_mean.max())]
            info['data_std_range'] = [float(self.data_std.min()), float(self.data_std.max())]
            
        return info
    
    def convert_to_pressure(self, calibrated_values):
        """将校准后的值转换为压力值（牛顿）"""
        if not self.is_loaded or self.conversion_poly_coeffs is None:
            print("⚠️ 无法转换压力：未加载压力转换系数")
            return calibrated_values
        
        try:
            # 使用二次多项式将校准值转换为压力
            # Pressure_N = a * V^2 + b * V + c
            a, b, c = self.conversion_poly_coeffs
            
            # 展平数据
            if isinstance(calibrated_values, np.ndarray):
                if calibrated_values.ndim == 2:
                    calibrated_flat = calibrated_values.flatten()
                else:
                    calibrated_flat = calibrated_values
            else:
                calibrated_flat = calibrated_values
            
            # 应用转换函数
            pressure_values = a * calibrated_flat**2 + b * calibrated_flat + c
            
            # 恢复原始形状
            if isinstance(calibrated_values, np.ndarray) and calibrated_values.ndim == 2:
                pressure_values = pressure_values.reshape(calibrated_values.shape)
            print("================================================")
            print(f"calibrated_values: {calibrated_values}")
            print("================================================")
            print(f"pressure_values: {pressure_values}")
            return pressure_values
            
        except Exception as e:
            print(f"⚠️ 压力转换失败: {e}")
            return calibrated_values
    
    def get_pressure_analysis_info(self):
        """获取压力关系分析信息"""
        if not self.is_loaded or self.conversion_poly_coeffs is None:
            return None

        info = {
            'has_pressure_conversion': True,
            'conversion_function': f"Pressure_N = {self.conversion_poly_coeffs[0]:.6f} * V² + {self.conversion_poly_coeffs[1]:.4f} * V + {self.conversion_poly_coeffs[2]:.4f}",
            'pressure_range': self.pressure_range,
            'calibration_pressures': self.calibration_pressures.tolist() if self.calibration_pressures is not None else None
        }

        return info

    def get_pressure_baseline(self, baseline_matrix):
        """获取压力基准（将校准基准转换为压力基准）

        Args:
            baseline_matrix: 校准基准矩阵（去皮前）

        Returns:
            pressure_baseline: 压力基准矩阵（牛顿单位）
        """
        if not self.is_loaded or self.conversion_poly_coeffs is None:
            print("⚠️ 校准器未加载或缺少压力转换系数，无法计算压力基准")
            return baseline_matrix

        try:
            # 将校准基准转换为压力基准
            pressure_baseline = self.convert_to_pressure(baseline_matrix)
            print(f"✅ 压力基准计算完成，范围: [{pressure_baseline.min():.2f}N, {pressure_baseline.max():.2f}N]")
            return pressure_baseline

        except Exception as e:
            print(f"⚠️ 压力基准计算失败: {e}")
            return baseline_matrix
