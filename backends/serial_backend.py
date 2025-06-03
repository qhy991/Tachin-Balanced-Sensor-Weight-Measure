# CAN通讯协议读取示例代码
import numpy as np
import serial
import threading
from collections import deque
from backends.decoding import Decoder
import time
import os
import json

baud_rate = json.load(open(os.path.dirname(__file__) + '/config_serial.json', 'rt'))['baud_rate']
print(f"Baud rate: {baud_rate}")


class SerialBackend:
    def __init__(self, config_array):
        # 在子线程中读取CAN协议传来的数据。主线程会将数据取走
        # CAN卡对连续读数要求较高
        self.serial = serial.Serial(None, baud_rate, timeout=None)
        # 解包
        self.decoder = Decoder(config_array)
        self.err_queue = deque(maxlen=1)
        #
        self.active = False

    def start(self, port):
        # 通过REV号区分不同的采集卡
        try:
            self.serial.port = port
            self.serial.open()
            self.active = True
            threading.Thread(target=self.read_forever, daemon=True).start()
            return True
        except Exception as e:
            print('Failed to connect to CAN device')
            raise e

    def stop(self):
        self.active = False
        return True

    def read_forever(self):
        while self.active:
            self.read()

    def read(self):
        try:
            last_message = [int(_) for _ in self.serial.read()]
        except Exception as e:
            self.stop()
            self.err_queue.append(e)
            print(e)
            raise Exception('Serial read/write failed')
        self.decoder(last_message)

    def get(self):
        return self.decoder.get()

    def get_last(self):
        return self.decoder.get_last()


if __name__ == '__main__':
    # 简单的调用测试
    import json
    import os
    config_array = json.load(open(os.path.join(os.path.dirname(__file__), 'config_array_16.json'), 'rt'))
    sb = SerialBackend(config_array)  # 使用中支持在UsbBackend里存一些数后一起取出。如果发现数据不完整，酌情增加该数值
    sb.start('COM4')  # 设备区分还没做
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

