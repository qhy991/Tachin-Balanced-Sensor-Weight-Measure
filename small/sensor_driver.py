
from abstract_sensor_driver import AbstractSensorDriver
import warnings
import serial
# NOTE: 用pip install pyserial安装serial
import serial.tools.list_ports
import atexit
import numpy as np
import time
import re
import threading

FOLDING_ROW = [0, 4, 2, 6, 1, 5, 3, 7]
FOLDING_COL = [0, 1, 2, 3, 4, 5, 6, 7]

SIZE = 8


class SmallSensorDriver(AbstractSensorDriver):

    # 传感器个数
    SENSOR_SHAPE = (8, 8)
    # 数据格式
    ZERO_LEN_MIN = 16
    DATA_TYPE = np.int16

    def __init__(self):
        super(SmallSensorDriver, self).__init__()
        self.ser = None
        self.file = None
        #
        self.__preparing_frame = np.zeros(self.SENSOR_SHAPE, dtype=self.DATA_TYPE)
        self.__prepare_start_time = 0
        self.__preparing_row_index = -1
        self.__aborted = False
        #
        self.__finished_frame = np.zeros(self.SENSOR_SHAPE, dtype=self.DATA_TYPE)
        self.__finish_time = 0
        self.stored_message = ''
        #
        self.__working = False
        threading.Thread(target=self.read_forever, daemon=True).start()

    def __bool__(self):
        return self.__working

    def connect(self, port):
        self.__finish_time = 0
        if not self:
            if port.lower().startswith('com'):
                try:
                    self.ser = serial.Serial(port, 115200, timeout=0.)
                    atexit.register(self.on_exit)
                    self.__working = True
                    return True
                except serial.SerialException as e:
                    warnings.warn(f'串口{port}连接失败')
                    print(e)
                    return False
            else:
                try:
                    self.file = np.loadtxt(port, delimiter=',', dtype=self.DATA_TYPE)\
                        .reshape((-1, self.SENSOR_SHAPE[0], self.SENSOR_SHAPE[1]))
                    atexit.register(self.on_exit)
                    self.__working = True
                    return True
                except FileNotFoundError as e:
                    warnings.warn(f'文件{port}不存在')
                    return False
        else:
            return False

    def disconnect(self):
        print('断开连接')
        self.__abort_frame()
        if self:
            self.__working = False
            time.sleep(0.01)
            if self.ser:
                self.ser.close()
                self.ser = None
            elif self.file is not None:
                self.file = None
            else:
                raise Exception()
            return True
        else:
            return False

    def on_exit(self):
        self.disconnect()

    def read_forever(self):
        while True:
            if self:
                self.read()
            else:
                time.sleep(0.001)
                # pass

    def read(self):
        if self.ser:
            read = self.ser.readline()
            self.ser.flush()
            if not read:
                # print('未接收到数据')
                return
            try:
                self.stored_message += read.decode('utf-8')
                self.stored_message = self.stored_message[-256:]
            except UnicodeDecodeError:
                warnings.warn('未启动')
                return
            # 这里可以重点优化一下。用re匹配不优雅，不过目前没发现有什么问题
            pattern = r'[\S\s]*(\d+)\svalue\s*=\s*(\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+)([\S\s]*)'
            # 等待行号
            flag = True
            while flag:
                flag = False
                matched = re.match(pattern, self.stored_message)
                if matched:
                    flag = True
                    self.stored_message = matched.group(3)
                    split = matched.group(2).split('  ')
                    # 等待行号
                    try:
                        row = [int(item) for item in split]
                        row_idx = int(matched.group(1))
                    except ValueError:
                        warnings.warn('解码错误')
                        self.__abort_frame()
                        return
                    #
                    if self.__aborted:
                        if row_idx == 0:
                            self.__aborted = False
                    if not self.__aborted:
                        if row_idx == self.__preparing_row_index + 1:
                            self.__preparing_frame[row_idx, :] = row
                            self.__preparing_row_index += 1
                            if row_idx == 0:
                                self.__prepare_start_time = time.time()
                            elif row_idx == self.SENSOR_SHAPE[0] - 1:
                                self.__finish_frame()
                        else:
                            warnings.warn("检测到行号不连续")
                            self.__abort_frame()
        elif self.file is not None:
            row = self.file[0, :, :]
            print(row)
            self.file[...] = np.roll(self.file, -1, axis=0)
            self.__finished_frame[...] = row
            self.__finish_time = time.time()
            time.sleep(0.005)
        else:
            raise Exception('无效接口')

    def __finish_frame(self):
        self.__finished_frame[...] = self.__preparing_frame
        if self.__finish_time > 0:
            print(f'时间：{self.__prepare_start_time - self.__finish_time}')
        self.__finish_time = self.__prepare_start_time
        self.__preparing_frame[...] = 0
        self.__preparing_row_index = -1

    def __abort_frame(self):
        self.__aborted = True
        self.__preparing_frame[...] = 0
        self.__preparing_row_index = -1

    def get(self):
        return self.__finished_frame[FOLDING_ROW, :][:, FOLDING_COL].copy(), self.__finish_time

