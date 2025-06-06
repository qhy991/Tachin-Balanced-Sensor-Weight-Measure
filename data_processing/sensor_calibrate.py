import numpy as np
import os
from scipy.interpolate import interp1d
from scipy.optimize import minimize
from data_processing.interpolation import Interpolation

abs_dir = os.path.dirname(os.path.abspath(__file__))


class Calibration:
    def __init__(self, sensor_class):
        self.cycles = []  # list for PointCycleData
        self.algorithm: Algorithm = Algorithm(sensor_class, self)
        self.transform = lambda x: x

    def __bool__(self):
        return len(self.cycles) > 0

    def set_log_scale(self):
        self.transform = np.log

    def set_linear_scale(self):
        self.transform = lambda x: x

    def clear(self):
        self.cycles.clear()

    def load_data_from_csv(self, path):
        self.clear()
        with open(path, 'rt') as f:
            loaded = np.loadtxt(f, delimiter=',', skiprows=1, usecols=[4, 7, 8])
            forces = loaded[:, 0]
            sensor_readings = loaded[:, 1] ** -1
            repetition = loaded[:, 2]
            for rep in np.unique(repetition):
                if rep > 0:
                    force = forces[repetition == rep]
                    sensor_reading = sensor_readings[repetition == rep]
                    self.cycles.append(PointCycleData(force, sensor_reading))


FORCE_SCALING = 100  # 力的单位转换系数。100表示标定文件里的1是0.01N


class PointCycleData:
    def __init__(self, force=np.ndarray((0, )), sensor_reading=np.ndarray((0, ))):
        assert force.ndim == sensor_reading.ndim == 1
        length = force.shape[0]
        assert length == sensor_reading.shape[0]
        self.force = force.copy()
        self.sensor_reading = sensor_reading.copy()
        self.force_est = None


class Algorithm:

    IS_NOT_IDLE = False

    def __init__(self, sensor_class, calibration, extern=None):
        self.sensor_class = sensor_class
        self.calibration = calibration
        pass

    def fit(self, ignore=None, extra=None):
        """
        根据存储的数据进行拟合
        :param ignore: 不拟合的数据序号
        :return: None
        """
        pass

    def transform(self, sensor_reading):
        """
        变换任意数据
        :param sensor_reading: 读数
        :return: 力
        """
        return sensor_reading

    def apply(self):
        """
        应用于存储的数据
        :return: None
        """
        for cycle in self.calibration.cycles:
            cycle: PointCycleData
            cycle.force_est = self.transform(cycle.sensor_reading)

    def clear_streaming(self):
        """
        清除实时变换记忆
        :return: None
        """
        pass

    def transform_streaming(self, sensor_reading):
        """
        实时变换数据
        :param sensor_reading: 读数
        :return: 力
        """
        return sensor_reading

    def save(self) -> str:
        """
        导出标定文件的文本
        :return: 标定文件文本
        """
        return ''

    def load(self, content: str) -> bool:
        """
        将标定文件文本读入
        :param content: 标定文件文本
        :return: None
        """
        return True

    def get_range(self):
        """
        获取标定范围
        :return: 标定范围
        """
        return [0, 1]

    def get_data(self, ignore):
        if ignore is None:
            ignore = []
        sensor_readings = []
        forces = []
        for i_c, cycle in enumerate(self.calibration.cycles):
            cycle: PointCycleData
            if not i_c in ignore:
                sensor_readings.append(cycle.sensor_reading)
                forces.append(cycle.force)
            else:
                print(f"Ignored cycle {i_c}")
        return sensor_readings, forces


