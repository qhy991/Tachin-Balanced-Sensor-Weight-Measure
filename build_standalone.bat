call activate sensor_driver_gui
pyinstaller -D interface_large_sensor.py -i resources\logo.ico --add-data "C:\Windows\System32\libusb-1.0.dll;." --add-data ".\config_files\config.json;.\config_files" --add-data ".\config_files\config_array_64.json;.\config_files" --add-data ".\resources\logo.ico;.\resources" --add-data ".\resources\logo.png;.\resources"
pause