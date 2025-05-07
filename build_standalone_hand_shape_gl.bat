call activate sensor_driver_gui
pyinstaller -w -D interface_hand_shape_gl.py -i interfaces\hand_shape\resources\tujian.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
copy config.json dist\interface_hand_shape_gl\_internal\config.json
mkdir dist\interface_hand_shape_gl\_internal\backends
copy backends\config_array_gl.json dist\interface_hand_shape_gl\_internal\backends\config_array_gl.json
mkdir dist\interface_hand_shape_gl\_internal\interfaces
mkdir dist\interface_hand_shape_gl\_internal\interfaces\hand_shape
mkdir dist\interface_hand_shape_gl\_internal\interfaces\hand_shape\resources
copy interfaces\hand_shape\config_mapping_hand_gl.json dist\interface_hand_shape_gl\_internal\interfaces\hand_shape\config_mapping_hand_gl.json
copy interfaces\hand_shape\resources\hand_gl.png dist\interface_hand_shape_gl\_internal\interfaces\hand_shape\resources\hand_gl.png
copy interfaces\hand_shape\resources\logo.png dist\interface_hand_shape_gl\_internal\interfaces\hand_shape\resources\logo.png
pause