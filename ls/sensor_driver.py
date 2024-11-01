
import socket
import crcmod.predefined
import numpy as np
import time
from abstract_sensor_driver import AbstractSensorDriver

DEPTH = 4
DATA_START = 7
DATA_END = 25607


class LSSensorDriver(AbstractSensorDriver):

    SENSOR_SHAPE = (80, 80)

    def __init__(self):
        # 创建一个socket:
        super(LSSensorDriver, self).__init__()
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.crc_fun = crcmod.predefined.mkCrcFun('crc-8-maxim')
        self.serial_numbers = None
        self.last_data = np.zeros(self.SENSOR_SHAPE, dtype=self.DATA_TYPE)

    def connect(self, port):
        try:
            self.s.connect(('127.0.0.1', 20000))
            self.serial_numbers = self.__query_handles()
            self.connected = True
            return True
        except:
            return False

    def disconnect(self):
        self.connected = False
        return True

    def __crc(self, b):
        return self.crc_fun(b)

    @staticmethod
    def __num2str(num):
        str = hex(num)
        str = str[2:4]
        if len(str) == 1:
            str = '0' + str
        str = bytes.fromhex(str)
        # print(str)
        return str

    def __send_str(self, send_data):
        split_send_data = send_data.split(sep=' ')
        split_send_data = [int(_, 16) for _ in split_send_data]
        return self.__send_list(split_send_data)

    def __send_list(self, list_data, big=False):
        put_data = b''
        for _ in list_data:
            put_data += self.__num2str(_)
        # print(f'发送：{put_data}')
        self.s.send(put_data)
        recv_data = self.s.recv(32768 if big else 1024)
        # print(f'收到：{recv_data}，长度{recv_data.__len__()}')
        # for _ in recv_data:
        #     print(hex(_))
        return recv_data

    def __query_handles(self):
        recv_data = self.__send_str('AA BB 01 00 00 00 00 C1 FF')
        recv_existing = self.__send_str('AA BB 09 00 00 00 00 FF FF')
        idx = 7
        STEP = 16
        serial_numbers = []
        serial_lst = []
        while idx + STEP < recv_data.__len__():
            serial_numbers.append(recv_data[idx + 1:(idx + 1 + STEP)])
            serial_lst.append(recv_existing[idx:(idx + STEP)])
            idx += STEP
        # 设置标定文件
        for idx in range(serial_numbers.__len__()):
            to_be_send = [0xAA, 0xBB, 0x07, 0x20, 0x00, 0x00, 0x00]
            to_be_send += serial_lst[idx]
            to_be_send += serial_numbers[idx]
            to_be_send.append(self.crc_fun(bytes(to_be_send)))
            to_be_send.append(0xFF)
            self.__send_list(to_be_send)
            pass
        #
        return serial_numbers

    def get(self):
        bits = self.query_bits(0)
        if bits:
            data = bits[2].astype(np.int16) + (np.maximum(bits[3].astype(np.int16), 1) - 1) * 256
            if not np.all(data == self.last_data):
                self.last_data = data
                return data, time.time()
            else:
                return None, None
        else:
            return None, None

    def query_bits(self, number):
        if not self.connected:
            return None
        acquired_data = self.__send_query_command(number)
        #
        recv = np.frombuffer(acquired_data, dtype=np.uint8)
        data_0 = recv[(DATA_START + 0):DATA_END:DEPTH].reshape(self.SENSOR_SHAPE)
        data_1 = recv[(DATA_START + 1):DATA_END:DEPTH].reshape(self.SENSOR_SHAPE)
        data_2 = recv[(DATA_START + 2):DATA_END:DEPTH].reshape(self.SENSOR_SHAPE)
        data_3 = recv[(DATA_START + 3):DATA_END:DEPTH].reshape(self.SENSOR_SHAPE)
        data_3 = np.where(data_3 > 64, data_3 - 64, data_3)
        return [data_0, data_1, data_2, data_3]

    def __send_query_command(self, number):
        handle = self.serial_numbers[number]
        to_be_send = [0xAA, 0xBB, 0x02, 0x10, 0x00, 0x00, 0x00]
        to_be_send += [int(_) for _ in handle]
        to_be_send.append(self.crc_fun(bytes(to_be_send)))
        to_be_send.append(0xFF)
        recv = self.__send_list(to_be_send, big=True)
        return recv
