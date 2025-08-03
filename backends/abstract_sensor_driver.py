
class SensorDriver:

    SENSOR_SHAPE = (0, 0)  # 传感器形状。对使用SplitDataDict的，给出full_data形状
    DATA_TYPE = '>i2'  # 基础数据格式
    SCALE = 1.  # 某些情况有用

    def __init__(self):
        pass

    def connect(self, port) -> bool:
        """
        尝试连接硬件
        :param port: 硬件的识别号
        :return: 是否成功
        """
        raise NotImplementedError()

    def disconnect(self) -> bool:
        """
        尝试连接硬件
        :param
        :return: 是否成功
        """
        raise NotImplementedError()

    def get(self):
        """
        从缓存提取最早的数据，并移除它
        :return: np.ndarray或backends.tactile_split.SplitDataDict
        """
        raise NotImplementedError()

    def get_last(self):
        """
        从缓存提取最新的数据，并清空缓存
        :return: np.ndarray或backends.tactile_split.SplitDataDict
        """
        raise NotImplementedError()
