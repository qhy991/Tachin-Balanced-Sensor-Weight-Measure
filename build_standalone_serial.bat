call activate sensor_driver_gui
pyinstaller -D -w interface_serial.py -i ordinary\layout\tujian.ico
copy config.json dist\interface_serial\_internal\config.json
copy config_array.json dist\interface_serial\_internal\config_array.json
mkdir dist\interface_serial\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_serial\\ordinary\layout\tujian.ico
pause