#!/usr/bin/env python3
"""
比较结果管理类

负责更新比较结果显示
"""

import traceback


class ComparisonManager:
    """比较结果管理器"""
    
    def __init__(self):
        self.comparison_label = None
    
    def set_comparison_label(self, label):
        """设置比较结果标签"""
        self.comparison_label = label
    
    def update_comparison_results(self, results):
        """更新比较结果"""
        try:
            comparison_text = ""
            
            # 🆕 修改：检查是否有足够的数据进行比较
            if 'raw' not in results:
                comparison_text = "比较结果: 无原始数据，无法进行比较"
                if self.comparison_label:
                    self.comparison_label.setText(comparison_text)
                return
            
            if 'old' in results and 'new' in results:
                old_stats = results['old']
                new_stats = results['new']
                raw_stats = results['raw']
                
                # 计算改善程度
                old_improvement = (raw_stats['std'] - old_stats['std']) / raw_stats['std'] * 100
                new_improvement = (raw_stats['std'] - new_stats['std']) / raw_stats['std'] * 100
                
                comparison_text = f"""双校准器比较结果:

原始数据标准差: {raw_stats['std']:.2f}

旧版本校准器:
  标准差: {old_stats['std']:.2f}
  改善程度: {old_improvement:.1f}%

新版本校准器:
  标准差: {new_stats['std']:.2f}
  改善程度: {new_improvement:.1f}%

结论: {'新版本校准器效果更好' if new_improvement > old_improvement else '旧版本校准器效果更好'}"""
                
            elif 'new' in results:
                # 🆕 修改：只有新版本校准器的情况
                new_stats = results['new']
                raw_stats = results['raw']
                
                # 计算改善程度
                new_improvement = (raw_stats['std'] - new_stats['std']) / raw_stats['std'] * 100
                
                comparison_text = f"""新版本校准器结果:

原始数据标准差: {raw_stats['std']:.2f}

新版本校准器:
  标准差: {new_stats['std']:.2f}
  改善程度: {new_improvement:.1f}%

状态: 新版本校准器已启用"""
                
            elif 'old' in results:
                # 🆕 修改：只有旧版本校准器的情况
                old_stats = results['old']
                raw_stats = results['raw']
                
                # 计算改善程度
                old_improvement = (raw_stats['std'] - old_stats['std']) / raw_stats['std'] * 100
                
                comparison_text = f"""旧版本校准器结果:

原始数据标准差: {raw_stats['std']:.2f}

旧版本校准器:
  标准差: {old_stats['std']:.2f}
  改善程度: {old_improvement:.1f}%

状态: 旧版本校准器已启用"""
                
            else:
                comparison_text = "比较结果: 没有可用的校准数据"
            
            # 更新显示
            if self.comparison_label:
                self.comparison_label.setText(comparison_text)
            else:
                print("⚠️ comparison_results_label 不存在")
                
        except Exception as e:
            print(f"❌ 更新比较结果失败: {e}")
            traceback.print_exc()
