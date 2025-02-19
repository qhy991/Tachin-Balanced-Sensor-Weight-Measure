# CAN通讯协议读取示例代码
import os.path
from ctypes import *
import threading
from collections import deque
import time
import numpy as np
from backends.decoding import Decoder


class CanBackend:
    def __init__(self, config_array):
        # 在子线程中读取CAN协议传来的数据。主线程会将数据取走
        # CAN卡对连续读数要求较高
        self.can = CanDevice()
        # 解包
        self.decoder = Decoder(config_array)
        self.err_queue = deque(maxlen=1)
        #
        self.active = False

    def start(self, port):
        # 通过REV号区分不同的采集卡
        try:
            self.can.connect()
            self.active = True
            threading.Thread(target=self.read_forever, args=(0.0, ), daemon=True).start()
            return True
        except Exception as e:
            print('Failed to connect to CAN device')
            raise e

    def stop(self):
        self.active = False
        return True

    def read_forever(self, interval):
        while self.active:
            start_time = time.time()
            self.read()
            elapsed_time = time.time() - start_time
            sleep_time = max([0, interval - elapsed_time])
            time.sleep(sleep_time)

    def read(self):
        try:
            last_message = self.can.read()
        except Exception as e:
            self.stop()
            self.err_queue.append(e)
            print(e)
            raise Exception('CAN read/write failed')
        self.decoder(last_message)

    def get(self):
        return self.decoder.get()

    def get_last(self):
        return self.decoder.get_last()


LEN = 2500


class CanDevice:
    VCI_USBCAN2 = 4
    STATUS_OK = 1

    class VCI_INIT_CONFIG(Structure):
        _fields_ = [("AccCode", c_uint),
                    ("AccMask", c_uint),
                    ("Reserved", c_uint),
                    ("Filter", c_ubyte),
                    ("Timing0", c_ubyte),
                    ("Timing1", c_ubyte),
                    ("Mode", c_ubyte)
                    ]

    class VCI_CAN_OBJ(Structure):
        _fields_ = [("ID", c_uint),
                    ("TimeStamp", c_uint),
                    ("TimeFlag", c_ubyte),
                    ("SendType", c_ubyte),
                    ("RemoteFlag", c_ubyte),
                    ("ExternFlag", c_ubyte),
                    ("DataLen", c_ubyte),
                    ("Data", c_ubyte * 8),
                    ("Reserved", c_ubyte * 3)
                    ]

    class VCI_CAN_OBJ_ARRAY(Structure):
        # _fields_ = [('SIZE', c_uint16), ('STRUCT_ARRAY', POINTER(CanDevice.VCI_CAN_OBJ))]

        def __init__(self, num_of_structs):
            super().__init__()
            # 这个括号不能少
            self.STRUCT_ARRAY = cast((CanDevice.VCI_CAN_OBJ * num_of_structs)(),
                                     POINTER(CanDevice.VCI_CAN_OBJ))  # 结构体数组
            self.SIZE = num_of_structs  # 结构体长度
            self.ADDR = self.STRUCT_ARRAY[0]  # 结构体数组地址  byref()转c地址

    def __init__(self):
        CanDLLName = os.path.join(os.path.dirname(__file__), './ControlCAN.dll')  # 把DLL放到对应的目录下
        self.canDLL = windll.LoadLibrary(CanDLLName)
        # Linux系统下使用下面语句，编译命令：python3 python3.8.0.py
        # canDLL = cdll.LoadLibrary('./libcontrolcan.so')
        self.rx_vci_can_obj = CanDevice.VCI_CAN_OBJ_ARRAY(LEN)  # 结构体数组
        print(CanDLLName)
        self.data_storage = deque(maxlen=LEN)
        self.communicate_thread = threading.Thread(target=self.communicate_forever, daemon=True)
        self.activated = False

    def connect(self):

        ret = self.canDLL.VCI_OpenDevice(self.VCI_USBCAN2, 0, 0)
        if ret == self.STATUS_OK:
            print('调用 VCI_OpenDevice成功\r\n')
        if ret != self.STATUS_OK:
            print('调用 VCI_OpenDevice出错\r\n')

        # 初始0通道
        vci_initconfig = self.VCI_INIT_CONFIG(0x80000000, 0xFFFFFFFF, 0,
                                              1, 0x00, 0x1C, 0)  # 波特率500k，正常模式
        ret = self.canDLL.VCI_InitCAN(self.VCI_USBCAN2, 0, 0, byref(vci_initconfig))
        if ret == self.STATUS_OK:
            print('调用 VCI_InitCAN1成功\r\n')
        else:
            print('调用 VCI_InitCAN1出错\r\n')

        ret = self.canDLL.VCI_StartCAN(self.VCI_USBCAN2, 0, 0)
        if ret == self.STATUS_OK:
            print('调用 VCI_StartCAN1成功\r\n')
        else:
            print('调用 VCI_StartCAN1出错\r\n')
        self.activated = True
        self.communicate_thread.start()

    def disconnect(self):
        # 关闭
        self.canDLL.VCI_CloseDevice(self.VCI_USBCAN2, 0)
        print('调用 VCI_CloseDevice成功\r\n')
        self.activated = False
        self.communicate_thread = threading.Thread(target=self.communicate_forever, daemon=True)

    def read(self):
        # 取走self.data_storage里的数据
        ret_all = self.data_storage
        self.data_storage = deque(maxlen=LEN)
        return ret_all

    def communicate_forever(self):
        while self.activated:
            self.communicate()

    def communicate(self):
        f = self.canDLL.VCI_Receive(self.VCI_USBCAN2, 0, 0, byref(self.rx_vci_can_obj.ADDR), LEN, 0)
        if f > 0:  # 接收到数据
            for i in range(f):
                ret = list(self.rx_vci_can_obj.STRUCT_ARRAY[i].Data)[:self.rx_vci_can_obj.STRUCT_ARRAY[i].DataLen]
                self.data_storage.extend(ret)
        else:
            time.sleep(0.0)


if __name__ == '__main__':
    # 简单的调用测试
    from config import config_array
    sb = CanBackend(config_array)  # 使用中支持在UsbBackend里存一些数后一起取出。如果发现数据不完整，酌情增加该数值
    sb.start(None)  # 设备区分还没做
    print('start')
    t_last = None
    while True:
        while True:
            bits, t = sb.get()
            if bits is not None:
                print(np.max(bits), np.mean(bits))
                # print(t)
                if t_last is not None:
                    print(t - t_last)
                t_last = t
            else:
                break
        time.sleep(0.001)
    pass
