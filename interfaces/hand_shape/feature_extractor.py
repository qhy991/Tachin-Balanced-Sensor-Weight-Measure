

import numpy as np

SCALE = (32768. * 25. / 5.) ** -1  # 换算系数


class FingerFeatureExtractor:

    def __init__(self, skin_data_threshold, skin_data_scale, smooth, move_scale, range_based_suppression_scale):
        self.skin_data_threshold = skin_data_threshold
        self.contact_strength_scale = skin_data_scale
        self.smooth_for_move = smooth
        self.move_scale = move_scale
        self.range_based_suppression_scale = range_based_suppression_scale
        #
        self.frame_last = None
        self.contact_strength_smoothed = 0
        self.center_x_smoothed = 0
        self.center_y_smoothed = 0
        self.sigma_x_smoothed = 0
        self.sigma_y_smoothed = 0
        #
        self.center_x_diff_last = 0
        self.center_y_diff_last = 0

    def __scale__(self, skin_data):
        return (skin_data - self.skin_data_threshold) * self.contact_strength_scale
        # skin_data = skin_data / SCALE
        # return (np.log10(np.maximum(skin_data, self.skin_data_threshold)) - np.log10(self.skin_data_threshold))\
        #     * self.contact_strength_scale

    def __c__call__(self, skin: np.ndarray):
        skin = self.__scale__(skin)
        contact_strength = np.sum(skin)
        xx = np.arange(skin.shape[0])[:, None]
        yy = np.arange(skin.shape[1])[None, :]
        center_x_this = (np.sum(xx * skin) / contact_strength) if contact_strength > 0 else 0
        center_y_this = (np.sum(yy * skin) / contact_strength) if contact_strength > 0 else 0

        if self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move) > 0:
            self.center_x_smoothed = (self.center_x_smoothed * self.contact_strength_smoothed * self.smooth_for_move
                                      + center_x_this * (1. - self.smooth_for_move) * contact_strength) \
                                     / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move))
            self.center_y_smoothed = (self.center_y_smoothed * self.contact_strength_smoothed * self.smooth_for_move
                                      + center_y_this * (1. - self.smooth_for_move) * contact_strength) \
                                     / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move))
        else:
            self.center_x_smoothed = 0
            self.center_y_smoothed = 0

        self.contact_strength_smoothed = self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move)

        if contact_strength > 0:
            distribution_x_this = np.sum(np.abs(xx - center_x_this) * skin) / contact_strength * self.range_based_suppression_scale
            distribution_y_this = np.sum(np.abs(yy - center_y_this) * skin) / contact_strength * self.range_based_suppression_scale
        else:
            distribution_x_this = 0
            distribution_y_this = 0
        if self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move) > 0:
            self.sigma_x_smoothed = (self.sigma_x_smoothed * self.contact_strength_smoothed * self.smooth_for_move + distribution_x_this * contact_strength * (1 - self.smooth_for_move)) / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1 - self.smooth_for_move))
            self.sigma_y_smoothed = (self.sigma_y_smoothed * self.contact_strength_smoothed * self.smooth_for_move + distribution_y_this * contact_strength * (1 - self.smooth_for_move)) / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1 - self.smooth_for_move))
        else:
            self.sigma_x_smoothed = 0
            self.sigma_y_smoothed = 0

        magnitude = min([contact_strength, self.contact_strength_smoothed]) ** 0.5 * self.move_scale

        center_x_diff = center_x_this - self.center_x_smoothed
        if abs(center_x_diff) + self.sigma_x_smoothed > 0:
            center_x_diff *= abs(center_x_diff) / (abs(center_x_diff) + self.sigma_x_smoothed) * magnitude
        else:
            center_x_diff = 0
        #
        center_y_diff = center_y_this - self.center_y_smoothed
        if abs(center_y_diff) + self.sigma_y_smoothed > 0:
            center_y_diff *= abs(center_y_diff) / (abs(center_y_diff) + self.sigma_y_smoothed) * magnitude
        else:
            center_y_diff = 0
        #
        change_rate = np.linalg.norm([center_x_diff, center_y_diff, 1]) \
                                / np.linalg.norm([self.center_x_diff_last, self.center_y_diff_last, 1])
        reserve_rate_slip_end = 2. - np.clip(change_rate, 1., 2.)
        reserve_rate_strength_keep = min([1., (contact_strength + 1.) / (self.contact_strength_smoothed + 1.)])
        reserve_rate = reserve_rate_slip_end * reserve_rate_strength_keep
        reserved_x_diff = self.center_x_diff_last * reserve_rate
        reserved_y_diff = self.center_y_diff_last * reserve_rate
        self.center_x_diff_last = center_x_diff * (1. - reserve_rate) + reserved_x_diff
        self.center_y_diff_last = center_y_diff * (1. - reserve_rate) + reserved_y_diff
        x_randomize = 1. + (np.random.rand() - 0.5) * np.clip(change_rate, -1., 1.) * 0.1
        y_randomize = 1. + (np.random.rand() - 0.5) * np.clip(change_rate, -1., 1.) * 0.1
        print(x_randomize, y_randomize)
        return {'contact_strength': contact_strength,
                'center_x_diff': center_x_diff * (1. - reserve_rate) + reserved_x_diff * x_randomize,
                'center_y_diff': center_y_diff * (1. - reserve_rate) + reserved_y_diff * y_randomize}

    # 以下为废弃接口

    def __a__call__(self, skin: np.ndarray):
        # 该版本bug：按压、脱离会判定接触
        skin = self.__scale__(skin)
        contact_strength = np.sum(skin)
        xx = np.arange(skin.shape[0])[:, None]
        yy = np.arange(skin.shape[1])[None, :]
        center_x_this = (np.sum(xx * skin) / contact_strength) if contact_strength > 0 else 0
        center_y_this = (np.sum(yy * skin) / contact_strength) if contact_strength > 0 else 0
        #
        center_x_diff = (center_x_this - self.center_x_smoothed) * min([self.contact_strength_smoothed, contact_strength])
        center_y_diff = (center_y_this - self.center_y_smoothed) * min([self.contact_strength_smoothed, contact_strength])
        #
        self.contact_strength_smoothed = self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move)
        if self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move) > 0:
            self.center_x_smoothed = (self.center_x_smoothed * self.contact_strength_smoothed * self.smooth_for_move
                                      + center_x_this * (1. - self.smooth_for_move) * contact_strength) \
                                     / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move))
            self.center_y_smoothed = (self.center_y_smoothed * self.contact_strength_smoothed * self.smooth_for_move
                                      + center_y_this * (1. - self.smooth_for_move) * contact_strength) \
                                     / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move))
        else:
            self.center_x_smoothed = 0
            self.center_y_smoothed = 0
        return {'contact_strength': contact_strength,
                'center_x_diff': center_x_diff,
                'center_y_diff': center_y_diff}

    def __call__(self, skin: np.ndarray):
        skin = self.__scale__(skin)
        contact_strength = np.sum(skin)
        xx = np.arange(skin.shape[0])[:, None]
        yy = np.arange(skin.shape[1])[None, :]
        center_x_this = (np.sum(xx * skin) / contact_strength) if contact_strength > 0 else 0
        center_y_this = (np.sum(yy * skin) / contact_strength) if contact_strength > 0 else 0
        #

        if self.frame_last is None:
            diff = np.zeros_like(skin)
        else:
            diff = skin - self.frame_last
        sum_negative = -np.sum(diff[diff < 0])
        sum_positive = np.sum(diff[diff > 0])
        magnitude = min([sum_negative, sum_positive]) + contact_strength * 0.05
        #
        center_x_diff = (center_x_this - self.center_x_smoothed) * magnitude
        center_y_diff = (center_y_this - self.center_y_smoothed) * magnitude

        #

        if self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move) > 0:
            self.center_x_smoothed = (self.center_x_smoothed * self.contact_strength_smoothed * self.smooth_for_move
                                      + center_x_this * (1. - self.smooth_for_move) * contact_strength) \
                                     / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move))
            self.center_y_smoothed = (self.center_y_smoothed * self.contact_strength_smoothed * self.smooth_for_move
                                      + center_y_this * (1. - self.smooth_for_move) * contact_strength) \
                                     / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move))
        else:
            self.center_x_smoothed = 0
            self.center_y_smoothed = 0

        if self.frame_last is None:
            self.frame_last = np.zeros_like(skin)
        self.frame_last = self.frame_last * self.smooth_for_move + skin.copy() * (1. - self.smooth_for_move)
        self.contact_strength_smoothed = self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move)
        #
        # print(contact_strength, center_x_diff, center_y_diff)
        #
        return {'contact_strength': contact_strength,
                'center_x_diff': center_x_diff * self.move_scale,
                'center_y_diff': center_y_diff * self.move_scale}

    def __c__call__(self, skin: np.ndarray):
        skin = self.__scale__(skin)
        contact_strength = np.sum(skin)
        xx = np.arange(skin.shape[0])[:, None]
        yy = np.arange(skin.shape[1])[None, :]
        center_x_this = (np.sum(xx * skin) / contact_strength) if contact_strength > 0 else 0
        center_y_this = (np.sum(yy * skin) / contact_strength) if contact_strength > 0 else 0

        if self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move) > 0:
            self.center_x_smoothed = (self.center_x_smoothed * self.contact_strength_smoothed * self.smooth_for_move
                                      + center_x_this * (1. - self.smooth_for_move) * contact_strength) \
                                     / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (
                        1. - self.smooth_for_move))
            self.center_y_smoothed = (self.center_y_smoothed * self.contact_strength_smoothed * self.smooth_for_move
                                      + center_y_this * (1. - self.smooth_for_move) * contact_strength) \
                                     / (self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (
                        1. - self.smooth_for_move))
        else:
            self.center_x_smoothed = 0
            self.center_y_smoothed = 0

        self.contact_strength_smoothed = self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (
                    1. - self.smooth_for_move)

        if contact_strength > 0:
            distribution_x_this = np.sum(
                np.abs(xx - center_x_this) * skin) / contact_strength * self.range_based_suppression_scale
            distribution_y_this = np.sum(
                np.abs(yy - center_y_this) * skin) / contact_strength * self.range_based_suppression_scale
        else:
            distribution_x_this = 0
            distribution_y_this = 0
        if self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (1. - self.smooth_for_move) > 0:
            self.sigma_x_smoothed = (
                                            self.sigma_x_smoothed * self.contact_strength_smoothed * self.smooth_for_move + distribution_x_this * contact_strength * (
                                                    1 - self.smooth_for_move)) / (
                                                self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (
                                                    1 - self.smooth_for_move))
            self.sigma_y_smoothed = (
                                                self.sigma_y_smoothed * self.contact_strength_smoothed * self.smooth_for_move + distribution_y_this * contact_strength * (
                                                    1 - self.smooth_for_move)) / (
                                                self.contact_strength_smoothed * self.smooth_for_move + contact_strength * (
                                                    1 - self.smooth_for_move))
        else:
            self.sigma_x_smoothed = 0
            self.sigma_y_smoothed = 0

        magnitude = min([contact_strength, self.contact_strength_smoothed]) ** 0.5 * self.move_scale

        center_x_diff = center_x_this - self.center_x_smoothed
        if abs(center_x_diff) + self.sigma_x_smoothed > 0:
            center_x_diff *= abs(center_x_diff) / (abs(center_x_diff) + self.sigma_x_smoothed) * magnitude
        else:
            center_x_diff = 0
        #
        center_y_diff = center_y_this - self.center_y_smoothed
        if abs(center_y_diff) + self.sigma_y_smoothed > 0:
            center_y_diff *= abs(center_y_diff) / (abs(center_y_diff) + self.sigma_y_smoothed) * magnitude
        else:
            center_y_diff = 0
        #

        return {'contact_strength': contact_strength,
                'center_x_diff': center_x_diff,
                'center_y_diff': center_y_diff}

