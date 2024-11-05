
import socket
import numpy as np
import time
from data_handler.data_handler import VALUE_DTYPE
from abstract_sensor_driver import AbstractSensorDriver
import atexit
from server.utils import crc, CommandCodes
from utils.performance_monitor import Ticker

ticker = Ticker()

RETRY = 3


class SocketClient(AbstractSensorDriver):

    SENSOR_SHAPE = (64, 64)

    PERIOD_UNIT = 2 ** 16

    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数

    def __init__(self):
        super(SocketClient, self).__init__()
        self.host = 'localhost'
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # instantiate
        # 设置输入缓冲区大小
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 ** 16)
        self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # 调整TCP协议的检测时间
        # self.client_socket.setblocking(False)
        atexit.register(self.disconnect)
        self.last_receive_time = time.time()
        self.last_t_now = 0.
        self.base_time = 0.
        ticker.tic()

    def connect(self, port):
        retry = RETRY
        while retry:
            retry -= 1
            try:
                self.client_socket.connect((self.host, int(port)))
                print('成功')
                return True
            # except BlockingIOError:
            #     wait()
            except OSError:
                return False
        return False

    def disconnect(self):
        if self.client_socket.fileno() != -1:
            self.client_socket.close()

    # 对test、query做装饰器，在调用后进行统一计时
    @staticmethod
    def time_decorator(func):
        def wrapper(self, *args, **kwargs):
            res = func(self, *args, **kwargs)
            time_now = time.time()
            print(f"时间间隔：{time_now - self.last_receive_time}")
            self.last_receive_time = time_now
            return res
        return wrapper

    @time_decorator
    def test(self):
        message = [0x55, 0xaa, 0x00, CommandCodes.NULL]
        # 设置最后一位为CRC校验码
        message.append(crc(message))
        #
        self.client_socket.send(bytes(message))
        data = self.client_socket.recv(2 ** 4)
        print(f"收到时间{time.time()}")
        print(data)

    @time_decorator
    def query(self):
        message = [0x55, 0xaa, 0x00, CommandCodes.LATEST_FRAME, 0x00]
        # 设置最后一位为CRC校验码
        message.append(crc(message))
        #
        ticker.toc('其他')
        self.client_socket.sendall(bytes(message))
        ticker.toc('客户端发送')
        data = self.client_socket.recv(2 ** 15)
        ticker.toc('客户端接收')
        print(f"接收字节长度：{len(data)}")
        value_bytes, t_now = None, None
        if data[:2] == bytes([0xaa, 0x55]) and data[-1] == crc(data[:-1]):
            if data[3] == CommandCodes.LATEST_FRAME:
                if data[6] == 0x01:
                    time_after_begin_bytes = (np.frombuffer(data[7:9], dtype='>i2')
                                              .astype(float) * 1e-3)[0]
                    t_now = self.base_time + time_after_begin_bytes
                    if t_now != self.last_t_now:
                        value_bytes = np.frombuffer(data[9:-1], dtype=VALUE_DTYPE).reshape(self.SENSOR_SHAPE)
                        if t_now < self.last_t_now:
                            self.base_time += self.PERIOD_UNIT * 1e-3
                            t_now += self.PERIOD_UNIT * 1e-3
                        self.last_t_now = t_now
                        pass
                    else:
                        value_bytes = None

                else:
                    print("无数据")
                # print(f"收到时间：{time.time()}")
            else:
                print("未知指令")
        else:
            print("校验失败")
            print(data)
        ticker.toc('返回')
        # print(time_after_begin_bytes, value_bytes)
        return value_bytes, t_now

    def get(self):
        value_bytes, t_now = self.query()
        if value_bytes is not None:
            # 给上位机时，需要把value_bytes再转回去
            # value = (np.log(np.maximum(data_f - self.zero, 1e-6) * self.driver.SCALE) / np.log(10)).astype(VALUE_DTYPE)
            value = value_bytes
        else:
            value = None
        return value, t_now


if __name__ == '__main__':
    client = SocketClient()
    client.connect(10083)
    while True:
        client.query()
