from data_handler.data_handler import DataHandler
import socket
from threading import Thread
import atexit
import time
from server.utils import crc, CommandCodes, wait
import warnings
from large.sensor_driver import LargeSensorDriver

QUERY_SUCCESS_LENGTH = 1 + 2 + 2 * 4096
QUERY_FAIL_LENGTH = 1


class SocketServer:
    def __init__(self, device_number, max_len=4, port_start=10080, max_client_count=16, client_timeout=60):
        self.data_handler = DataHandler(max_len=max_len, template_sensor_driver=LargeSensorDriver)
        self.device_number = device_number
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
        self.data_thread = Thread(target=self.trigger_forever, daemon=True)
        self.initiate()
        atexit.register(self.terminate)

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
                        if self.data_handler.value:
                            time_after_begin = self.data_handler.time_ms[-1]
                            value = self.data_handler.value[-1]
                            message = bytes([0xaa, 0x55, client_id, CommandCodes.LATEST_FRAME,
                                             *QUERY_SUCCESS_LENGTH.to_bytes(2, 'big'),
                                             0x01])\
                                      + time_after_begin.tobytes() + bytes(value)
                            message += bytes([crc(message)])
                            # print(f"数据时间：{time_after_begin + self.data_handler.begin_time}")
                            # print(f"发送时间：{time.time()}")
                            client.sendall(message)
                        else:
                            # print(f"发送时间：{time.time()}")
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
        Thread(target=self.handle_client, args=(client_id,), daemon=True).start()

    def initiate(self):
        if not self.data_handler.driver.connected:
            try:
                flag = self.data_handler.driver.connect(self.device_number)
                if flag:
                    atexit.register(self.data_handler.driver.disconnect)
            except Exception as e:
                warnings.warn("采集卡连接失败")
        self.data_thread.start()
        for c_id in range(self.max_client_count):
            Thread(target=self.handle_client, args=(c_id, ), daemon=True).start()

    def terminate(self):
        self.activate = False
        for server in self.servers:
            server.close()

    def trigger_forever(self):
        while True:
            self.data_handler.trigger()
            time.sleep(0.001)


if __name__ == '__main__':
    server = SocketServer(2)
    while True:
        time.sleep(1.)

