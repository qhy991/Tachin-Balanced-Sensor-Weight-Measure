from server.socket_server import SocketServer
import time

server = SocketServer()
while True:
    time.sleep(60.)
