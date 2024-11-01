call activate sensor_driver_gui
pyinstaller -D interface_large_sensor.py -i ordinary\layout\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_large_sensor\_internal\config.json
copy config_mapping.json dist\interface_large_sensor\_internal\config_mapping.json
copy config_array.json dist\interface_large_sensor\_internal\config_array.json
mkdir dist\interface_large_sensor\_internal\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_large_sensor\_internal\ordinary\layout\tujian.ico
pause