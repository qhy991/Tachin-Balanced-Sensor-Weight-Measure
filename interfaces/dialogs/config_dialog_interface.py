from PyQt5 import QtCore, QtGui, QtWidgets
from interfaces.dialogs.layout.layout_config import Ui_Dialog
import numpy as np
import re

class ConfigDialogInterface(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, window):
        super().__init__()
        self.setupUi(self)
        self.window = window
        self.__set_buttons()
        self.__load_config()

    def __set_buttons(self):
        # 绑定按钮事件
        self.button_ensure.clicked.connect(self.__apply_changes)  # 确定按钮
        self.button_cancel.clicked.connect(self.reject)  # 取消按钮

    def __load_config(self):
        config = self.window.config
        # YLIM
        ylim = config['ylim']
        assert len(ylim) == 2
        diff_y_lim = ylim[1] - ylim[0]
        y_range_str_list = [self.combo_box_y_range.itemText(index) for index in range(self.combo_box_y_range.count())]
        y_range_values = [np.log(float(re.sub(r'倍', '', item))) for item in y_range_str_list]
        # find the index nerest to diff_y_lim
        nearest_index = np.argmin(np.abs(np.array(y_range_values) - diff_y_lim))
        self.combo_box_y_range.setCurrentIndex(nearest_index)
        # baseline calibrated


    def __apply_changes(self):
        pass