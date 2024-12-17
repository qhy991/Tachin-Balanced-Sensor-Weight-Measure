call activate sensor_driver_gui
pyinstaller -D -w interface_large_sensor.py -i ordinary\layout\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_large_sensor\_internal\config.json
copy config_array.json dist\interface_large_sensor\_internal\config_array.json
mkdir dist\interface_large_sensor\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_large_sensor\\ordinary\layout\tujian.ico
pause