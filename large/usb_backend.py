# USB通讯协议读取示例代码

import usb.core
import threading
from collections import deque
import time
import json
import numpy as np
import crcmod.predefined

crc = crcmod.predefined.mkCrcFun('crc-ccitt-false')

MESSAGE_SIZE = 1024
OFFSET_0 = 0
OFFSET_1 = 256
PACKAGE_SIZE = 136
PACKAGE_COUNT_IN_FRAME = 64
SENSOR_SIZE = 64
BYTES_PER_POINT = 2
POINTS_PER_PACKAGE = 64

FOLDING = json.load(open('config_array.json', 'rt'))['column_array']


class UsbBackend:
    def __init__(self, buffer_length):
        # buffer_length为储存的长度
        # 在子线程中读取USB协议传来的数据。主线程会将数据取走

        # USB相关
        self.bc = BulkChannel()
        self.epi_t = None

        # 临时容器
        self.last_message = np.ndarray((MESSAGE_SIZE,), dtype=np.uint8)
        self.preparing_frame = [np.zeros((SENSOR_SIZE * SENSOR_SIZE,), dtype=np.uint8) for _ in range(BYTES_PER_POINT)]
        self.preparing_cursor = 0
        self.finished_frame = [np.zeros((SENSOR_SIZE * SENSOR_SIZE,), dtype=np.uint8) for _ in range(BYTES_PER_POINT)]
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

    def start(self, rev):
        # 通过REV号区分不同的采集卡
        self.__preset_buffer()
        try:
            # 此处待优化：暂时没有找到优雅地关闭已打开的USB口的方法
            # 因此，进程一旦曾经成功连接到USB端口，就无法再改变，除非重启程序
            if self.epi_t is None:
                self.bc.update_backend(self.bc.get_backend())
                interface_t, epo_t, epi_t = self.bc.get_interfaces_list(rev)
                self.epi_t = epi_t

            self.active = True
            threading.Thread(target=self.read_forever, daemon=True).start()
            return True
        except usb.core.USBError as e:
            print('Failed to connect to USB device')
            raise e

    def __preset_buffer(self):
        for _ in range(self.buffer.maxlen):
            self.buffer.append((self.finished_frame, self.last_finish_time))
        self.buffer.clear()

    def stop(self):
        self.active = False
        return True

    def get_interval(self):
        return self.last_interval

    def read_forever(self):
        while self.active:
            self.read()

    def read(self):
        try:
            self.last_message[...] = self.epi_t.read(MESSAGE_SIZE)
        except usb.core.USBError as e:
            self.stop()
            self.err_queue.append(e)
            print(e)
            raise Exception('USB read/write failed')

        if len(self.message_cache) == 0:
            self.message_cache = self.last_message.copy()
        else:
            self.message_cache = np.concatenate((self.message_cache, self.last_message), axis=0)

        offset = 0
        m = len(self.message_cache)

        while offset < (m - PACKAGE_SIZE):
            # 格式：AA 10 33 “长度” 帧号 包号 数据 CRC
            self.warn_info = ''
            if (self.message_cache[offset] == 0xaa)\
                    & (self.message_cache[offset + PACKAGE_SIZE] == 0xaa):

                # 包头效验正确
                frame_number = self.message_cache[offset + 4]
                package_number = self.message_cache[offset + 5]
                data = self.message_cache[offset
                                          :offset + 6 + POINTS_PER_PACKAGE * BYTES_PER_POINT]
                crc_received = self.message_cache[offset + 6 + POINTS_PER_PACKAGE * BYTES_PER_POINT
                                                  :offset + 8 + POINTS_PER_PACKAGE * BYTES_PER_POINT]
                crc_calculated = self.__calculate_crc(data)
                if crc_received[0] * 256 + crc_received[1] != crc_calculated:
                    self.warn_info = 'CRC check failed'
                    flag = False
                else:
                    flag = self.__validate_package(frame_number, package_number)

                if flag:
                    self.__write_data(offset, package_number)
                offset += PACKAGE_SIZE
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
                if self.last_package_number == PACKAGE_COUNT_IN_FRAME - 1:
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
        self.preparing_cursor = POINTS_PER_PACKAGE * package_number.astype(np.uint16)
        begin = self.preparing_cursor
        end = self.preparing_cursor + POINTS_PER_PACKAGE
        slice_to = slice(begin, end)
        slices_from = [slice(offset + 6 + bit, offset + 6 + POINTS_PER_PACKAGE * BYTES_PER_POINT + bit, BYTES_PER_POINT) for bit in range(BYTES_PER_POINT)]
        for bit, slice_from in enumerate(slices_from):
            self.preparing_frame[bit][slice_to] = self.message_cache[slice_from][FOLDING]

    def read_void(self):
        try:
            self.last_message[...] = self.epi_t.read(MESSAGE_SIZE)
        except usb.core.USBError as e:
            print(e)

    def __finish_frame(self):
        with self.lock:
            for bit in range(BYTES_PER_POINT):
                self.finished_frame[bit][...] = self.preparing_frame[bit][...]
                self.preparing_cursor = 0
            time_now = time.time()
            if self.last_finish_time > 0:
                self.last_interval = time_now - self.last_finish_time
            self.last_finish_time = time_now
            self.buffer.append((self.finished_frame, self.last_finish_time))

    def __abort_frame(self):
        for bit in range(BYTES_PER_POINT):
            self.preparing_frame[bit][...] = 0
            self.preparing_cursor = 0

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

