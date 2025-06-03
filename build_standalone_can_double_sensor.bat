call activate sensor_driver_gui
pyinstaller -D -w interface_can_double_sensor.py -i interfaces\resources\logo.ico
mkdir dist\interface_can_double_sensor\_internal\backends
mkdir dist\interface_can_double_sensor\_internal\interfaces
mkdir dist\interface_can_double_sensor\_internal\interfaces\resources
mkdir dist\interface_can_double_sensor\_internal\interfaces\config_mapping
copy config.json dist\interface_can_double_sensor\_internal\config.json
copy interfaces\config_mapping\config_mapping_jk.json dist\interface_can_double_sensor\_internal\interfaces\config_mapping\config_mapping_jk.json
copy backends\config_array_16.json dist\interface_can_double_sensor\_internal\backends\config_array_16.json
copy backends\ControlCAN.dll dist\interface_can_double_sensor\_internal\backends\ControlCAN.dll
copy backends\config_can.json dist\interface_can_double_sensor\_internal\backends\config_can.json
copy interfaces\resources\logo.ico dist\interface_can_double_sensor\_internal\interfaces\resources\logo.ico
copy interfaces\resources\logo.png dist\interface_can_double_sensor\_internal\interfaces\resources\logo.png
pause