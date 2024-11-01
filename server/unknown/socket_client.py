
import socket
import numpy as np
import time
from ordinary.data_handler import VALUE_DTYPE, SENSOR_SHAPE
import atexit
from server.utils import crc, CommandCodes
import warnings


class SocketClient:

    def __init__(self, c_id):
        self.host = 'localhost'  # as both code is running on same pc
        self.port = 10080 + c_id  # socket server port number
        self.client_socket = socket.socket()  # instantiate
        atexit.register(self.disconnect)
        self.last_receive_time = time.time()

    def connect(self):
        self.client_socket.connect((self.host, self.port))

    def disconnect(self):
        self.client_socket.close()

    def test(self):
        self.connect()
        message = [0x55, 0xaa, 0x00, CommandCodes.NULL]
        # 设置最后一位为CRC校验码
        message.append(crc(message))
        #
        self.client_socket.send(bytes(message))
        data = self.client_socket.recv(2 ** 15)
        print(f"收到时间{time.time()}")
        print(data)
        self.disconnect()

    def query(self):
        self.connect()
        message = [0x55, 0xaa, 0x00, CommandCodes.LATEST_FRAME]
        # 设置最后一位为CRC校验码
        message.append(crc(message))
        #
        self.client_socket.send(bytes(message))
        data = self.client_socket.recv(2 ** 15)
        # data = self.client_socket.recv(2 ** 5)
        if data[:2] == bytes([0xaa, 0x55]) and data[-1] == crc(data[:-1]):
            if data[3] == CommandCodes.LATEST_FRAME:
                if data[6] == 0x01:
                    time_after_begin_bytes = np.frombuffer(data[7:11], dtype=VALUE_DTYPE)[0]
                    value_bytes = np.frombuffer(data[11:-1], dtype=VALUE_DTYPE).reshape(SENSOR_SHAPE)
                    print(f"收到时间：{time.time()}")
                else:
                    print("无数据")
            else:
                print("未知指令")
        else:
            print("校验失败")
            print(data)
        self.disconnect()

if __name__ == '__main__':
    client = SocketClient(0)
    # client.connect()
    while True:
        client.test()
