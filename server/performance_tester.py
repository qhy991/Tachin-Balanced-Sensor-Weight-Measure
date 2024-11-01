import time
import threading

from server.socket_server import SocketServer
from server.socket_client import SocketClient


def server_performance_test(client_count):
    SocketServer()
    threads = []
    clients = {}

    def query_forever(i_client):
        client = clients[i_client]
        client.connect(i_client)
        while True:
            client.query()

    for i_client in range(client_count):
        client = SocketClient()
        clients.update({i_client: client})
        threads.append(threading.Thread(target=query_forever, args=(i_client, ), daemon=True))

    for th in threads:
        th.start()

    while True:
        time.sleep(60.)


if __name__ == '__main__':
    server_performance_test(10084)
