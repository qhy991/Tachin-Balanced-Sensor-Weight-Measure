import time
import socket
import threading
import atexit
import warnings
from backends.abstract_sensor_driver import AbstractSensorDriver
from server.server_utils import wait, CommandCodes, crc
import numpy as np


QUERY_FAIL_LENGTH = 1


class SocketServer:

    def __init__(self, sensor_class, source, port_start, max_client_count, client_timeout=60, *args, **kwargs):
        self.sensor: AbstractSensorDriver = sensor_class(*args, **kwargs)
        self.source = source
        self.port_start = port_start
        self.max_client_count = max_client_count
        self.client_timeout = client_timeout
        # 搭建一对多的socket服务端
        self.servers = []
        for i in range(max_client_count):
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 设置非阻塞
            server.setblocking(False)
            # 设置输出缓冲区大小
            server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 ** 16)
            server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            server.bind(("localhost", self.port_start + i))
            server.listen(1)  # 最大连接数
            self.servers.append(server)
        print(f"开始在端口{self.port_start}~{self.port_start + max_client_count - 1}上监听")
        self.clients = []
        self.activate = False
        self.initiate()
        atexit.register(self.terminate)

    def start(self):
        self.sensor.connect(self.source)

    def handle_client(self, client_id):
        while True:
            try:
                client, _ = self.servers[client_id].accept()
                print(f'客户端{client_id}连接成功')
                break
            except BlockingIOError:
                wait()
        time_last = time.time()
        while True:
            try:
                success_flag = True
                time_now = time.time()
                command = b''
                try:
                    command = client.recv(16)
                    if command.__len__() == 0:
                        success_flag = False
                except BlockingIOError:
                    success_flag = False
                if not success_flag:
                    wait()
                    if time_now - time_last > self.client_timeout:
                        break
                    continue
                time_last = time_now
                if command.__len__() >= 2 and command[:2] == bytes([0x55, 0xaa]) and command[-1] == crc(command[:-1]):
                    if command[3] == CommandCodes.NULL:
                        # NULL指令：0x55, 0xaa, 指令号(0x00), CRC*1
                        message = [0xaa, 0x55, client_id, CommandCodes.NULL, 0x00, 0x00]
                        client.sendall(bytes(message + [crc(message)]))
                    elif command[3] == CommandCodes.LATEST_FRAME:
                        # QUERY指令：0x55, 0xaa, 指令号(0x01), CRC*1
                        data, t = self.sensor.get_last()
                        if data is not None:
                            data_bytes = bytes(data)
                            t_ms = np.uint16((t * 1000) % (2 ** 16))
                            message = bytes([0xaa, 0x55, client_id, CommandCodes.LATEST_FRAME,
                                             *(1 + 2 + data_bytes.__len__()).to_bytes(2, 'big'),
                                             0x01])\
                                      + t_ms.tobytes() + data_bytes
                            message += bytes([crc(message)])
                            client.sendall(message)
                        else:
                            message = [0xaa, 0x55, client_id, CommandCodes.LATEST_FRAME,
                                       *QUERY_FAIL_LENGTH.to_bytes(2, 'big'), 0x00]
                            client.sendall(bytes(message + [crc(message)]))
                    else:
                        if command:
                            print(f"收到未知指令：{command}")
                else:
                    print(f"收到CRC校验错误的指令：{command}")
            except ConnectionResetError:
                break
        client.close()
        print(f'客户端{client_id}断开连接')
        self.servers[client_id].close()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("localhost", self.port_start + client_id))
        server.listen(1)  # 最大连接数
        self.servers[client_id] = server
        threading.Thread(target=self.handle_client, args=(client_id,)).start()

    def initiate(self):
        try:
            assert self.sensor.connect(self.source)
        except Exception as e:
            warnings.warn("传感器连接失败")
        for c_id in range(self.max_client_count):
            threading.Thread(target=self.handle_client, args=(c_id, )).start()

    def terminate(self):
        self.activate = False
        for server in self.servers:
            server.close()

