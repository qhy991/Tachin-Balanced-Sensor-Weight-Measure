call activate sensor_driver_gui
pyinstaller -D -w interface_hand_shape.py -i interfaces\hand_shape\resources\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_hand_shape\_internal\config.json
mkdir dist\interface_hand_shape\_internal\backends
copy backends\config_array_zw.json dist\interface_hand_shape\_internal\backends\config_array_zw.json
mkdir dist\interface_hand_shape\_internal\interfaces\hand_shape
mkdir dist\interface_hand_shape\_internal\interfaces\hand_shape\resources
copy interfaces\hand_shape\resources\tujian.ico dist\interface_hand_shape\_internal\interfaces\hand_shape\resources\tujian.ico
copy interfaces\hand_shape\config_mapping_hand.json dist\interface_hand_shape\_internal\interfaces\hand_shape\config_mapping_hand.json
copy interfaces\hand_shape\resources\hand.png dist\interface_hand_shape\_internal\interfaces\hand_shape\resources\hand.png
copy interfaces\hand_shape\resources\logo.png dist\interface_hand_shape\_internal\interfaces\hand_shape\resources\logo.png
pause