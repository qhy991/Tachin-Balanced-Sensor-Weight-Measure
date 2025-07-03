call activate sensor_driver_gui
pyinstaller -D interface_usb_zc.py -i interfaces\resources\logo.ico --add-data "C:\Windows\System32\libusb-1.0.dll;."
mkdir dist\interface_usb_zc\_internal\backends
mkdir dist\interface_usb_zc\_internal\interfaces
mkdir dist\interface_usb_zc\_internal\interfaces\resources
mkdir dist\interface_usb_zc\_internal\interfaces\hand_shape\resources
mkdir dist\interface_usb_zc\_internal\interfaces\config_mapping
mkdir dist\interface_usb_zc\_internal\calibrate_files
copy config.json dist\interface_usb_zc\_internal\config.json
copy interfaces\config_mapping\config_mapping_zc.json dist\interface_usb_zc\_internal\interfaces\config_mapping\config_mapping_zc.json
copy backends\config_array_zc.json dist\interface_usb_zc\_internal\backends\config_array_zc.json
copy interfaces\resources\logo.ico dist\interface_usb_zc\_internal\interfaces\resources\logo.ico
copy interfaces\resources\logo.png dist\interface_usb_zc\_internal\interfaces\resources\logo.png
copy calibrate_files\calibration_log.clb dist\interface_usb_zc\_internal\calibrate_files\calibration_log.clb
pause