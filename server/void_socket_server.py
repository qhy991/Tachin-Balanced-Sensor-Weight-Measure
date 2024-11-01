
import socket
from threading import Thread
import atexit
import time
from server.utils import crc, CommandCodes, wait
import warnings

QUERY_SUCCESS_LENGTH = 1 + 4 + 4 * 4096
QUERY_FAIL_LENGTH = 1


class SocketServer:
    def __init__(self, max_len=16, port=10080, max_client_count=16, client_timeout=10):
        self.port = port
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
            server.bind(("localhost", self.port + i))
            server.listen(1)  # 最大连接数
            self.servers.append(server)
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
                try:
                    command = client.recv(16)
                except BlockingIOError:
                    wait()
                    continue
                if command == bytes([0x55, 0xaa, 0x00, CommandCodes.NULL] + [crc([0x55, 0xaa, 0x00, CommandCodes.NULL])]):
                    # NULL指令：0x55, 0xaa, 指令号(0x00), CRC*1
                    message = [0xaa, 0x55, client_id, CommandCodes.NULL]
                    print(f"发送时间：{time.time()}")
                    client.sendall(bytes(message + [crc(message)]))
                elif command == bytes([0x55, 0xaa, 0x00, CommandCodes.LATEST_FRAME] + [crc([0x55, 0xaa, 0x00, CommandCodes.LATEST_FRAME])]):
                    # QUERY指令：0x55, 0xaa, 指令号(0x01), CRC*1
                    print(f"发送时间：{time.time()}")
                    # QUERY应答：0xaa, 0x55, 指令号(0x00), 失败标记, 时间*4, 数据*4*4096, CRC*1
                    message = [0xaa, 0x55, client_id, CommandCodes.LATEST_FRAME,
                               *QUERY_SUCCESS_LENGTH.to_bytes(2, 'big'), 0x00]
                    client.sendall(bytes(message + [crc(message)]))
                else:
                    if command:
                        print(f"收到未知指令：{command}")
                time_now = time.time()
                if time_now - time_last > self.client_timeout:
                    break
                time_last = time_now
            except ConnectionResetError:
                break
        client.close()
        print(f'客户端{client_id}断开连接')
        self.servers[client_id].close()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("localhost", self.port + client_id))
        server.listen(1)  # 最大连接数
        self.servers[client_id] = server
        Thread(target=self.handle_client, args=(client_id,), daemon=True).start()

    def initiate(self):
        self.data_thread.start()
        for c_id in range(self.max_client_count):
            Thread(target=self.handle_client, args=(c_id, ), daemon=True).start()

    def terminate(self):
        self.activate = False
        for server in self.servers:
            server.close()

    def trigger_forever(self):
        while True:
            time.sleep(0.001)


if __name__ == '__main__':
    server = SocketServer()
    while True:
        time.sleep(1.)

