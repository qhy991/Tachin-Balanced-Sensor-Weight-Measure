call activate sensor_driver_gui
pyinstaller -D -w interface_data_viewer.py -i ordinary\layout\tujian.ico"
copy config.json dist\interface_data_viewer\_internal\config.json
mkdir dist\interface_data_viewer\ordinary\layout
copy ordinary\layout\tujian.ico dist\interface_data_viewer\ordinary\layout\tujian.ico
pause