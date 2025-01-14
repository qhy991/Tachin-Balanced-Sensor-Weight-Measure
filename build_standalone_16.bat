call activate sensor_driver_gui
pyinstaller -D -w interface_16_sensor.py -i ordinary\layout\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_16_sensor\_internal\config.json
copy config_files\config_array_16.json dist\interface_16_sensor\_internal\config_array.json
mkdir dist\interface_16_sensor\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_16_sensor\\ordinary\layout\tujian.ico
pause