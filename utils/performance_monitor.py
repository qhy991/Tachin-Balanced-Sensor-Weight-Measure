import time


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
