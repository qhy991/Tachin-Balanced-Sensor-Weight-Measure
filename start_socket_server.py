from server.socket_server import SocketServer
from backends.usb_driver import ZWUsbSensorDriver
import argparse
import time

parser = argparse.ArgumentParser(description='启动socket服务器')
parser.add_argument('--source', type=int, default=0, help='数据源（USB设备的REV号）')
parser.add_argument('--port_start', type=int, default=10080, help='起始端口号')
parser.add_argument('--max_client_count', type=int, default=16, help='最大客户端数目（将占用从起始端口号开始相应数量的端口）')
parser.add_argument('--client_timeout', type=int, default=10, help='客户端自动断线时间（秒）')

args = parser.parse_args()

sensor_class = ZWUsbSensorDriver
server = SocketServer(sensor_class, args.source, args.port_start, args.max_client_count, args.client_timeout)

while True:
    time.sleep(1)

