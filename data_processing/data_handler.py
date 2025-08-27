import os
import warnings
from collections import deque
import numpy as np
import atexit
from . import filters as preprocessing
from .interpolation import Interpolation
import json
import sqlite3
from .convert_data import convert_db_to_csv
from ..config import config
import threading
from .calibrate_adaptor import CalibrateAdaptor
from .calibration.sensor_calibrate import Algorithm, ManualDirectionLinearAlgorithm
import time
from .convert_data import extract_data, dataframe_to_numpy
import torch

# 添加对balance-sensor校准格式的支持
class BalanceSensorCalibrationAdapter:
    """适配balance-sensor校准格式的适配器"""
    
    def __init__(self):
        self.calibration_data = None
        self.calibration_map = None
        self.coefficient = 1.0
        self.bias = 0.0
        self.is_loaded = False
    
    def load_calibration(self, filepath):
        """加载balance-sensor格式的校准文件"""
        try:
            if filepath.endswith('.json'):
                self._load_json_calibration(filepath)
            elif filepath.endswith('.npy'):
                self._load_numpy_calibration(filepath)
            elif filepath.endswith('.csv'):
                self._load_csv_calibration(filepath)
            else:
                raise ValueError(f"不支持的校准文件格式: {filepath}")
            
            self.is_loaded = True
            print(f"✅ 已加载balance-sensor校准文件: {filepath}")
            return True
            
        except Exception as e:
            print(f"⚠️ 加载balance-sensor校准文件失败: {e}")
            return False
    
    def _load_json_calibration(self, filepath):
        """加载JSON格式校准文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            self.calibration_data = json.load(f)
        
        # 检查是否是position_calibration_data.json格式
        if 'positions' in self.calibration_data:
            # 这是position_calibration_data.json格式
            positions = self.calibration_data['positions']
            if 'center' in positions:
                # 使用中心位置的校准参数
                center_cal = positions['center']['calibration']
                self.coefficient = float(center_cal['slope'])
                self.bias = float(center_cal['intercept'])
                print(f"✅ 从position_calibration_data.json加载校准参数:")
                print(f"   - 系数 (slope): {self.coefficient}")
                print(f"   - 偏置 (intercept): {self.bias}")
            else:
                # 如果没有中心位置，使用第一个可用位置
                first_position = list(positions.values())[0]
                if 'calibration' in first_position:
                    cal = first_position['calibration']
                    self.coefficient = float(cal['slope'])
                    self.bias = float(cal['intercept'])
                    print(f"✅ 从position_calibration_data.json加载校准参数 (使用{first_position['name']}):")
                    print(f"   - 系数 (slope): {self.coefficient}")
                    print(f"   - 偏置 (intercept): {self.bias}")
        else:
            # 标准格式
            if 'calibration_map' in self.calibration_data:
                self.calibration_map = np.array(self.calibration_data['calibration_map'])
            
            if 'coefficient' in self.calibration_data:
                self.coefficient = float(self.calibration_data['coefficient'])
            
            if 'bias' in self.calibration_data:
                self.bias = float(self.calibration_data['bias'])
    
    def _load_numpy_calibration(self, filepath):
        """加载NumPy格式校准文件"""
        data = np.load(filepath, allow_pickle=True)
        
        # 检查数据格式
        if data.shape == (64, 64):
            # 这是一个64x64的校准映射数组
            self.calibration_map = data.astype(np.float32)
            self.coefficient = 1.0  # 默认系数
            self.bias = 0.0  # 默认偏置
            print(f"✅ 从NumPy文件加载64x64校准映射:")
            print(f"   - 映射形状: {self.calibration_map.shape}")
            print(f"   - 映射均值: {np.mean(self.calibration_map):.4f}")
            print(f"   - 映射范围: [{np.min(self.calibration_map):.4f}, {np.max(self.calibration_map):.4f}]")
        elif isinstance(data, np.ndarray) and data.dtype == object:
            # 这是一个包含字典的数组
            data_dict = data.item()
            self.calibration_data = data_dict
            
            if 'calibration_map' in data_dict:
                self.calibration_map = data_dict['calibration_map']
            
            if 'coefficient' in data_dict:
                self.coefficient = float(data_dict['coefficient'])
            
            if 'bias' in data_dict:
                self.bias = float(data_dict['bias'])
        else:
            print(f"⚠️ 未知的NumPy文件格式: {data.shape}, {data.dtype}")
            return False
        
        return True
    
    def _load_csv_calibration(self, filepath):
        """加载CSV格式校准文件"""
        # 简单的CSV格式支持，假设第一行是系数和偏置
        data = np.loadtxt(filepath, delimiter=',', skiprows=1)
        if len(data.shape) == 2:
            self.calibration_map = data
        else:
            # 如果只有一行，假设是系数和偏置
            if len(data) >= 2:
                self.coefficient = float(data[0])
                self.bias = float(data[1])
    
    def apply_calibration(self, raw_data):
        """应用校准到原始数据"""
        if not self.is_loaded:
            return raw_data
        
        calibrated_data = raw_data.copy()
        
        # 应用校准映射（如果存在）
        if self.calibration_map is not None and raw_data.shape == self.calibration_map.shape:
            calibrated_data = raw_data * self.calibration_map
        
        # 应用线性校准：y = kx + b
        calibrated_data = self.coefficient * calibrated_data + self.bias
        
        return calibrated_data
    
    def get_info(self):
        """获取校准信息"""
        if not self.is_loaded:
            return None
        
        info = {
            'is_loaded': True,
            'coefficient': self.coefficient,
            'bias': self.bias
        }
        
        if self.calibration_map is not None:
            info['calibration_map_shape'] = self.calibration_map.shape
            info['calibration_map_mean'] = float(np.mean(self.calibration_map))
        
        return info

class AICalibrationAdapter:
    """AI校准适配器"""

    def __init__(self):
        self.coeffs = None
        self.device = None
        self.is_loaded = False

    def load_calibration(self, filepath):
        """加载AI校准模型"""
        try:
            if not os.path.exists(filepath):
                print(f"❌ AI校准文件不存在: {filepath}")
                return False

            # 加载PyTorch模型
            self.coeffs = torch.load(filepath)
            print(f"✅ 成功加载AI校准系数，形状: {self.coeffs.shape}")

            # 设置设备
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                print("✅ 使用GPU进行AI校准")
            else:
                self.device = torch.device("cpu")
                print("✅ 使用CPU进行AI校准")

            # 将系数移到指定设备
            self.coeffs = self.coeffs.to(self.device)
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
            raw_flat = raw_tensor.view(-1)  # 展平为4096维向量

            # 应用二次多项式校准: y = a*x^2 + b*x + c
            x = raw_flat
            a = self.coeffs[:, 0]  # 二次项系数
            b = self.coeffs[:, 1]  # 一次项系数
            c = self.coeffs[:, 2]  # 常数项

            # 并行计算校准
            calibrated_flat = a * x**2 + b * x + c

            # 恢复为64x64矩阵
            calibrated_tensor = calibrated_flat.view(64, 64)
            calibrated_data = calibrated_tensor.cpu().numpy()

            return calibrated_data

        except Exception as e:
            print(f"⚠️ AI校准应用失败: {e}")
            return raw_data

    def get_info(self):
        """获取AI校准信息"""
        if not self.is_loaded:
            return None

        return {
            'is_loaded': True,
            'coeffs_shape': self.coeffs.shape if self.coeffs is not None else None,
            'device': str(self.device),
            'coeffs_range': {
                'a': [float(self.coeffs[:, 0].min()), float(self.coeffs[:, 0].max())],
                'b': [float(self.coeffs[:, 1].min()), float(self.coeffs[:, 1].max())],
                'c': [float(self.coeffs[:, 2].min()), float(self.coeffs[:, 2].max())]
            } if self.coeffs is not None else None
        }

VALUE_DTYPE = float


class DataHandler:

    ZERO_LEN_REQUIRE = 4
    MAX_IN = 16

    def __init__(self, template_sensor_driver, max_len=64):
        """
        数据枢纽
        :param template_sensor_driver: SensorDriver的构造函数
        :param max_len: 保存数据长度。注意与SensorDriver自身的缓冲无关
        """
        self.max_len = max_len
        self.driver = template_sensor_driver()  # 传感器驱动
        # 滤波器。调用顺序见trigger方法
        self.filter_time = preprocessing.Filter(template_sensor_driver)  # 当前的时间滤波。可被设置
        self.filter_frame = preprocessing.Filter(template_sensor_driver)  # 当前的空间滤波。可被设置
        self.filters_for_each = None
        self.filter_after_zero = preprocessing.Filter(template_sensor_driver)
        self.filters_for_each_after_zero = None
        self.preset_filters = preprocessing.build_preset_filters(template_sensor_driver)  # 下拉菜单里可设置的滤波器
        self.interpolation = Interpolation(1, 0., template_sensor_driver.SENSOR_SHAPE)  # 插值。可被设置
        # region_count为0表示为单片；否则为分片
        try:
            self.region_indices = template_sensor_driver.range_mapping.keys()
        except AttributeError:
            self.region_indices = []
        # 标定
        self.calibration_adaptor: CalibrateAdaptor = CalibrateAdaptor(self.driver, Algorithm)  # 标定器
        self.using_calibration = False
        
        # 添加balance-sensor校准适配器
        self.balance_calibration_adaptor = BalanceSensorCalibrationAdapter()
        self.using_balance_calibration = False

        # 添加AI校准适配器
        self.ai_calibration_adaptor = AICalibrationAdapter()
        self.using_ai_calibration = False
        # 数据容器
        self.begin_time = None
        self.data = deque(maxlen=self.max_len)  # 直接从SensorDriver获得的数据
        self.filtered_data = deque(maxlen=self.max_len)  # 直接从SensorDriver获得的数据
        self.value_before_zero = deque(maxlen=self.max_len)
        self.value = deque(maxlen=self.max_len)  # 经过所有处理，但未通过interpolation，也未做对数尺度变换。对自研卡，未开启标定时，是电阻(kΩ)的倒数
        self.time = deque(maxlen=self.max_len)  # 从connect后首个采集点开始到现在的时间
        self.time_ms = deque(maxlen=self.max_len)  # ms上的整型。通讯专用
        self.zero = np.zeros(template_sensor_driver.SENSOR_SHAPE, dtype=template_sensor_driver.DATA_TYPE)  # 零点
        self.value_zero = np.zeros(template_sensor_driver.SENSOR_SHAPE, dtype=template_sensor_driver.DATA_TYPE)
        self.maximum = deque(maxlen=self.max_len)  # 峰值
        self.summed = deque(maxlen=self.max_len)  # 总值
        self.tracings = deque(maxlen=self.max_len)  # 追踪点。Experimental修改：多个追踪点
        self.t_tracing = deque(maxlen=self.max_len)  # 追踪点的时间。由于更新追踪点时会清空，故单独记录
        self.tracing_points = []  # 当前的追踪点。Experimental修改：多个追踪点
        self.lock = threading.Lock()
        self.zero_set = False
        # 保存
        self.output_file = None
        self.cursor = None
        self.path_db = None
        # 退出时断开
        atexit.register(self.disconnect)
        #
        self.dump_interval = config.get("dump_interval", 10.) * 0.001
        self.next_dump = 0.
        #
        self.play_data = None
        self.play_flag = False
        self.play_complete_flag = False

    # 保存功能。部分保存功能还有待测试
    def link_output_file(self, path):
        # 采集到文件时，打开文件
        try:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            self.output_file = sqlite3.connect(path)
            self.path_db = path
            self.cursor = self.output_file.cursor()
            if not self.region_indices:  # 无分区
                command = ('create table data (time float, time_after_begin float, '
                          + ', '.join([f'data_row_{i} text'
                                      for i in range(self.driver.SENSOR_SHAPE[0])
                                      ]) + ','
                          + ', '.join(['config_zero_set int', 'config_using_calibration int',
                                       'feature_summed int', 'feature_maximum int'])
                           + ')')
            else:
                # SplitDataDict 模式
                command = ('create table data (time float, time_after_begin float, '
                          + ', '.join([f'data_region_{i}_row_{j} text'
                                       for i in self.region_indices
                                       for j in range(self.driver.get_zeros(i).shape[0])
                                       ]) + ','
                            + ', '.join(['config_zero_set int', 'config_using_calibration int',
                                         'feature_summed int', 'feature_maximum int'])
                           + ')')
            self.cursor.execute(command)

        except PermissionError as e:
            raise Exception('文件无法写入。可能正被占用')
        except Exception as e:
            raise e

    def write_to_file(self, time_now, time_after_begin, data, summed, maximum):
        #
        if self.output_file is not None:
            if time_after_begin - self.next_dump > 2 * self.dump_interval:
                self.next_dump = 0.
            if self.next_dump == 0.:
                self.next_dump = time_after_begin
            if time_after_begin >= self.next_dump:
                if not self.region_indices:
                    command = (f'insert into data values ({time_now}, {time_after_begin}, '
                               + ', '.join(['\"' + json.dumps(_.tolist()) + '\"' for _ in data]) + ','
                               + ', '.join([str(_) for _ in [int(self.zero_set), int(self.using_calibration),
                                                             summed, maximum]]) +
                               ')')
                else:
                    # SplitDataDict 模式
                    data_list = sum([['\"' + json.dumps(_.tolist()) + '\"' for _ in data[k]] for k in data.keys()], [])
                    command = (f'insert into data values ({time_now}, {time_after_begin}, '
                               + ', '.join(data_list) + ','
                               + ', '.join([str(_) for _ in [int(self.zero_set), int(self.using_calibration)]]) + ','
                               + ', '.join([str(_) for _ in [summed, maximum]]) + ')')
                self.cursor.execute(command)
                self.commit_file()
                self.next_dump = self.next_dump + self.dump_interval

    def commit_file(self):
        if self.output_file is not None:
            self.output_file.commit()

    def close_output_file(self):
        if self.output_file:
            self.commit_file()
            output_file = self.output_file
            self.output_file = None
            self.cursor = None
            output_file.close()
            convert_db_to_csv(self.path_db)
            self.path_db = None

    @property
    def saving_file(self):
        return bool(self.output_file)

    # 保存功能结束

    def clear(self):
        self.lock.acquire()
        self.data.clear()
        self.filtered_data.clear()
        self.value_before_zero.clear()
        self.value.clear()
        self.time.clear()
        self.time_ms.clear()
        self.maximum.clear()
        self.summed.clear()
        self.tracings.clear()
        self.t_tracing.clear()
        self.lock.release()

    def connect(self, port):
        self.begin_time = None
        flag = self.driver.connect(port)  # 会因import的驱动类型而改变
        return flag

    def disconnect(self):
        self.close_output_file()
        self.clear()
        flag = self.driver.disconnect()
        return flag

    # 重放

    def read_data_from_db(self, path):
        """
        从 SQLite 数据库读取数据
        :param path: 数据库文件路径
        :return: 包含所有数据的列表
        """
        try:
            data = extract_data(path)
            data = dataframe_to_numpy(data)

            # 播放模式参数
            self.play_fps = 100.0  # 默认帧率（帧/秒）
            self.play_interval = 1.0 / self.play_fps  # 每帧持续时间（秒）
            self.play_start_time = None  # 播放模式起始时间（首次播放时初始化）
            self.play_frame_count = 0  # 已播放帧数
            self.last_frame_time = None  # 上一帧的虚构时间

            data = np.array(data)
            self.play_data = data

        except FileNotFoundError:
            raise Exception('指定的数据库文件不存在')
        except sqlite3.Error as e:
            raise Exception(f'数据库操作错误: {str(e)}')
        except Exception as e:
            raise Exception(f'读取文件时发生未知错误: {str(e)}')

    def get_data(self):
        if self.play_flag == False:
            data, time_now = self.driver.get()
        else:  # 进入播放模式
            # 初始化播放起始时间
            if self.play_start_time is None:
                self.play_start_time = time.time()  # 使用系统时间作为起始点
                self.last_frame_time = self.play_start_time

            # 计算当前帧的预期时间
            current_expected_time = self.play_start_time + self.play_frame_count * self.play_interval

            # 等待直到达到预期时间（控制帧率）
            while time.time() < current_expected_time:
                time.sleep(0.001)  # 短暂休眠避免CPU占用过高

            # 更新时间戳和帧计数
            self.play_frame_count += 1
            time_now = current_expected_time  # 使用预期时间作为time_now
            self.last_frame_time = time_now
            self.play_frame_count += 1
            time_now = self.play_start_time + self.play_frame_count * self.play_interval
            # 尚未播放完
            if self.play_data.shape[0] >= 2:
                # 切一帧来
                data = self.play_data[0]
                self.play_data = self.play_data[1:]
            else:
                # 播放已经结束
                self.play_complete_flag = True
                self.play_flag = False
                data = None
        return data, time_now

    def trigger(self):
        """
        核心触发
        :return: None
        """
        count_in = self.MAX_IN  # 一次触发最大读取数据量。避免提取数据的速度赶不上SensorDriver累积数据速度
        while count_in:
            count_in -= 1
            data, time_now = self.get_data()  # 从其缓存中最早的数据开始逐一提取和处理
            if data is not None:
                # 以下为各类滤波器处理顺序
                _ = self.filter_time.filter(self.filter_frame.filter(data))
                if self.filters_for_each is not None:
                    for k in self.filters_for_each:
                        _[k] = self.filters_for_each[k].filter(_[k])
                
                # 应用原始校准（如果启用）
                value = self.calibration_adaptor.transform_frame(_.astype(float) * self.driver.SCALE)
                
                # # 应用balance-sensor校准（如果启用）
                # if self.using_balance_calibration:
                #     value = self.balance_calibration_adaptor.apply_calibration(value)

                # 应用AI校准（如果启用）
                if self.using_ai_calibration:
                    value = self.ai_calibration_adaptor.apply_calibration(value)
                
                value = self.interpolation.smooth(value)
                value_before_zero = value
                _ = self.filter_after_zero.filter(value_before_zero - self.zero)
                if self.filters_for_each_after_zero is not None:
                    for k in self.filters_for_each_after_zero:
                        _[k] = self.filters_for_each_after_zero[k].filter(_[k])
                value = np.maximum(_, 0.)
                # 时间
                if self.begin_time is None:
                    self.begin_time = time_now
                time_after_begin = time_now - self.begin_time
                # 导出基础特征
                summed = np.sum(value)
                maximum = np.max(value)
                tracings = []
                for tracing_point in self.tracing_points:
                    tracing = np.mean(np.asarray(value)[
                                                       tracing_point[0] * self.interpolation.interp
                                                       : (tracing_point[0] + 1) * self.interpolation.interp,
                                                       tracing_point[1] * self.interpolation.interp
                                                       : (tracing_point[1] + 1) * self.interpolation.interp])
                    tracings.append(tracing)

                self.lock.acquire()
                self.data.append(data)
                self.value_before_zero.append(value_before_zero)
                self.value.append(value)
                self.time.append(time_after_begin)
                self.t_tracing.append(time_after_begin)
                self.time_ms.append(np.array([(time_after_begin * 1e3) % 10000], dtype='>i2'))  # ms
                self.maximum.append(maximum)
                self.summed.append(summed)
                self.tracings.append(tracings)
                self.lock.release()
                #
                try:
                    self.write_to_file(time_now, time_after_begin, data, summed, maximum)
                except TypeError:
                    warnings.warn('未完成保存模块')
            else:
                break
        # print(f"取得数据{self.MAX_IN - count_in}条")

    def set_zero(self) -> bool:
        """
        置零
        :return: 是否成功
        """
        if self.value_before_zero.__len__() >= self.ZERO_LEN_REQUIRE + self.filter_time.order * 2:
            self.zero_set = True
            self.zero = np.mean(np.maximum(np.asarray(self.value_before_zero)[-self.ZERO_LEN_REQUIRE:, ...], 0), axis=0)
            self.clear()
            print('置零成功')
            return True
        else:
            # print('数据不足，无法置零')
            return False

    def abandon_zero(self):
        """
        解除置零
        :return:
        """
        self.zero = np.zeros([_ * self.interpolation.interp for _ in self.driver.SENSOR_SHAPE],
                             dtype=self.driver.DATA_TYPE)
        self.zero_set = False

    def set_filter(self, filter_name_frame, filter_name_time):
        """
        在预设模组中选择滤波器。注意空间滤波器和时间滤波器实际没有约束
        :param filter_name_frame: 空间滤波器名
        :param filter_name_time: 时间滤波器名
        :return:
        """
        try:
            self.filter_frame = self.preset_filters[filter_name_frame]()
            self.filter_time = self.preset_filters[filter_name_time]()
            self.abandon_zero()
            self.clear()
        except KeyError:
            raise Exception('指定的滤波器不存在')

    def set_tracing(self, i, j):
        """
        添加追踪点
        :param i: 行标。输入超限值清除追踪
        :param j: 列标。输入超限值清除追踪
        :return: 正在追踪的点数
        """
        # 鼠标选点时，设置追踪点
        if 0 <= i < self.driver.SENSOR_SHAPE[0] and 0 <= j < self.driver.SENSOR_SHAPE[1]:
            if (i, j) in self.tracing_points:
                # 如果点已存在，则删除
                self.tracing_points.remove((i, j))
            else:
                self.tracing_points.append((i, j))
            self.t_tracing.clear()
            self.tracings.clear()
        else:
            self.tracing_points.clear()
            self.t_tracing.clear()
            self.tracings.clear()
        return self.tracing_points.__len__()

    def set_interpolation_and_blur(self, interpolate, blur):
        assert interpolate == int(interpolate)
        assert 1 <= interpolate <= 8
        assert blur == float(blur)
        assert 0. <= blur <= 8.
        self.interpolation = Interpolation(interpolate, blur, self.driver.SENSOR_SHAPE)
        self.abandon_zero()
        self.clear()

    def set_calibrator(self, path, forced_to_use_clb=False):
        try:
            self.calibration_adaptor = CalibrateAdaptor(self.driver, ManualDirectionLinearAlgorithm)
            self.calibration_adaptor.load(path, forced_to_use_clb)
            self.abandon_zero()
            self.clear()
            self.using_calibration = True
            return True
        except Exception as e:
            self.abandon_calibrator()
            raise e

    def abandon_calibrator(self):
        """
        解除标定
        :return:
        """
        self.using_calibration = False
        self.calibration_adaptor = CalibrateAdaptor(self.driver, Algorithm)
    
    def set_balance_calibration(self, filepath):
        """
        设置balance-sensor校准文件
        :param filepath: 校准文件路径
        :return: 是否成功
        """
        try:
            success = self.balance_calibration_adaptor.load_calibration(filepath)
            if success:
                self.using_balance_calibration = True
                print(f"✅ 已启用balance-sensor校准: {filepath}")
                return True
            else:
                print(f"❌ 启用balance-sensor校准时失败: {filepath}")
                return False
        except Exception as e:
            print(f"⚠️ 设置balance-sensor校准时出错: {e}")
            return False
    
    def abandon_balance_calibration(self):
        """
        解除balance-sensor校准
        :return:
        """
        self.using_balance_calibration = False
        self.balance_calibration_adaptor = BalanceSensorCalibrationAdapter()
        print("✅ 已解除balance-sensor校准")
    
    def get_balance_calibration_info(self):
        """
        获取balance-sensor校准信息
        :return: 校准信息字典
        """
        return self.balance_calibration_adaptor.get_info()

    def set_ai_calibration(self, filepath):
        """
        设置AI校准模型
        :param filepath: AI校准模型文件路径
        :return: 是否成功
        """
        try:
            success = self.ai_calibration_adaptor.load_calibration(filepath)
            if success:
                self.using_ai_calibration = True
                print(f"✅ 已启用AI校准: {filepath}")
                return True
            else:
                print(f"❌ 启用AI校准失败: {filepath}")
                return False
        except Exception as e:
            print(f"⚠️ 设置AI校准时出错: {e}")
            return False

    def abandon_ai_calibration(self):
        """
        解除AI校准
        :return:
        """
        self.using_ai_calibration = False
        self.ai_calibration_adaptor = AICalibrationAdapter()
        print("✅ 已解除AI校准")

    def get_ai_calibration_info(self):
        """
        获取AI校准信息
        :return: 校准信息字典
        """
        return self.ai_calibration_adaptor.get_info()
