
from scipy.ndimage import median_filter, gaussian_filter, zoom
import numpy as np


class Interpolation:

    def __init__(self, interp, blur, sensor_shape, use_median=False):
        self.interp = interp
        self.blur = blur
        self.use_median = use_median
        if blur > 16:
            raise Exception("过大的模糊参数")
        self.sensor_shape = sensor_shape

    def smooth(self, data):
        if isinstance(data, np.ndarray):
            data = data.astype(float)
            if self.use_median:
                data = median_filter(data, size=3, mode='constant', cval=0)
            if self.blur > 0:
                data = gaussian_filter(data, sigma=self.blur, mode='constant', cval=0)
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

if __name__ == '__main__':
    a = np.array([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10], [11, 12, 13, 14, 15]])
    print(median_filter(a, size=3, mode='constant', cval=0))
