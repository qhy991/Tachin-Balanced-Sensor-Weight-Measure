import socket
import time
import threading

# 创建一个本地socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('localhost', 0))  # 绑定到一个随机的可用端口
s.listen(1)


# 在另一个线程中接受连接
def accept_connection():
    conn, addr = s.accept()
    data = conn.recv(1024)  # 接收数据
    print(f"Received: {data}")
    conn.close()


threading.Thread(target=accept_connection).start()

# 连接到本地socket
s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s2.connect(s.getsockname())

# 发送一个数据包，并测量所需的时间
start_time = time.time()
s2.send(b'hello')
end_time = time.time()

print(f"Latency: {(end_time - start_time) * 1000} ms")

s2.close()
s.close()
