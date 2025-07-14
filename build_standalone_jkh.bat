call activate sensor_driver_gui
pyinstaller -D interface_hand_shape_jkh.py -i interfaces\resources\logo.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
mkdir dist\interface_hand_shape_jkh\_internal\backends
mkdir dist\interface_hand_shape_jkh\_internal\interfaces
mkdir dist\interface_hand_shape_jkh\_internal\interfaces\resources
mkdir dist\interface_hand_shape_jkh\_internal\interfaces\hand_shape\resources
mkdir dist\interface_hand_shape_jkh\_internal\interfaces\config_mapping
mkdir dist\interface_hand_shape_jkh\_internal\calibrate_files
copy config.json dist\interface_hand_shape_jkh\_internal\config.json
copy interfaces\config_mapping\config_mapping_jkh.json dist\interface_hand_shape_jkh\_internal\interfaces\config_mapping\config_mapping_jkh.json
copy backends\config_array_64.json dist\interface_hand_shape_jkh\_internal\backends\config_array_64.json
copy interfaces\hand_shape\resources\hand_jkh.png dist\interface_hand_shape_jkh\_internal\interfaces\hand_shape\resources\hand_jkh.png
copy interfaces\resources\logo.ico dist\interface_hand_shape_jkh\_internal\interfaces\resources\logo.ico
copy interfaces\resources\logo.png dist\interface_hand_shape_jkh\_internal\interfaces\resources\logo.png
copy calibrate_files\calibration_jkh.clb dist\interface_hand_shape_jkh\_internal\calibrate_files\calibration_jkh.clb
pause