# 公用的解码程序

import time
import numpy as np
import crcmod.predefined
from collections import deque

crc = crcmod.predefined.mkCrcFun('crc-ccitt-false')

HEAD_LENGTH = 6
CRC_LENGTH = 2


class Decoder:

    MINIMUM_INTERVAL = 0.01

    def __init__(self, config_array):
        self.row_array = config_array['row_array']
        self.column_array = config_array['column_array']
        self.bytes_per_point = config_array.get('bytes_per_point', 2)  # 默认
        assert self.bytes_per_point in [1, 2]
        self.buffer_length = config_array.get('buffer_length', 64)  # 默认
        self.sensor_shape = (self.row_array.__len__(), self.column_array.__len__())
        self.package_size = HEAD_LENGTH + CRC_LENGTH + self.sensor_shape[1] * self.bytes_per_point
        #
        self.preparing_frame \
            = [np.zeros((self.sensor_shape[0] * self.sensor_shape[1], ), dtype=np.uint8)
               for _ in range(self.bytes_per_point)]
        self.finished_frame \
            = [np.zeros((self.sensor_shape[0] * self.sensor_shape[1], ), dtype=np.uint8)
               for _ in range(self.bytes_per_point)]
        self.last_finish_time = 0.
        self.last_frame_number = None
        self.last_package_number = None
        self.buffer = deque(maxlen=self.buffer_length)
        self.message_cache = np.empty(0, dtype=np.uint8)
        self.max_cache_length = self.package_size * self.buffer_length
        #
        self.warn_info = ''

    def __call__(self, message):
        self.message_cache = np.concatenate((self.message_cache, np.array(message, dtype=np.uint8)), axis=0)
        #
        offset = 0
        while offset + self.package_size <= self.message_cache.__len__():
            # 校验前三位为[0xaa, 0x10, 0x33]
            if self.message_cache[offset + 0] == 0xaa\
                    and self.message_cache[offset + 1] == 0x10\
                    and self.message_cache[offset + 2] == 0x33:
                # 包头效验正确
                frame_number = self.message_cache[offset + 4]
                package_number = self.message_cache[offset + 5]
                data = self.message_cache[offset:offset + HEAD_LENGTH + self.sensor_shape[1] * self.bytes_per_point]
                crc_received = \
                    self.message_cache[offset + HEAD_LENGTH + self.sensor_shape[1] * self.bytes_per_point
                                       :offset + HEAD_LENGTH + CRC_LENGTH + self.sensor_shape[1] * self.bytes_per_point]
                crc_calculated = self.__calculate_crc(data)
                if crc_received[0].astype(np.uint16) * 256 + crc_received[1].astype(np.uint16) != crc_calculated:
                    self.warn_info = 'CRC check failed'
                    flag = False
                else:
                    flag = self.__validate_package(frame_number, package_number)

                if flag:
                    self.__write_data(self.message_cache, offset, package_number)
                    offset += self.package_size
                else:
                    offset += 1
            else:
                offset += 1
        self.message_cache = self.message_cache[offset:]
        self.message_cache = self.message_cache[-self.max_cache_length:]
        if self.warn_info:
            print(self.warn_info)
            self.warn_info = ''

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
                    self.warn_info = f'Package number error: ' \
                                     f'{self.last_frame_number}, {self.last_package_number} -> {frame_number}, {package_number}'
                    flag = False
                self.last_frame_number = frame_number
                self.last_package_number = package_number
            elif self.last_package_number is None:
                self.warn_info = 'Waiting for next frame'
                flag = False
            else:
                flag = (package_number == self.last_package_number + 1) and (frame_number == self.last_frame_number)
                if not flag:
                    self.warn_info = f'Package number error: ' \
                                     f'{self.last_frame_number}, {self.last_package_number} -> {frame_number}, {package_number}'
                else:
                    self.last_package_number = package_number
        return flag

    def __write_data(self, message, offset, package_number):
        preparing_cursor = self.sensor_shape[1] * self.row_array[package_number.astype(np.uint16)]
        begin = preparing_cursor
        end = preparing_cursor + self.sensor_shape[1]
        slice_to = slice(begin, end)
        slices_from = [slice(
            offset + HEAD_LENGTH + bit,
            offset + HEAD_LENGTH + self.sensor_shape[1] * self.bytes_per_point + bit,
            self.bytes_per_point
        ) for bit in range(self.bytes_per_point)]
        for bit, slice_from in enumerate(slices_from):
            self.preparing_frame[bit][slice_to] = message[slice_from][self.column_array]

    def __finish_frame(self):
        for bit in range(self.bytes_per_point):
            self.finished_frame[bit][...] = self.preparing_frame[bit][...]
        time_now = time.time()
        if self.last_finish_time > 0:
            self.last_interval = time_now - self.last_finish_time
        if time_now - self.last_finish_time >= self.MINIMUM_INTERVAL:
            self.last_finish_time = time_now
            data = sum([(_.astype(np.int8) if bit == 0 else _).astype(np.int16)
                        * (2 ** (8 * (self.bytes_per_point - bit - 1)))
                        for bit, _ in enumerate(self.finished_frame)]).reshape(self.sensor_shape)
            # 引入底层滤波器
            self.buffer.append((data, self.last_finish_time))

    def __abort_frame(self):
        for bit in range(self.bytes_per_point):
            self.preparing_frame[bit][...] = 0

    @staticmethod
    def __calculate_crc(data):
        return crc(data)

    def get(self):
        try:
            if self.buffer:
                data, t = self.buffer.popleft()
                return data, t
            else:
                return None, None
        except Exception as e:
            raise Exception("Unexpected Exception")

    def get_last(self):
        try:
            if self.buffer:
                data, t = self.buffer.pop()
                self.buffer.clear()
                return data, t
            else:
                return None, None
        except Exception as e:
            raise Exception("Unexpected Exception")



