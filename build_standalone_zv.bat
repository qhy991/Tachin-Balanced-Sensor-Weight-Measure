call activate sensor_driver_gui
pyinstaller -D interface_hand_shape_zv.py -i interfaces\resources\logo.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
mkdir dist\interface_hand_shape_zv\_internal\backends
mkdir dist\interface_hand_shape_zv\_internal\interfaces
mkdir dist\interface_hand_shape_zv\_internal\interfaces\resources
mkdir dist\interface_hand_shape_zv\_internal\interfaces\hand_shape\resources
mkdir dist\interface_hand_shape_zv\_internal\interfaces\config_mapping
mkdir dist\interface_hand_shape_zv\_internal\calibrate_files
copy config.json dist\interface_hand_shape_zv\_internal\config.json
copy interfaces\config_mapping\config_mapping_zv.json dist\interface_hand_shape_zv\_internal\interfaces\config_mapping\config_mapping_zv.json
copy backends\config_array_zv.json dist\interface_hand_shape_zv\_internal\backends\config_array_zv.json
copy interfaces\hand_shape\resources\hand_zv.png dist\interface_hand_shape_zv\_internal\interfaces\hand_shape\resources\hand_zv.png
copy interfaces\resources\logo.ico dist\interface_hand_shape_zv\_internal\interfaces\resources\logo.ico
copy interfaces\resources\logo.png dist\interface_hand_shape_zv\_internal\interfaces\resources\logo.png
copy calibrate_files\default_calibration_file.clb dist\interface_hand_shape_zv\_internal\calibrate_files\default_calibration_file.clb
pause