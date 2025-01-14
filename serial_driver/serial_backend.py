# USB通讯协议读取示例代码

import serial
import threading
from collections import deque
import time
import json
import numpy as np
import crcmod.predefined
from config import config_array

crc = crcmod.predefined.mkCrcFun('crc-ccitt-false')

MESSAGE_SIZE = 512
HEAD_LENGTH = 6
CRC_LENGTH = 2

FOLDING_ROW = config_array['row_array']
FOLDING_COL = config_array['column_array']


class SerialBackend:
    def __init__(self, buffer_length, sensor_shape, bytes_per_point):
        # buffer_length为储存的长度
        # 在子线程中读取serial协议传来的数据。主线程会将数据取走
        self.sensor_shape = sensor_shape
        self.bytes_per_point = bytes_per_point
        self.package_size = HEAD_LENGTH + CRC_LENGTH + sensor_shape[1] * bytes_per_point
        # 串口相关
        self.serial = serial.Serial(None, 230400, timeout=None)
        # 临时容器
        self.last_message = np.ndarray((MESSAGE_SIZE,), dtype=np.uint8)
        self.preparing_frame = [np.zeros((self.sensor_shape[0] * self.sensor_shape[1],), dtype=np.uint8)
                                for _ in range(self.bytes_per_point)]
        self.finished_frame = [np.zeros((self.sensor_shape[0] * self.sensor_shape[1],), dtype=np.uint8)
                               for _ in range(self.bytes_per_point)]
        self.last_finish_time = 0.
        self.last_frame_number = None
        self.last_package_number = None
        self.last_interval = 0.
        self.message_cache = np.empty(0, dtype=np.uint8)
        self.lock = threading.Lock()

        # 已完成数据容器
        self.__buffer_length = buffer_length
        self.buffer = deque(maxlen=buffer_length)

        # 错误信息
        self.warn_info = ''
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
        except serial.SerialException as e:
            print('Failed to connect to serial device')
            raise e

    def __preset_buffer(self):
        for _ in range(self.buffer.maxlen):
            self.buffer.append((self.finished_frame, self.last_finish_time))
        self.buffer.clear()

    def stop(self):
        self.active = False
        self.serial.close()
        self.err_queue.clear()
        return True

    def get_interval(self):
        return self.last_interval

    def read_forever(self):
        while self.active:
            self.read()

    def read(self):
        try:
            received = self.serial.read(MESSAGE_SIZE)
            received = [int(_) for _ in received]
            self.last_message = np.array(received, dtype=np.uint8)
        # except serial.SerialException as e:
        except Exception as e:
            self.stop()
            self.err_queue.append(e)
            print(e)
            raise Exception('Serial read/write failed')
        if len(self.message_cache) == 0:
            self.message_cache = self.last_message.copy()
        else:
            self.message_cache = np.concatenate((self.message_cache, self.last_message), axis=0)

        offset = 0
        m = len(self.message_cache)

        while offset < (m - self.package_size):
            # 格式：AA 10 33 “长度” 帧号 包号 数据 CRC
            self.warn_info = ''
            if (self.message_cache[offset] == 0xaa) \
                    & (self.message_cache[offset + self.package_size] == 0xaa):

                # 包头效验正确
                frame_number = self.message_cache[offset + 4]
                package_number = self.message_cache[offset + 5]
                data = self.message_cache[offset
                                          :offset + HEAD_LENGTH + self.sensor_shape[1] * self.bytes_per_point]
                crc_received = self.message_cache[offset + HEAD_LENGTH + self.sensor_shape[1] * self.bytes_per_point
                                                  :offset + HEAD_LENGTH + CRC_LENGTH + self.sensor_shape[
                    1] * self.bytes_per_point]
                crc_calculated = self.__calculate_crc(data)
                if crc_received[0].astype(np.uint16) * 256 + crc_received[1].astype(np.uint16) != crc_calculated:
                    self.warn_info = 'CRC check failed'
                    flag = False
                else:
                    flag = self.__validate_package(frame_number, package_number)

                if flag:
                    self.__write_data(offset, package_number)
                offset += self.package_size
            else:
                offset += 1
                self.warn_info = ''

            if self.warn_info:
                print(self.warn_info)

        self.message_cache = self.message_cache[offset:]

    def __validate_package(self, frame_number, package_number):
        if self.last_frame_number is None:
            flag = (package_number == 0)
            if flag:
                self.last_frame_number = frame_number
                self.last_package_number = package_number
            else:
                self.warn_info = ''
        else:
            if package_number == 0:
                if self.last_package_number == self.sensor_shape[0] - 1:
                    self.__finish_frame()
                    flag = True
                else:
                    self.warn_info = f"{self.last_frame_number}/{self.last_package_number} -> {frame_number}/{package_number}"
                    flag = False
                self.last_frame_number = frame_number
                self.last_package_number = package_number
            elif self.last_package_number is None:
                self.warn_info = 'Waiting for next frame'
                flag = False
            else:
                flag = (package_number == self.last_package_number + 1) and (frame_number == self.last_frame_number)
                if not flag:
                    self.warn_info = f"{self.last_frame_number}/{self.last_package_number} -> {frame_number}/{package_number}"
                else:
                    self.last_package_number = package_number
        return flag

    def __write_data(self, offset, package_number):
        preparing_cursor = self.sensor_shape[1] * FOLDING_ROW[package_number.astype(np.uint16)]
        begin = preparing_cursor
        end = preparing_cursor + self.sensor_shape[1]
        slice_to = slice(begin, end)
        slices_from = [slice(
            offset + HEAD_LENGTH + bit,
            offset + HEAD_LENGTH + self.sensor_shape[1] * self.bytes_per_point + bit,
            self.bytes_per_point
        ) for bit in range(self.bytes_per_point)]
        for bit, slice_from in enumerate(slices_from):
            self.preparing_frame[bit][slice_to] = self.message_cache[slice_from][FOLDING_COL]

    def read_void(self):
        try:
            self.last_message[...] = self.epi_t.read(MESSAGE_SIZE)
        except serial.SerialException as e:
            print(e)

    def __finish_frame(self):
        with self.lock:
            for bit in range(self.bytes_per_point):
                self.finished_frame[bit][...] = self.preparing_frame[bit][...]
            time_now = time.time()
            if self.last_finish_time > 0:
                self.last_interval = time_now - self.last_finish_time
            self.last_finish_time = time_now
            self.buffer.append(([_.copy() for _ in self.finished_frame], self.last_finish_time))

    def __abort_frame(self):
        for bit in range(self.bytes_per_point):
            self.preparing_frame[bit][...] = 0

    @staticmethod
    def __calculate_crc(data):
        return crc(data)

    def get(self):
        if self.buffer:
            with self.lock:
                bits, t = self.buffer.popleft()
            return bits, t
        else:
            return None, None


if __name__ == '__main__':
    # 简单的调用测试
    sb = SerialBackend(16, (16, 16), 2)  # 使用中支持在UsbBackend里存一些数后一起取出。如果发现数据不完整，酌情增加该数值
    sb.start('COM28')  # 卡号
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