class ManualDirectionLinearAlgorithm(Algorithm):

    IS_NOT_IDLE = False

    def __init__(self, sensor_class, calibration):
        super().__init__(sensor_class, calibration)
        self.interp_base = None
        self.record_voltage = 0.
        self.segments = np.ndarray((0, ))
        self.nodes_center = np.ndarray((0, ))
        self.nodes_hysteresis = np.ndarray((0, ))
        self.median = Interpolation(interp=1, blur=0.5, sensor_shape=sensor_class.SENSOR_SHAPE, use_median=False)
        #
        self.streaming_voltage = None
        self.streaming_trend = np.zeros(shape=sensor_class.SENSOR_SHAPE, dtype=float)

    def get_range(self):
        if self.nodes_center.__len__() == 0:
            return [0, 1]
        else:
            return [self.nodes_center[0], self.nodes_center[-1]]

    def clear_streaming(self):
        self.streaming_voltage = None
        self.streaming_trend[...] = 0.

    @staticmethod
    def calculate_estimated_force(sensor_reading, segments, nodes_center, nodes_hysteresis, record_voltage,
                                  use_hysteresis=True):
        assert nodes_center.ndim == 1
        assert nodes_hysteresis.ndim == 1
        assert nodes_center.shape[0] == nodes_hysteresis.shape[0]
        x_trend = 0.
        x_direction = np.zeros(sensor_reading.shape)
        for i in range(1, sensor_reading.__len__()):
            dist = abs(sensor_reading[i] - sensor_reading[i - 1])
            a = -dist / record_voltage
            fade_rate = np.exp(a)
            # 这段数据本身也正在衰减
            x_trend = x_trend * fade_rate \
                      + np.sign(sensor_reading[i] - sensor_reading[i - 1]) * (1 - fade_rate)
            x_direction[i] = x_trend
        interp_center = interp1d(segments, nodes_center, kind='linear',
                                 bounds_error=False, fill_value=(nodes_center[0], nodes_center[-1]))
        interp_hysteresis = interp1d(segments, nodes_hysteresis, kind='linear',
                                     bounds_error=False, fill_value=(nodes_hysteresis[0], nodes_hysteresis[-1]))
        if use_hysteresis:
            force_est = interp_center(sensor_reading) + interp_hysteresis(sensor_reading) * x_direction
        else:
            force_est = interp_center(sensor_reading)
        return force_est

    def calculate_estimated_force_streaming(self, sensor_reading):
        if self.streaming_voltage is not None:
            fade_rate = np.exp(-abs(sensor_reading - self.streaming_voltage) / self.record_voltage)
            # if np.any(np.isnan(fade_rate)):
            #     fade_rate[...] = 0.
            self.streaming_trend = self.streaming_trend * fade_rate \
                                     + np.sign(sensor_reading - self.streaming_voltage) * (-fade_rate + 1.)
        self.streaming_voltage = sensor_reading
        interp_center = interp1d(self.segments, self.nodes_center, kind='linear',
                                 bounds_error=False,
                                 fill_value=(self.nodes_center[0], self.nodes_center[-1]))
        interp_hysteresis = interp1d(self.segments, self.nodes_hysteresis, kind='linear',
                                     bounds_error=False,
                                     fill_value=(self.nodes_hysteresis[0], self.nodes_hysteresis[-1]))
        force_est = sensor_reading.__array_wrap__(interp_center(sensor_reading) + interp_hysteresis(sensor_reading) * self.streaming_trend)
        return force_est

    def fit(self, ignore=None, extra=None):
        # extern按_[0]从小到大排列
        if extra is None:
            return
        extra.sort(key=lambda _: _[0])
        print(extra)
        xx = [_[0] for _ in extra]
        yy = [_[1] for _ in extra]
        if not xx:
            return
        segments = np.array([10 ** _ for _ in xx])
        # 只使用xx分段线性插值
        sensor_readings, forces = self.get_data(ignore=ignore)
        # 寻找一组最优的节点

        def is_in_range(sensor_reading):
            return np.logical_and(sensor_reading >= segments[0], sensor_reading < segments[-1]).astype(float)

        def loss(encoded_nodes: np.ndarray, hysteresis_penalty=0.5):
            assert encoded_nodes.ndim == 1
            assert encoded_nodes.shape[0] % 2 == 1
            record_voltage = encoded_nodes[0]
            nodes_center = encoded_nodes[1::2]
            nodes_hysteresis = encoded_nodes[2::2]
            loss = 0.
            for sensor_reading, force in zip(sensor_readings, forces):
                forces_est = self.calculate_estimated_force(sensor_reading, segments,
                                                            nodes_center, nodes_hysteresis, record_voltage)
                loss += np.mean((force - forces_est) ** 2 * is_in_range(sensor_reading))
                forces_est_no_hysteresis = self.calculate_estimated_force(sensor_reading, segments,
                                                                          nodes_center, nodes_hysteresis,
                                                                          record_voltage,
                                                                          use_hysteresis=False)
                loss += hysteresis_penalty\
                        * np.mean((forces_est - forces_est_no_hysteresis) ** 2 * is_in_range(sensor_reading))

            return loss

        # 优化
        init = np.zeros((2 * segments.__len__() + 1, ))
        init[0] = 0.01
        init[1::2] = yy
        result = minimize(loss, init)
        nodes = result.x
        record_voltage = nodes[0]
        nodes_center = nodes[1::2]
        nodes_hysteresis = nodes[2::2]
        # 保存结果
        self.segments = segments
        self.record_voltage = record_voltage
        self.nodes_center = nodes_center
        self.nodes_hysteresis = nodes_hysteresis
        print("Optimized nodes:")
        print(f"\tSegments:{segments}")
        print(f"\tRecord voltage:{record_voltage}")
        print(f"\tCenter nodes:{nodes_center}")
        print(f"\tHysteresis nodes:{nodes_hysteresis}")

        self.apply()

    def transform(self, sensor_reading):
        force_est = self.calculate_estimated_force(sensor_reading, self.segments,
                                                   self.nodes_center,
                                                   self.nodes_hysteresis,
                                                   self.record_voltage)
        return force_est

    def transform_streaming(self, sensor_reading):
        force_est = self.calculate_estimated_force_streaming(self.median.smooth(sensor_reading))
        return force_est

    def save(self):
        text_all = ''
        text_all += f'{np.int16(self.record_voltage / self.sensor_class.SCALE)}\n'
        for segment, node_center, node_hysteresis in zip(self.segments, self.nodes_center, self.nodes_hysteresis):
            voltage = segment / self.sensor_class.SCALE
            pressure_center = node_center * FORCE_SCALING
            pressure_hysteresis = node_hysteresis * FORCE_SCALING
            text = f'{np.int16(voltage)}, {np.int16(pressure_center)}, {np.int16(pressure_hysteresis)}\n'
            text_all += text
        return text_all

    def load(self, content):
        lines = content.split('\n')
        self.record_voltage = int(lines[0]) * self.sensor_class.SCALE
        segments = []
        nodes_center = []
        nodes_hysteresis = []
        for line in lines[1:]:
            if not line:
                continue
            voltage, pressure_center, pressure_hysteresis = line.split(',')
            segments.append(int(voltage) * self.sensor_class.SCALE)
            nodes_center.append(float(pressure_center) / FORCE_SCALING)
            nodes_hysteresis.append(float(pressure_hysteresis) / FORCE_SCALING)
        self.segments = np.array(segments)
        self.nodes_center = np.array(nodes_center)
        self.nodes_hysteresis = np.array(nodes_hysteresis)
        return True

