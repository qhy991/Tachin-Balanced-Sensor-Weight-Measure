# USB通讯协议读取示例代码

import usb.core
import threading
from collections import deque
import time
import numpy as np
from backends.decoding import Decoder
from array import array
import warnings

DELAY = 0.002
MESSAGE_SIZE = 1024


class UsbBackend:
    def __init__(self, config_array):
        # 在子线程中读取USB协议传来的数据。主线程会将数据取走
        # USB相关
        self.bc = BulkChannel()
        self.epi_t = None
        self.epvo_t = None
        self.epvi_t = None
        # 解包
        self.decoder = Decoder(config_array)
        self.err_queue = deque(maxlen=1)
        #
        self.active = False
        #
        self.lock_devs = threading.Lock()
        # 校验
        self.dna = None
        self.key_set = False

    def get_available_sources(self):
        names_found = None
        with self.lock_devs:
            self.bc.refresh_usb_devices()
            names_found = [_.bcdDevice for _ in self.bc.devices_found]
        return names_found

    def start_by_idx(self, idx):
        try:
            if self.epi_t is None:
                # 似乎由于USB的缺陷，无法重连
                with self.lock_devs:
                    interface_t, epi_t, epvo_t, epvi_t\
                        = self.bc.get_dev_interface_epio(device=self.bc.devices_found[idx])
                self.epi_t = epi_t
                self.epvo_t = epvo_t
                self.epvi_t = epvi_t
            self.active = True
            threading.Thread(target=self.__read_forever, daemon=True).start()
            return True
        except usb.core.USBError as e:
            print('Failed to connect to USB device')
            raise e

    def start(self, rev):
        # 通过REV号区分不同的采集卡
        try:
            # 此处待优化：暂时没有找到优雅地关闭已打开的USB口的方法
            # 因此，进程一旦曾经成功连接到USB端口，就无法再改变，除非重启程序
            if self.epi_t is None:
                self.bc.update_backend(self.bc.get_backend())
                interface_t, epi_t, epvo_t, epvi_t = self.bc.get_interfaces_list(rev)
                self.epi_t = epi_t
                self.epvo_t = epvo_t
                self.epvi_t = epvi_t
            self.active = True
            threading.Thread(target=self.__read_forever, daemon=True).start()
            return True
        except usb.core.USBError as e:
            print('Failed to connect to USB device')
            raise e

    def query_dna(self):
        assert self.active
        # 发送查询DNA的指令
        while True:
            try:
                self.epvi_t.read(1)
            except usb.core.USBError as e:
                break
        self.epvo_t.write(b'\x3c\x01')
        time.sleep(DELAY)  # 等待设备响应
        dna_response = array('B', [])
        while True:
            try:
                dna_response.extend(self.epvi_t.read(1))
            except usb.core.USBError as e:
                break
        if dna_response:
            try:
                parts = [dna_response[i] << 8 | dna_response[i + 1] for i in range(0, 8, 2)]
                dna = '_'.join(f'{p:04X}' for p in parts)
                print(f"采集卡编号：{dna}")
                return dna
            except:
                print("OTA功能出错")
                return None
        else:
            print("采集卡不具备OTA功能")
            return None

    def set_key(self, key_str):
        # key为字符串输入，形如D854_2791_C023_89B4
        assert self.active
        assert isinstance(key_str, str) and key_str.__len__() == 19, "Key格式错误"
        try:
            while True:
                try:
                    self.epvi_t.read(1)
                except:
                    break
            self.epvo_t.write(b'\x3c\x02')
            time.sleep(DELAY)
            hex_parts = key_str.split('_')
            key_bytes = b''.join(int(part, 16).to_bytes(2, 'big') for part in hex_parts)
            while True:
                try:
                    self.epvi_t.read(1)
                except:
                    break
            self.epvo_t.write(key_bytes)
            time.sleep(DELAY)
            self.epvo_t.write(b'\x3c\x03')
            time.sleep(DELAY)
            read = self.epvi_t.read(16).tobytes()
            # read形如“array('B', [85, 170])”。将它与55aa或3355对比
            if read == b'\x55\xaa':
                self.key_set = True
                return True
            elif read == b'\x33\x55':
                self.key_set = False
                warnings.warn('激活失败')
                return False
            else:
                warnings.warn('激活状态未知')
                return False
        except usb.core.USBError as e:
            warnings.warn("板卡版本可能不匹配")
            return True

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
    idVendor = 0x04b4
    idProduct = 0x1004

    def __init__(self):
        self.LIB_PATH = 'C:\\Windows\\System32\\libusb0-1.0.dll'
        self.interface_index = ''
        self.backend = None
        self.devices_found = []

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

    def refresh_usb_devices(self):
        if not self.backend:
            self.update_backend(self.get_backend())
        devs = usb.core.find(backend=self.backend,
                             idVendor=self.idVendor, idProduct=self.idProduct,
                             find_all=True)
        self.devices_found = devs

    def get_usb_devices(self, rev):
        """获取当前系统上挂载的设备iter"""
        # 若rev为None,则返回所有设备
        # 若rev为int，则返回rev对应的设备，若没有则会报错
        # 如果没有后端,就尝试添加一个
        if not self.backend:
            self.update_backend(self.get_backend())
        # print(usb.core.show_devices(backend=backend))
        # find USB devices, 记得添加backend参数
        # 0x04b4和0x1004是采集卡的固定参数
        devs = usb.core.find(backend=self.backend,
                             idVendor=self.idVendor, idProduct=self.idProduct,
                             find_all=True)
        if rev is None:
            return devs
        else:
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

        def custom_match_data_in(e):
            addr = e.bEndpointAddress
            ep_num = addr & 0x0f
            flag_in = usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            flag_ep = ep_num == 0x06
            return flag_in and flag_ep

        def custom_match_validate_query(e):
            addr = e.bEndpointAddress
            ep_num = addr & 0x0f
            flag_out = usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            flag_ep = ep_num == 0x04
            return flag_out and flag_ep

        def custom_match_validate_receive(e):
            addr = e.bEndpointAddress
            ep_num = addr & 0x0f
            flag_in = usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            flag_ep = ep_num == 0x08
            return flag_in and flag_ep

        epi = usb.util.find_descriptor(
            interface,
            custom_match=custom_match_data_in)

        epvo = usb.util.find_descriptor(
            interface,
            custom_match=custom_match_validate_query)

        epvi = usb.util.find_descriptor(
            interface,
            custom_match=custom_match_validate_receive
        )

        return interface, epi, epvo, epvi

    def get_interfaces_list(self, rev):
        """仅仅只返回由现存interfaces name组成的list"""
        devices = self.get_usb_devices(rev)
        dev_t = devices
        # 返回cfg的interface/endpoint bulk out/endpoint bulk in
        interface_t, epi_t, epvo_t, epvi_t = self.get_dev_interface_epio(device=dev_t)
        return interface_t, epi_t, epvo_t, epvi_t

