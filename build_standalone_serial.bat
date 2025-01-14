call activate sensor_driver_gui
pyinstaller -D -w interface_serial_sensor.py -i ordinary\layout\tujian.ico
copy config.json dist\interface_serial_sensor\_internal\config.json
copy config_array.json dist\interface_serial_sensor\_internal\config_array.json
mkdir dist\interface_serial_sensor\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_serial_sensor\ordinary\layout\tujian.ico
pause