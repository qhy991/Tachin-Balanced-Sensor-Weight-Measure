import warnings
from collections import deque
import serial
import numpy as np
import threading
import time

baud_rate = 115200

class Decoder:

    def __init__(self):
        self.max_len = 4096
        self.package_delimiter = '\r\n\r\n'
        self.row_delimiter = '\r\n'
        self.column_delimiter = ','
        self.buffer = deque(maxlen=self.max_len)

    def decode(self, data):
        self.buffer.extend(data)
        # 格式为：'\r\n'开头，'\r\n\r\n'结尾
        split = ''.join(self.buffer).split(self.package_delimiter)
        try:
            if split.__len__() >= 3:
                package = split[1]
                self.buffer = deque(self.package_delimiter + split[2], maxlen=self.max_len)
                # 解析data
                result = []
                rows = package.split(self.row_delimiter)
                for row in rows:
                    cols = row.split(self.column_delimiter)
                    v_cols = [float(col.strip()) for col in cols]
                    result.append(v_cols)
                result = np.array(result)
                assert result.shape == (5, 16)
                return result
            else:
                return None
        except Exception as e:
            warnings.warn(str(e))
            return None


class FLDriver:
    def __init__(self, port):
        self.port = port
        self.serial = serial.Serial(port, baudrate=baud_rate, timeout=1)
        self.decoder = Decoder()
        self.results = deque(maxlen=64)
        self.activated = False
        self.running = False
        self.last_time = None

    def start(self):
        if not self.running:
            self.activated = True
            threading.Thread(target=self.__read_forever, daemon=True).start()
            self.running = True
            return True
        else:
            print("Driver is already running.")
            return False

    def stop(self):
        self.activated = False
        while self.running:
            pass
        return True

    def get(self):
        if self.results:
            return self.results.popleft()
        else:
            return None

    def __read_forever(self):
        self.last_time = time.time()
        while self.activated:
            values = self.__read()
            if values is not None:
                self.results.append(values)
                current_time = time.time()
                if self.last_time is not None:
                    elapsed_time = current_time - self.last_time
                    print(f"Time since last read: {elapsed_time:.4f} seconds")
                    self.last_time = current_time
        self.running = False

    def __read(self):
        data = self.serial.read_all().decode('utf-8')
        if data:
            values = self.decoder.decode(data)
            return values
        else:
            return None

    def close(self):
        self.serial.close()


if __name__ == '__main__':
    driver = FLDriver('COM28')
    assert driver.start()
    try:
        while True:
            values = driver.get()
            if values is not None:
                print(values)
    except KeyboardInterrupt:
        driver.close()
        print("Driver closed.")



