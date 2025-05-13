call activate sensor_driver_gui
pyinstaller -D interface_usb_double_sensor.py -i interfaces\resources\logo.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
mkdir dist\interface_usb_double_sensor\_internal\backends
mkdir dist\interface_usb_double_sensor\_internal\interfaces
mkdir dist\interface_usb_double_sensor\_internal\interfaces\resources
mkdir dist\interface_usb_double_sensor\_internal\interfaces\config_mapping
copy config.json dist\interface_usb_double_sensor\_internal\config.json
copy interfaces\config_mapping\config_mapping_jk.json dist\interface_usb_double_sensor\_internal\interfaces\config_mapping\config_mapping_jk.json
copy backends\config_array_64.json dist\interface_usb_double_sensor\_internal\backends\config_array_64.json
copy interfaces\resources\logo.ico dist\interface_usb_double_sensor\_internal\interfaces\resources\logo.ico
copy interfaces\resources\logo.png dist\interface_usb_double_sensor\_internal\interfaces\resources\logo.png
pause