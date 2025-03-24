# USB通讯协议读取示例代码

import usb.core
import threading
from collections import deque
import time
import numpy as np
from backends.decoding import Decoder


MESSAGE_SIZE = 1024


class UsbBackend:
    def __init__(self, config_array):
        # 在子线程中读取USB协议传来的数据。主线程会将数据取走
        # USB相关
        self.bc = BulkChannel()
        self.epi_t = None
        # 解包
        self.decoder = Decoder(config_array)
        self.err_queue = deque(maxlen=1)
        #
        self.active = False

    def start(self, rev):
        # 通过REV号区分不同的采集卡
        try:
            # 此处待优化：暂时没有找到优雅地关闭已打开的USB口的方法
            # 因此，进程一旦曾经成功连接到USB端口，就无法再改变，除非重启程序
            if self.epi_t is None:
                self.bc.update_backend(self.bc.get_backend())
                interface_t, epo_t, epi_t = self.bc.get_interfaces_list(rev)
                self.epi_t = epi_t
            self.active = True
            threading.Thread(target=self.__read_forever, daemon=True).start()
            return True
        except usb.core.USBError as e:
            print('Failed to connect to USB device')
            raise e

    def stop(self):
        self.active = False
        return True

    def __read_forever(self):
        while self.active:
            self.__read()

    def __read(self):
        try:
            last_message = self.epi_t.read(MESSAGE_SIZE)
        except usb.core.USBError as e:
            self.stop()
            self.err_queue.append(e)
            print(e)
            raise Exception('USB read/write failed')
        self.decoder(last_message)

    def get(self):
        return self.decoder.get()

    def get_last(self):
        return self.decoder.get_last()


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
    from config import config_array
    ub = UsbBackend(config_array)  # 使用中支持在UsbBackend里存一些数后一起取出，默认16帧
    ub.start(2)  # 卡号
    t_last = None
    while True:
        data, t = ub.get()
        if data is not None:
            print(np.max(data), np.mean(data))
            if t_last is not None:
                print(t - t_last)
            t_last = t
        time.sleep(0.001)
    pass