class BulkChannel:
    # USB协议相关
    # USB协议存在平台差异。代码是Windows下的实现

    def __init__(self):
        self.LIB_PATH = 'C:\\Windows\\System32\\libusb0-1.0.dll'
        self.interface_index = ''
        self.backend = None

    def update_backend(self, backend):
        """更新当前后端"""
        self.backend = backend

    def get_backend(self):
        """获取当前系统后端"""
        from usb.backend import libusb1 as libusb0
        backend = libusb0.get_backend()
        if not backend:
            raise Exception('Failed to load USB backend. Missing libusb-1.0.dll')
        return backend

    def get_usb_devices(self, rev):
        """获取当前系统上挂载的设备iter"""
        # 如果没有后端,就尝试添加一个
        if not self.backend:
            self.update_backend(self.get_backend())
        # print(usb.core.show_devices(backend=backend))
        # find USB devices, 记得添加backend参数
        # 0x04b4和0x1004是采集卡的固定参数
        devs = usb.core.find(backend=self.backend, idVendor=0x04b4, idProduct=0x1004, find_all=True)
        for dev in devs:
            if dev.bcdDevice == rev:
                return dev
        raise Exception('USB device not found or incorrect REV number')

    def get_dev_interface_epio(self, device):
        """获取当前dev上的interface和相应的epo/epi"""
        try:
            device.set_configuration()
        except NotImplementedError as e:
            print(e)
            raise Exception('Device configuration failed. Incorrect driver version. Use Zadig to install driver')
        cfg = device.get_active_configuration()
        interface = cfg[(0, 0)]

        epo = usb.util.find_descriptor(
            interface,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)

        epi = usb.util.find_descriptor(
            interface,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)

        return interface, epo, epi

    def get_interfaces_list(self, rev):
        """仅仅只返回由现存interfaces name组成的list"""
        devices = self.get_usb_devices(rev)
        dev_t = devices
        # 返回cfg的interface/endpoint bulk out/endpoint bulk in
        interface_t, epo_t, epi_t = self.get_dev_interface_epio(device=dev_t)
        return interface_t, epo_t, epi_t


if __name__ == '__main__':
    # 简单的调用测试
    ub = UsbBackend(16)  # 使用中支持在UsbBackend里存一些数后一起取出。如果发现数据不完整，酌情增加该数值
    ub.start(1)  # 卡号
    while True:
        bits, t = ub.get()
        if bits is not None:
            print(bits)
            print(t)
        time.sleep(0.001)
    pass
