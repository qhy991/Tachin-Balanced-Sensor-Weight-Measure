import time
import os
import atexit


class Ticker:

    def __init__(self):
        self.last_time = time.time()

    def tic(self):
        time_now = time.time()
        self.last_time = time_now

    def toc(self, hint=''):
        time_now = time.time()
        time_delta = time_now - self.last_time
        print(f'{hint}-时间已过{round(time_delta * 1e3)}ms')
        self.last_time = time_now
        return time_delta

class Logger:

    def __init__(self):
        os.makedirs(os.path.dirname(__file__), exist_ok=True)
        self.file = open(os.path.join(os.path.dirname(__file__), 'log.txt'), 'wt', encoding='utf-8')
        self.file.write(f'{"-" * 20}\n')
        # 写上时间
        self.file.write(f'日志开始时间: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}\n')
        self.file.flush()
        atexit.register(self.file.close)

    def __call__(self, content):
        content = str(content)
        # self.file.write(f'{content}\n')
        # self.file.flush()
        print(content)

logger = Logger()
