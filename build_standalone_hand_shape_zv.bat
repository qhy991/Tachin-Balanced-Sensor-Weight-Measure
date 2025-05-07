call activate sensor_driver_gui
pyinstaller -w -D interface_hand_shape_zv.py -i interfaces\hand_shape\resources\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_hand_shape_zv\_internal\config.json
mkdir dist\interface_hand_shape_zv\_internal\backends
copy backends\config_array_zv.json dist\interface_hand_shape_zv\_internal\backends\config_array_zv.json
mkdir dist\interface_hand_shape_zv\_internal\interfaces
mkdir dist\interface_hand_shape_zv\_internal\interfaces\hand_shape
mkdir dist\interface_hand_shape_zv\_internal\interfaces\hand_shape\resources
copy interfaces\hand_shape\config_mapping_hand_zv.json dist\interface_hand_shape_zv\_internal\interfaces\hand_shape\config_mapping_hand_zv.json
copy interfaces\hand_shape\resources\hand_zv.png dist\interface_hand_shape_zv\_internal\interfaces\hand_shape\resources\hand_zv.png
copy interfaces\hand_shape\resources\logo.png dist\interface_hand_shape_zv\_internal\interfaces\hand_shape\resources\logo.png
pause