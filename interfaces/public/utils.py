import os
# import everything
from PyQt5 import QtGui, QtWidgets, QtCore

RESOURCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../resources')

def set_logo(window):
    window.setWindowTitle(QtCore.QCoreApplication.translate("MainWindow", "电子皮肤采集程序"))
    window.setWindowIcon(QtGui.QIcon(os.path.join(RESOURCE_FOLDER, "logo.ico")))
    logo_path = os.path.join(RESOURCE_FOLDER, "logo.png")
    pixmap = QtGui.QPixmap(logo_path)
    window.label_logo.setPixmap(pixmap)
    window.label_logo.setScaledContents(True)
    window.label_logo.setFixedSize(pixmap.size())  # 强制 QLabel 与位图保持相同比例
    window.label_logo.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)






