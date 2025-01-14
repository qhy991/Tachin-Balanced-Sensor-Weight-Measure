# 公用的解码程序

import time
import numpy as np
import crcmod.predefined

crc = crcmod.predefined.mkCrcFun('crc-ccitt-false')

HEAD_LENGTH = 6
CRC_LENGTH = 2


class Decoder:
    def __init__(self, config_array):
        self.row_array = config_array['row_array']
        self.column_array = config_array['column_array']
        self.message_size = config_array.get('message_size', 1024)  # 默认
        self.bytes_per_point = config_array.get('bytes_per_point', 2)  # 默认
        self.sensor_shape = (self.row_array.__len__(), self.column_array.__len__())
        self.package_size = HEAD_LENGTH + CRC_LENGTH + self.sensor_shape[1] * self.bytes_per_point

    def __call__(self, message):
        offset = 0
        m = len(message)

        while message.__len__() < self.package_size:
            # 格式：AA 10 33 “长度” 帧号 包号 数据 CRC
            self.warn_info = ''
            if (message[offset] == 0xaa)\
                    & (message[offset + self.package_size] == 0xaa):

                # 包头效验正确
                frame_number = message[offset + 4]
                package_number = message[offset + 5]
                data = message[offset
                               :offset + HEAD_LENGTH + self.sensor_shape[1] * self.bytes_per_point]
                crc_received = message[offset + HEAD_LENGTH + self.sensor_shape[1] * self.bytes_per_point
                                       :offset + HEAD_LENGTH + CRC_LENGTH + self.sensor_shape[1] * self.bytes_per_point]
                crc_calculated = self.__calculate_crc(data)
                if crc_received[0] * 256 + crc_received[1] != crc_calculated:
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
                    self.warn_info = 'Package number error'
                    flag = False
                self.last_frame_number = frame_number
                self.last_package_number = package_number
            elif self.last_package_number is None:
                self.warn_info = 'Waiting for next frame'
                flag = False
            else:
                flag = (package_number == self.last_package_number + 1) and (frame_number == self.last_frame_number)
                if not flag:
                    self.warn_info = 'Package number error'
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
        except usb.core.USBError as e:
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

