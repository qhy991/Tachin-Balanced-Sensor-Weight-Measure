call activate sensor_driver_gui
pyinstaller -D interface_seat_shape.py -i ordinary\layout\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_seat_shape\_internal\config.json
copy config_multiple.json dist\interface_seat_shape\_internal\config_multiple.json
copy config_array.json dist\interface_seat_shape\_internal\config_array.json
mkdir dist\interface_seat_shape\_internal\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_seat_shape\_internal\ordinary\layout\tujian.ico
pause