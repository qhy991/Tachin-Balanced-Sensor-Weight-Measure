# algorithm_class 是 sensor_calibrate.py 中 Algorithm 的子类
eps = 1e-12


class CalibrateAdaptor:

    def __init__(self, sensor_class, algorithm_class):
        sensor_shape = sensor_class.SENSOR_SHAPE
        self.algorithm_class = algorithm_class
        self.algorithm = algorithm_class(sensor_class, None)
        self.__sensor_shape = sensor_shape

    def load(self, path):
        content = ''.join(open(path, 'rt').readlines())
        assert self.algorithm.load(content)

    def transform_frame(self, voltage_frame):
        # 将一帧从原始数据变为标定结果
        # 原始数据为量化电压
        assert voltage_frame.shape == self.__sensor_shape
        force_frame = self.algorithm.transform_streaming(voltage_frame)
        # force_frame = average_2x2_blocks(force_frame)
        return force_frame

    def __bool__(self):
        return self.algorithm_class.IS_NOT_IDLE

