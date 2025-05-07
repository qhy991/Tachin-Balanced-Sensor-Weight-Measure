
from scipy.ndimage import median_filter, gaussian_filter, zoom
import numpy as np


class Interpolation:

    def __init__(self, interp, blur, sensor_shape):
        self.interp = interp
        self.blur = blur
        if blur > 16:
            raise Exception("过大的模糊参数")
        self.sensor_shape = sensor_shape

    def smooth(self, data):
        if isinstance(data, np.ndarray):
            data = data.astype(float)
            if self.blur > 0:
                # data = median_filter(data, size=2 * int(self.blur) + 1)
                # data = median_filter(data, size=3)
                data = gaussian_filter(data, sigma=self.blur)
            data = self.zoom(data)
            return data
        else:
            data = data.copy()
            for k in data.keys():
                data[k] = self.smooth(data[k])
            return data

    def zoom(self, data):
        zoom_factors = self.interp
        zoomed_data = zoom(data, zoom_factors, order=1)
        return zoomed_data
