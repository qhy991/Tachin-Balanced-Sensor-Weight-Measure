from server.socket_client import SocketClient
client = SocketClient()
client.connect(10084)
while True:
    client.query()
