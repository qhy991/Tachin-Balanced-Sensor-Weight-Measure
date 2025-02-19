call activate sensor_driver_gui
pyinstaller -w interface_large_sensor.py --onefile -i interfaces\layout\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_large_sensor\_internal\config.json
copy config_array.json dist\interface_large_sensor\_internal\config_array.json
mkdir dist\interface_large_sensor\interfaces\layout
copy interfaces\layout\tujian.ico dist\interface_large_sensor\\interfaces\layout\tujian.ico
mkdir dist\interface_large_sensor\interfaces\resources
copy interfaces\resources\logo.png dist\interface_large_sensor\interfaces\resources\logo.png
pause