from abstract_sensor_driver import AbstractSensorDriver
import numpy as np
import time
import usb.core
import threading
from collections import deque
from config import config_array
import copy


class LargeSensorDriver(AbstractSensorDriver):
    # 传感器驱动

    SENSOR_SHAPE = (64, 64)  # 形状

    SCALE = (32768. * 25. / 5.) ** -1  # 示数对应到电阻倒数的系数

    def __init__(self):
        super(LargeSensorDriver, self).__init__()
        self.sensor_backend = SensorBackend(16)

    @property
    def connected(self):
        return self.sensor_backend.active

    def connect(self, port):
        return self.sensor_backend.start(int(port))

    def disconnect(self):
        return self.sensor_backend.stop()

    def get(self):
        if self.sensor_backend.err_queue:
            raise self.sensor_backend.err_queue.popleft()
        if self.sensor_backend.buffer:
            self.sensor_backend.lock.acquire()
            bits_and_t = self.sensor_backend.buffer.popleft()
            bits_and_t = (copy.deepcopy(bits_and_t[0]), bits_and_t[1])
            self.sensor_backend.lock.release()
            data = ((bits_and_t[0][0].reshape(self.SENSOR_SHAPE).astype(np.int8).astype(np.int16)) * 256) \
                   + bits_and_t[0][1].reshape(self.SENSOR_SHAPE).astype(np.int16)
            # for i in range(self.SENSOR_SHAPE[0]):
            #     for j in range(self.SENSOR_SHAPE[1]):
            #         if data[i, j] >= 255:
            #             print(f"{data[i, j]} = {bits_and_t[0][0].reshape(self.SENSOR_SHAPE)[i, j].astype(np.int8).astype(np.int16)}"
            #                   f" * 256 + {bits_and_t[0][1].reshape(self.SENSOR_SHAPE)[i, j]}")
            t = bits_and_t[1]
            return data, t
        else:
            return None, None


MESSAGE_SIZE = 1024
OFFSET_0 = 0
OFFSET_1 = 256
PACKAGE_SIZE = 136  # 256  #0xaa10/0x3388(4)+ frame_cnt(1) + packet_cnt(1)+ 64*2 + crc16(2)
PACKAGE_COUNT_IN_FRAME = 64
SENSOR_SIZE = 64
BYTES_PER_POINT = 2
POINTS_PER_PACKAGE = 64

FOLDING = config_array["column_array"]

# FOLDING = [FOLDING.index(_) for _ in range(64)]


