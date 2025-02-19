
class AbstractSensorDriver:

    SENSOR_SHAPE = (0, 0)
    DATA_TYPE = '>i2'
    SCALE = 1.

    def __init__(self):
        pass

    def connect(self, port):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def get_last(self):
        raise NotImplementedError()
