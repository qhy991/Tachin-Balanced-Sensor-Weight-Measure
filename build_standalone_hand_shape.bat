call activate sensor_driver_gui
pyinstaller -D -w interface_hand_shape.py -i ordinary\layout\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_hand_shape\_internal\config.json
copy config_array.json dist\interface_hand_shape\_internal\config_array.json
mkdir dist\interface_hand_shape\_internal\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_hand_shape\_internal\ordinary\layout\tujian.ico
mkdir dist\interface_hand_shape\_internal\hand_shape
mkdir dist\interface_hand_shape\_internal\hand_shape\resources
copy hand_shape\config_mapping_hand.json dist\interface_hand_shape\_internal\hand_shape\config_mapping_hand.json
copy hand_shape\resources\hand.png dist\interface_hand_shape\_internal\hand_shape\resources\hand.png
copy hand_shape\resources\tujian.ico dist\interface_hand_shape\_internal\hand_shape\resources\tujian.ico
pause