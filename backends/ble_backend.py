
import asyncio
from bleak import BleakScanner, BleakClient
from backends.decoding import Decoder
import json
import os

config_array = json.load(open(os.path.dirname(__file__) + '/config_array_32.json'))
decoder = Decoder(config_array)

# 需搜索的设备名称，可按需修改
TARGET_DEVICE_NAME = "ai-thinker"
# 要读取的服务和特征的 UUID，可按需修改
SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
# CHARACTERISTIC_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"
CHARACTERISTIC_UUID = "49535343-1e4d-4bd9-ba61-23c647249616"


async def scan_for_device():
    """扫描附近的 BLE 设备并返回目标设备"""
    print("正在扫描附近的 BLE 设备...")
    devices = await BleakScanner.discover(timeout=20)
    for device in devices:
        print(device.name)
        if device.name == TARGET_DEVICE_NAME:
            return device
    print(f"未找到名为 {TARGET_DEVICE_NAME} 的设备。")
    return None


async def enumerate_characteristics(client):
    try:
        # 获取所有服务
        services = await client.get_services()
        for service in services:
            print(f"服务 UUID: {service.uuid}")
            for characteristic in service.characteristics:
                properties = ','.join(characteristic.properties)
                print(f"  特征 UUID: {characteristic.uuid}, 句柄: {characteristic.handle}, 属性: {properties}")
    except Exception as e:
        print(f"枚举特征时出错: {e}")


from utils.performance_monitor import Ticker
ticker = Ticker()
ticker.tic()
ticker_frame = Ticker()
ticker_frame.tic()

def notification_handler(sender, data):
    """处理接收到的通知数据"""
    # print(f"Received data from {sender}: {data.hex()}")
    data = [int(_) for _ in data]
    # ticker.toc(f"长度为{data.__len__()}的数据耗时：")
    decoder(data)
    frame, t = decoder.get()
    if frame is not None:
        print(f"解析后的数据: {frame}")
        ticker_frame.toc(f"完成一帧数据耗时：")
    # ascii_data = bytes.fromhex(data.hex()).decode('ascii', errors='ignore')
    # print(f"解析后的数据: {ascii_data}")

async def read_ble_data(device):
    """连接到设备并使用通知方式获取数据"""
    if device is None:
        return

    async with BleakClient(device.address) as client:
        if not client.is_connected:
            print("无法连接到设备。")
            return

        print("已连接到设备。")
        await asyncio.sleep(1)  # 增加延迟

        try:
            # 启用通知
            await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
            print("已启用通知，等待数据...")

            # 保持程序运行一段时间以接收通知
            await asyncio.sleep(30)

            # 停止通知
            await client.stop_notify(CHARACTERISTIC_UUID)

        except Exception as e:
            print(f"读取数据时出错: {e}")


async def main():
    target_device = await scan_for_device()
    if target_device:
        async with BleakClient(target_device.address) as client:
            if client.is_connected:
                await enumerate_characteristics(client)

        await read_ble_data(target_device)


if __name__ == "__main__":
    asyncio.run(main())
