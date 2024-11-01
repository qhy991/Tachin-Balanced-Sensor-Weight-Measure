
from PIL import Image, ImageFilter
from scipy.signal import convolve2d
import numpy as np


class Interpolation:

    def __init__(self, interp, blur, sensor_shape):
        self.interp = interp
        if blur > 8:
            raise Exception("过大的模糊参数")
        if blur > 0:
            kernel_size = np.ceil(blur * 2) * 2 + 1
            coord = np.arange(kernel_size) - kernel_size // 2 + 0.5
            dist_sq = coord.reshape(-1, 1) ** 2 + coord.reshape(1, -1) ** 2
            kernel = np.exp(-dist_sq / blur)
            self.blur_kernel = kernel / np.sum(kernel)
        else:
            self.blur_kernel = None
        self.sensor_shape = sensor_shape

    def smooth(self, data):
        if isinstance(data, np.ndarray):
            data = data.astype(np.float)
            if self.blur_kernel is not None:
                data = convolve2d(data, self.blur_kernel, mode='same', boundary='fill', fillvalue=-6.)
            im_interp = Image.fromarray(data).resize(size=(self.interp * data.shape[1],
                                                           self.interp * data.shape[0]),
                                                     resample=Image.BILINEAR)
            im_interp = np.array(im_interp)
            return im_interp
        else:
            data = data.copy()
            for k in data.keys():
                data[k] = self.smooth(data[k])
            return data
