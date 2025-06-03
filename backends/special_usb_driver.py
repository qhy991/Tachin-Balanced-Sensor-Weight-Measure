from backends.usb_driver import LargeUsbSensorDriver
from collections import deque
from scipy.interpolate import interp1d

class SimulatedLowFrameUsbSensorDriver(LargeUsbSensorDriver):
    SENSOR_SHAPE = (64, 64)

    def __init__(self):
        super().__init__()
        self.COUNT = 3
        self.counter = 0
        self.buffered_data = deque(maxlen=2)

    def get(self):
        data, t = super().get()
        if data is not None:
            if self.counter == self.COUNT:
                self.buffered_data.append(data)
                self.counter = 0
            self.counter += 1
            if self.buffered_data.__len__() == 2:
                data_ret = interp1d(
                    [0., 1.], [self.buffered_data[0], self.buffered_data[1]], axis=0)(self.counter / self.COUNT)
                # data_ret = self.buffered_data[1]
                return data_ret, t
            else:
                return None, None
        else:
            return None, None