class SensorBackend:
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
        self.message_cache = np.empty((0), dtype=np.uint8)
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
        self.__preset_buffer()
        try:
            if self.epi_t is None:
                self.bc.update_backend(self.bc.get_backend())
                interface_t, epo_t, epi_t = self.bc.get_interfaces_list(rev)
                self.epi_t: usb.core.Endpoint = epi_t

            self.active = True
            threading.Thread(target=self.read_forever, daemon=True).start()
            return True
        except usb.core.USBError as e:
            print("连接采集卡失败")
            raise e

    def __preset_buffer(self):
        for i in range(self.buffer.maxlen):
            self.buffer.append((self.finished_frame, self.last_finish_time))
        self.buffer.clear()

    def stop(self):
        # self.__init__(self.__buffer_length)
        self.active = False
        return True

    def get_interval(self):
        return self.last_interval

    def read_forever(self):
        while self.active:
            self.read()

    def summary_last_message(self):
        str = ""
        for i_offset, offset in enumerate([OFFSET_0, OFFSET_1]):
            str += f"第{i_offset + 1}段："
            str += f"\t包头：{self.last_message[offset:offset + 4]}；"
            str += f"\t帧号：{self.last_message[offset + 4]}，行号：{self.last_message[offset + 5]}\n"
            # str += f"\t数据：{self.last_message[offset + 6:offset + 134]}\n"
        return str

    def read(self):
        # 具体的校验逻辑还有不少问题，包括没有校验CRC等
        try:
            self.last_message[...] = self.epi_t.read(MESSAGE_SIZE)
            # self.last_message[...] = self.epi_t.read(MESSAGE_SIZE)
            # self.last_message[...] = self.epi_t.read(MESSAGE_SIZE)
        except usb.core.USBError as e:
            self.stop()
            self.err_queue.append(e)
            print(e)
            raise Exception("USB端口读写失败")
        # 新采集数据并入列表
        # global  message_cache0
        if (len(self.message_cache) == 0):
            self.message_cache = self.last_message.copy()
        else:
            w = np.concatenate((self.message_cache, self.last_message), axis=0)
            self.message_cache = w
        offset = 0
        m = len(self.message_cache)

        while (offset < (m - PACKAGE_SIZE)):  # range(0,MESSAGE_SIZE-):     #[OFFSET_0, OFFSET_1]:
            # 格式：AA 10 33 “长度” 帧号 包号 数据 CRC
            self.warn_info = ''
            if ((self.message_cache[offset] == 0xaa) & (self.message_cache[offset + PACKAGE_SIZE] == 0xaa)):
                # 包头效验正确
                frame_number = self.message_cache[offset + 4]
                package_number = self.message_cache[offset + 5]
                if self.last_frame_number is None:
                    flag = (package_number == 0)
                    if flag:
                        self.last_frame_number = frame_number
                        self.last_package_number = package_number
                    else:
                        # self.warn_info = '尚未初始化'
                        self.warn_info = ''
                else:
                    if (package_number == 0):
                        if (self.last_package_number == PACKAGE_COUNT_IN_FRAME - 1):
                            self.__finish_frame()
                            flag = True
                        else:
                            self.warn_info = '包号错误'
                            flag = False
                            # return flag
                        self.last_frame_number = frame_number
                        self.last_package_number = package_number
                    elif self.last_package_number is None:
                        self.warn_info = '等待下一帧'
                        flag = False
                    else:
                        flag = (package_number == self.last_package_number + 1) \
                               and (frame_number == self.last_frame_number)
                        if not flag:
                            self.warn_info = '包号错误'
                        # if frame_number != self.last_frame_number or package_number > self.last_package_number + 1:
                        # self.__abort_frame()
                        # self.last_package_number = None
                        else:
                            self.last_package_number = package_number
                # 有效的包
                if flag:
                    # 写数
                    self.preparing_cursor = POINTS_PER_PACKAGE * package_number.astype(np.uint16)
                    begin = self.preparing_cursor
                    end = self.preparing_cursor + POINTS_PER_PACKAGE
                    slice_to = slice(begin, end)
                    slices_from = [slice(offset + 6 + bit,
                                         offset + 6 + POINTS_PER_PACKAGE * BYTES_PER_POINT + bit,
                                         BYTES_PER_POINT)
                                   for bit in range(BYTES_PER_POINT)]
                    #
                    for bit, slice_from in enumerate(slices_from):
                        # self.preparing_frame[bit][slice_to] = self.last_message[slice_from][FOLDING][FOLDING_]
                        self.preparing_frame[bit][slice_to] = self.message_cache[slice_from][FOLDING]
                        pass
                        # 记得验一下
                ##else:
                # break
                offset = offset + PACKAGE_SIZE
            else:
                offset = offset + 1
                # self.warn_info = '未找到包头'
                self.warn_info = ''

            if self.warn_info:
                print(self.warn_info)
            else:
                pass

        # return flag
        s = self.message_cache
        self.message_cache = s[offset:]
        # print(s)
        # print(self.message_cache)
        # return flag

    def read_void(self):
        try:
            self.last_message[...] = self.epi_t.read(MESSAGE_SIZE)
        except usb.core.USBError as e:
            print(e)

    def __finish_frame(self):
        self.lock.acquire()
        for bit in range(BYTES_PER_POINT):
            self.finished_frame[bit][...] = self.preparing_frame[bit][...]
            # self.preparing_frame[bit][...] = 0
            self.preparing_cursor = 0
        time_now = time.time()
        if self.last_finish_time > 0:
            self.last_interval = time_now - self.last_finish_time
        self.last_finish_time = time_now
        # SENSOR_SHAPE = (64, 64)
        # data = ((self.finished_frame[0].reshape(SENSOR_SHAPE).astype(np.int8).astype(np.int16)) * 256) \
        #        + self.finished_frame[1].reshape(SENSOR_SHAPE).astype(np.int16)
        # for i in range(SENSOR_SHAPE[0]):
        #     for j in range(SENSOR_SHAPE[1]):
        #         if data[i, j] >= 255:
        #             print(
        #                 f"{data[i, j]} = {self.finished_frame[0].reshape(SENSOR_SHAPE)[i, j].astype(np.int8).astype(np.int16)}"
        #                 f" * 256 + {self.finished_frame[1].reshape(SENSOR_SHAPE)[i, j]} BACKEND")
        self.buffer.append((self.finished_frame, self.last_finish_time))
        self.lock.release()

    def __abort_frame(self):
        for bit in range(BYTES_PER_POINT):
            self.preparing_frame[bit][...] = 0
            self.preparing_cursor = 0


class BulkChannel:
    # USB协议相关

    def __init__(self):
        ##""'C:\\Windows\\System32\\libusb0-1.0.dll' ""
        self.LIB_PATH = 'C:\\Windows\\System32\\libusb0-1.0.dll'
        self.interface_index = ''
        self.backend = None

    def update_backend(self, backend):
        """更新当前后端"""
        self.backend = backend

    def get_backend(self):
        """获取当前系统后端"""
        from usb.backend import libusb1 as libusb0

        # backend = libusb0.get_backend(lambda x: self.LIB_PATH)
        backend = libusb0.get_backend()

        if not backend:
            raise Exception('加载USB后端失败。可能是缺少libusb-1.0.dll')
        return backend

    def get_usb_devices(self, rev):
        """获取当前系统上挂载的设备iter"""
        # 如果没有后端,就尝试添加一个
        if not self.backend:
            self.update_backend(self.get_backend())
        # print(usb.core.show_devices(backend=backend))

        # find USB devices, 记得添加backend参数
        devs = usb.core.find(backend=self.backend, idVendor=0x04b4, idProduct=0x1004, find_all=True)
        for dev in devs:
            if dev.bcdDevice == rev:
                return dev
        raise Exception('未找到USB设备。请确认采集卡已正常连接')

    def get_dev_interface_epio(self, device):
        """获取当前dev上的interface和相应的epo/epi"""
        try:
            device.set_configuration()
        except NotImplementedError as e:
            print(e)
            raise Exception('设备配置失败，可能是驱动程序版本不正确。请使用Zadig安装WinUSB驱动')
        cfg = device.get_active_configuration()
        interface = cfg[(0, 0)]

        epo = usb.util.find_descriptor(
            interface,
            # match the first OUT endpoint
            custom_match=lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_OUT)

        epi = usb.util.find_descriptor(
            interface,
            # match the first IN endpoint
            custom_match=lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_IN)

        return interface, epo, epi

    def get_interfaces_list(self, rev):
        """仅仅只返回由现存interfaces name组成的list"""
        devices = self.get_usb_devices(rev)
        dev_t = devices
        # 返回cfg的interface/endpoint bulk out/endpoint bulk in
        interface_t, epo_t, epi_t = self.get_dev_interface_epio(device=dev_t)
        return interface_t, epo_t, epi_t
