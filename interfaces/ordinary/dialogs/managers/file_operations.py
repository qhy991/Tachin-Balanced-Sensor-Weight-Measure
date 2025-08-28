#!/usr/bin/env python3
"""
文件操作管理器

负责处理双校准比较对话框的文件操作，如保存截图等
"""

import time
from PyQt5 import QtWidgets


class FileOperationsManager:
    """文件操作管理器"""

    def __init__(self, dialog):
        self.dialog = dialog

    def save_screenshot(self):
        """保存截图"""
        try:
            filename = f"双校准器比较_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.dialog.grab().save(filename)
            print(f"✅ 截图已保存: {filename}")
            QtWidgets.QMessageBox.information(self.dialog, "保存成功", f"截图已保存为: {filename}")
        except Exception as e:
            print(f"❌ 保存截图失败: {e}")
            QtWidgets.QMessageBox.critical(self.dialog, "保存失败", f"保存截图失败:\n{str(e)}")

    def save_calibration_report(self, results, filename=None):
        """保存校准报告"""
        try:
            if filename is None:
                filename = f"校准报告_{time.strftime('%Y%m%d_%H%M%S')}.txt"

            with open(filename, 'w', encoding='utf-8') as f:
                f.write("双校准器比较报告\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # 写入统计信息
                if 'raw' in results:
                    f.write("原始数据统计:\n")
                    raw_data = results['raw']['data']
                    f.write(f"  数据范围: [{raw_data.min():.2f}, {raw_data.max():.2f}]\n")
                    f.write(f"  数据均值: {raw_data.mean():.2f}\n")
                    f.write(f"  数据标准差: {raw_data.std():.2f}\n\n")

                if 'new' in results:
                    f.write("新版本校准统计:\n")
                    new_data = results['new']['data']
                    f.write(f"  数据范围: [{new_data.min():.2f}, {new_data.max():.2f}]\n")
                    f.write(f"  数据均值: {new_data.mean():.2f}\n")
                    f.write(f"  数据标准差: {new_data.std():.2f}\n\n")

                    # 写入负值响应统计
                    if 'negative_response' in results:
                        nr_info = results['negative_response']
                        f.write("负值响应统计:\n")
                        f.write(f"  检测到负值点: {nr_info.get('count', 0)} 个\n")
                        if nr_info.get('has_negative', False):
                            f.write(f"  负值范围: [{nr_info['min_value']:.2f}, {nr_info['max_value']:.2f}]\n")
                            f.write(f"  负值均值: {nr_info['mean_value']:.2f}\n")
                        f.write("\n")

                # 写入区域信息
                if 'calibrated_regions' in results:
                    regions = results['calibrated_regions'].get('regions', [])
                    f.write(f"检测区域数量: {len(regions)}\n")
                    for i, region in enumerate(regions):
                        f.write(f"  区域 {i+1}:\n")
                        f.write(f"    面积: {region.get('area', 0)} 像素\n")
                        f.write(f"    中心: {region.get('center', (0, 0))}\n")
                        f.write(f"    平均压强: {region.get('avg_pressure', 0.0):.2f} kPa\n")
                        f.write(f"    紧凑度: {region.get('compactness', 0.0):.3f}\n")
                    f.write("\n")

                f.write("报告生成完成\n")

            print(f"✅ 校准报告已保存: {filename}")
            QtWidgets.QMessageBox.information(self.dialog, "保存成功", f"校准报告已保存为: {filename}")

        except Exception as e:
            print(f"❌ 保存校准报告失败: {e}")
            QtWidgets.QMessageBox.critical(self.dialog, "保存失败", f"保存校准报告失败:\n{str(e)}")

    def export_calibration_data(self, results, filename=None):
        """导出校准数据"""
        try:
            if filename is None:
                filename = f"校准数据_{time.strftime('%Y%m%d_%H%M%S')}.npz"

            data_to_save = {}

            if 'raw' in results:
                data_to_save['raw_data'] = results['raw']['data']

            if 'new' in results:
                data_to_save['new_calibrated_data'] = results['new']['data']
                if 'pressure_data' in results['new']:
                    data_to_save['pressure_data'] = results['new']['pressure_data']

            if 'change_data' in results:
                data_to_save['change_data'] = results['change_data']['data']

            if 'negative_response' in results:
                data_to_save['negative_response_data'] = results['negative_response']['data']

            # 保存区域信息
            if 'calibrated_regions' in results:
                regions = results['calibrated_regions'].get('regions', [])
                if regions:
                    # 将区域信息转换为可保存的格式
                    region_info = {
                        'count': len(regions),
                        'areas': [r.get('area', 0) for r in regions],
                        'centers': [r.get('center', (0, 0)) for r in regions],
                        'avg_pressures': [r.get('avg_pressure', 0.0) for r in regions]
                    }
                    data_to_save['region_info'] = region_info

            import numpy as np
            np.savez(filename, **data_to_save)

            print(f"✅ 校准数据已导出: {filename}")
            QtWidgets.QMessageBox.information(self.dialog, "导出成功", f"校准数据已导出为: {filename}")

        except Exception as e:
            print(f"❌ 导出校准数据失败: {e}")
            QtWidgets.QMessageBox.critical(self.dialog, "导出失败", f"导出校准数据失败:\n{str(e)}")

    def load_calibration_data(self, filename=None):
        """加载校准数据"""
        try:
            if filename is None:
                filename, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self.dialog,
                    "选择校准数据文件",
                    "",
                    "NumPy压缩文件 (*.npz);;所有文件 (*)"
                )

            if not filename:
                return None

            import numpy as np
            data = np.load(filename)

            results = {}

            if 'raw_data' in data:
                results['raw'] = {'data': data['raw_data']}

            if 'new_calibrated_data' in data:
                results['new'] = {'data': data['new_calibrated_data']}
                if 'pressure_data' in data:
                    results['new']['pressure_data'] = data['pressure_data']

            if 'change_data' in data:
                results['change_data'] = {'data': data['change_data']}

            if 'negative_response_data' in data:
                results['negative_response'] = {'data': data['negative_response_data']}

            print(f"✅ 校准数据已加载: {filename}")
            QtWidgets.QMessageBox.information(self.dialog, "加载成功", f"校准数据已从 {filename} 加载")

            return results

        except Exception as e:
            print(f"❌ 加载校准数据失败: {e}")
            QtWidgets.QMessageBox.critical(self.dialog, "加载失败", f"加载校准数据失败:\n{str(e)}")
            return None
