call activate sensor_driver_gui
pyinstaller -D interface_can_seat_sensor.py -i resources\logo.ico --add-data ".\config_files\config.json;.\config_files" --add-data ".\config_files\config_array_24_16.json;.\config_files" --add-data ".\config_files\config_array_16.json;.\config_files" --add-data ".\resources\logo.ico;.\resources" --add-data ".\resources\logo.png;.\resources"
pause