import sys
import pickle
import os
import warnings

import keyboard
import atexit
import numpy as np
import matplotlib.pyplot as plt


class FeatureExtractorStatistics:

    def __init__(self, name):
        self.name = name
        self.pressures = []
        self.slides = []
        self.pats = []
        self.labels = []
        # 当前模式。用keyboard可以切换
        self.activated = 0
        self.label = 0
        self.load()
        keyboard.on_press(self.keyboard_callback)

    def keyboard_callback(self, ev):
        key = ev.name
        if key == self.name:
            self.activated = 1
            print(f"名称为{self.name}的设备已激活")
        else:
            if self.activated:
                if key == 'q':
                    self.label = 0
                    print(f"设备{self.name}，标签：空")
                elif key == 'w':
                    self.label = 1
                    print(f"设备{self.name}，标签：按压")
                elif key == 'e':
                    self.label = 2
                    print(f"设备{self.name}，标签：抚摸")
                elif key == 'r':
                    self.label = 3
                    print(f"设备{self.name}，标签：拍打")
                elif key == 'o':
                    print(f"设备{self.name}保存中...")
                    self.save()
                    print(f"设备{self.name}保存完毕")
                elif key == 'p':
                    print(f"设备{self.name}重置中...")
                    self.load()
                    print(f"设备{self.name}重置完毕")

    def data_in(self, result):
        if self.activated:
            self.pressures.append(result['press'])
            self.slides.append(result['slide'])
            self.pats.append(result['pat'])
            self.labels.append(self.label)

    def load(self):
        path = os.path.join(os.path.dirname(__file__), f'dumping/dataset_{self.name}.pkl')
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.pressures = data.get('pressures', [])
                self.slides = data.get('slides', [])
                self.pats = data.get('pats', [])
                self.labels = data.get('labels', [])
        else:
            warnings.warn("未找到数据文件，已创建新的统计数据文件夹")
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))

    def save(self):
        path = os.path.join(os.path.dirname(__file__), f'dumping/dataset_{self.name}.pkl')
        data = {
            'pressures': self.pressures,
            'slides': self.slides,
            'pats': self.pats,
            'labels': self.labels
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)

    def train(self):
        # 画一个3*3的scatter_matrix，显示pressures, slides, pats的关系
        # 以label进行着色
        predictors = np.array([self.pressures, self.slides, self.pats]).T
        labels = np.array(self.labels)
        # 画散点图矩阵
        if len(predictors) > 0:
            plt.figure(figsize=(9, 9))
            for ii in range(3):
                for jj in range(3):
                    if ii == jj:
                        plt.subplot(3, 3, ii * 3 + jj + 1).hist(predictors[:, ii], bins=20, color='gray', alpha=0.5)
                    else:
                        plt.subplot(3, 3, ii * 3 + jj + 1).scatter(predictors[:, ii], predictors[:, jj], c=labels,
                                                                    cmap='viridis', alpha=0.5, s=8)
            plt.show()
        else:
            print("没有数据可供训练")



if __name__ == '__main__':
    feature_extractor = FeatureExtractorStatistics('0')
    feature_extractor.train()
    pass


