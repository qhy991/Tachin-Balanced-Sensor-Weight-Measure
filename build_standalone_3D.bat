call activate sensor_driver_gui
pyinstaller -D -w interface_large_sensor_3D.py -i interfaces\resources\logo.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
mkdir dist\interface_large_sensor_3D\_internal\backends
mkdir dist\interface_large_sensor_3D\_internal\interfaces
mkdir dist\interface_large_sensor_3D\_internal\interfaces\resources
copy config.json dist\interface_large_sensor_3D\_internal\config.json
copy backends\config_array_64.json dist\interface_large_sensor_3D\_internal\backends\config_array_64.json
copy interfaces\resources\logo.ico dist\interface_large_sensor_3D\_internal\interfaces\resources\logo.ico
copy interfaces\resources\logo.png dist\interface_large_sensor_3D\_internal\interfaces\resources\logo.png
pause