call activate sensor_driver_gui
pyinstaller -D -w interface_fixed.py -i ordinary\layout\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_fixed\_internal\config.json
copy config_mapping.json dist\interface_fixed\_internal\config_mapping.json
copy config_array.json dist\interface_fixed\_internal\config_array.json
mkdir dist\interface_fixed\ordinary
mkdir dist\interface_fixed\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_fixed\ordinary\layout\tujian.ico
mkdir dist\interface_fixed\ordinary\resources
copy ordinary\resources\logo.png dist\interface_fixed\ordinary\resources\logo.png
pause