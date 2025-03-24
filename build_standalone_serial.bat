call activate sensor_driver_gui
pyinstaller -D interface_serial_sensor.py -i interfaces\hand_shape\resources\tujian.ico
copy config.json dist\interface_serial_sensor\_internal\config.json
copy config_array.json dist\interface_serial_sensor\_internal\config_array.json
mkdir dist\interface_serial_sensor\interfaces\ordinary
mkdir dist\interface_serial_sensor\interfaces\ordinary\layout
copy interfaces\ordinary\layout\tujian.ico dist\interface_serial_sensor\interfaces\ordinary\layout\tujian.ico
mkdir dist\interface_serial_sensor\interfaces\
mkdir dist\interface_serial_sensor\interfaces\ordinary\resources
copy interfaces\ordinary\resources\logo.png dist\interface_large_sensor\interfaces\ordinary\resources\logo.png
mkdir dist\interface_serial_sensor\_internal\backends
copy backends\config_array_16.json dist\interface_serial_sensor\_internal\backends\config_array_16.json
pause