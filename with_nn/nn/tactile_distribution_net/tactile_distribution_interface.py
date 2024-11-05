import time

from with_nn.nn.tactile_distribution_net.tactile_distribution_model import DistributionToMaterialType as Model
import tensorflow as tf
import numpy as np
import os
import threading
# 当前文件路径
folder = os.path.dirname(os.path.abspath(__file__))

SCALE = (32768. * 25. / 5.) ** -1


class TactileDistributionInterface:

    def __init__(self, use_log):
        # 模式
        self.use_log = use_log
        #
        try:
            self.model = Model.load(os.path.join(folder, r'..\..\model_using'))
            print('加载触觉感知模型成功')
        except:
            print('加载触觉感知模型失败')
        self.model_out_translate = np.zeros((self.model.num_class, ))
        self.model_out_translate[...] = [0., 1., 0.5]
        self.smooth_rate = 0.75
        self.summed_prev = None
        # async
        self.tactile_frame = None
        self.ret = 0.5
        self.zero_vector_offset = 0.
        threading.Thread(target=self.classify_forever, daemon=True).start()

    def scale(self, data):
        # 此处需要与采集数据直至送入模型一致
        if self.use_log:
            value = -np.log(np.maximum(data, 1e-6) * SCALE) / np.log(10)
            # 至此，10 ** value 就是电阻（kΩ）
            value = ((-value + 4.) / 2.5 * 255)  # 用10**1.5至10**4.的范围
            value[value < 0] = 0
        else:
            value = data
        return value

    # 异步识别
    def classify_material_async(self, tactile_frame):
        self.tactile_frame = tactile_frame
        return self.ret

    def classify_forever(self):
        while True:
            if self.tactile_frame is not None:
                tactile_frame = self.tactile_frame
                self.tactile_frame = None
                ret = self.classify_material(tactile_frame)
                self.ret = ret
            time.sleep(0.01)

    def classify_material(self, tactile_frame):
        tactile_frame = self.scale(tactile_frame)
        # 弄成均值-差分格式
        x = tf.constant([tactile_frame], dtype=float)
        summed = np.array(self.model.log_call(x)[0])
        if self.summed_prev is None:
            self.summed_prev = np.zeros(summed.shape) + (1. / summed.shape[-1])
        self.summed_prev = self.summed_prev * self.smooth_rate + summed * (1. - self.smooth_rate)
        exp_summed = np.exp(self.summed_prev / 8.)
        ret = np.sum(self.model_out_translate * exp_summed / np.sum(exp_summed))
        ret_zeroed = self.inverse_smax(ret) - self.zero_vector_offset
        ret = 1. / (1. + np.exp(-ret_zeroed))
        return ret

    @staticmethod
    def inverse_smax(x):
        return np.log(x / (1. - x))

    def set_zero(self, recognized):
        de_zeroed_recognized = self.inverse_smax(recognized) + self.zero_vector_offset
        self.zero_vector_offset = np.mean(de_zeroed_recognized)


if __name__ == '__main__':
    td_interface = TactileDistributionInterface(False)
