#!/usr/bin/env python3
"""
配置管理类

负责用户偏好和设置的保存加载
"""

import json
import os
import traceback


class ConfigurationManager:
    """配置管理器"""
    
    def __init__(self):
        self.config_dir = os.path.join(os.path.expanduser("~"), ".sensor_calibration")
        self.config_file = os.path.join(self.config_dir, "dual_calibration_preferences.json")
        self.default_config = {
            'threshold_percentile': 80,
            'region_count': 2,
            'max_region_count': 10
        }
    
    def save_user_preferences(self, threshold_percentile, region_count, max_region_count):
        """保存用户配置偏好"""
        try:
            # 创建配置目录
            os.makedirs(self.config_dir, exist_ok=True)
            
            # 保存配置
            config = {
                'threshold_percentile': threshold_percentile,
                'region_count': region_count,
                'max_region_count': max_region_count
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 用户配置偏好已保存到: {self.config_file}")
            return True
            
        except Exception as e:
            print(f"⚠️ 保存用户配置偏好失败: {e}")
            traceback.print_exc()
            return False
    
    def load_user_preferences(self):
        """加载用户配置偏好"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 验证配置值
                validated_config = self._validate_config(config)
                print(f"✅ 用户配置偏好已从 {self.config_file} 加载")
                return validated_config
            else:
                print(f"⚠️ 配置文件不存在，使用默认配置")
                return self.default_config
                
        except Exception as e:
            print(f"⚠️ 加载用户配置偏好失败: {e}")
            traceback.print_exc()
            return self.default_config
    
    def _validate_config(self, config):
        """验证配置值"""
        validated = self.default_config.copy()
        
        # 验证阈值百分位数
        if 'threshold_percentile' in config:
            threshold = config['threshold_percentile']
            if isinstance(threshold, (int, float)) and 50 <= threshold <= 95:
                validated['threshold_percentile'] = int(threshold)
            else:
                print(f"⚠️ 无效的阈值百分位数: {threshold}，使用默认值: {validated['threshold_percentile']}")
        
        # 验证区域数量
        if 'region_count' in config:
            region_count = config['region_count']
            if isinstance(region_count, int) and 1 <= region_count <= validated['max_region_count']:
                validated['region_count'] = region_count
            else:
                print(f"⚠️ 无效的区域数量: {region_count}，使用默认值: {validated['region_count']}")
        
        # 验证最大区域数量
        if 'max_region_count' in config:
            max_region_count = config['max_region_count']
            if isinstance(max_region_count, int) and max_region_count >= 1:
                validated['max_region_count'] = max_region_count
                # 确保区域数量不超过最大限制
                if validated['region_count'] > validated['max_region_count']:
                    validated['region_count'] = validated['max_region_count']
                    print(f"⚠️ 区域数量超过最大限制，调整为: {validated['region_count']}")
            else:
                print(f"⚠️ 无效的最大区域数量: {max_region_count}，使用默认值: {validated['max_region_count']}")
        
        return validated
    
    def get_config_path(self):
        """获取配置文件路径"""
        return self.config_file
    
    def reset_to_defaults(self):
        """重置为默认配置"""
        try:
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
                print(f"✅ 配置文件已删除，将使用默认配置")
            return True
        except Exception as e:
            print(f"❌ 重置配置失败: {e}")
            return False
    
    def export_config(self, export_path):
        """导出配置到指定路径"""
        try:
            config = self.load_user_preferences()
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✅ 配置已导出到: {export_path}")
            return True
        except Exception as e:
            print(f"❌ 导出配置失败: {e}")
            return False
    
    def import_config(self, import_path):
        """从指定路径导入配置"""
        try:
            if os.path.exists(import_path):
                with open(import_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 验证并保存导入的配置
                validated_config = self._validate_config(config)
                self.save_user_preferences(
                    validated_config['threshold_percentile'],
                    validated_config['region_count'],
                    validated_config['max_region_count']
                )
                print(f"✅ 配置已从 {import_path} 导入")
                return True
            else:
                print(f"❌ 导入文件不存在: {import_path}")
                return False
        except Exception as e:
            print(f"❌ 导入配置失败: {e}")
            return False
