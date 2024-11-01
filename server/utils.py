import time
import crcmod.predefined
crc_ = crcmod.predefined.mkCrcFun('crc-8-maxim')


class CommandCodes:

    NULL = 0x00
    LATEST_FRAME = 0x01


def crc(message):
    # CRC校验
    # 对前三位求CRC
    return crc_(bytes(message))


def wait():
    time.sleep(0.001)
    pass
