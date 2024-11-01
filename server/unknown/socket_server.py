from ordinary.data_handler import DataHandler
import socket
import select
from threading import Thread
import atexit
import time
from server.utils import crc, CommandCodes
import warnings

QUERY_SUCCESS_LENGTH = 1 + 4 + 4 * 4096
QUERY_FAIL_LENGTH = 1


class SocketServer:
    def __init__(self, max_len=16, port=10080, max_client_count=16, client_timeout=10):
        self.data_handler = DataHandler(max_len=max_len)
        self.port = port
        self.max_client_count = max_client_count
        self.client_timeout = client_timeout
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setblocking(False)
        server.bind(("localhost", self.port))
        server.listen(max_client_count)  # 最大连接数
        self.server = server
        self.activate = False
        self.data_thread = Thread(target=self.trigger_forever, daemon=True)
        self.initiate()
        atexit.register(self.terminate)

    def start(self):
        self.handle_clients()

    def broadcast(self, message, clients):
        for client in clients:
            client.send(message)

    def handle_clients(self):
        inputs = [self.server]
        outputs = []
        while True:
            message = self.make_message()
            readable, _, _ = select.select(inputs, outputs, inputs)
            for s in readable:
                if s is self.server:
                    client, _ = self.server.accept()
                    client.setblocking(False)
                    inputs.append(client)
            self.broadcast(message, readable[1:])

    def make_message(self):
        if self.data_handler.value:
            time_after_begin = self.data_handler.time_ms[-1]
            value = self.data_handler.value[-1]
            message = bytes([0xaa, 0x55, 0x00, CommandCodes.LATEST_FRAME,
                             *QUERY_SUCCESS_LENGTH.to_bytes(2, 'big'),
                             0x01])\
                      + bytes(time_after_begin) + bytes(value)
            message += bytes([crc(message)])
            print(f"数据时间：{time_after_begin + self.data_handler.begin_time}")
            print(f"发送时间：{time.time()}")
        else:
            message = bytes([0xaa, 0x55, 0x00, CommandCodes.LATEST_FRAME,
                             *QUERY_FAIL_LENGTH.to_bytes(2, 'big'),
                             0x00])
            message += bytes([crc(message)])
        return message

    def initiate(self):
        if not self.data_handler.driver.connected:
            try:
                flag = self.data_handler.driver.connect(None)
                if flag:
                    atexit.register(self.data_handler.driver.disconnect)
            except Exception as e:
                warnings.warn(str(e))
        self.data_thread.start()

    def terminate(self):
        self.activate = False
        self.server.close()

    def trigger_forever(self):
        while True:
            self.data_handler.trigger()


if __name__ == '__main__':
    server = SocketServer()
    server.start()

