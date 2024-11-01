import json
import os

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './config.json')

config = json.load(
    open(config_path, 'rt'))

# 以下是可选配置

try:
    config_mapping = json.load(
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand/config_mapping_hand.json'), 'rt'))
except FileNotFoundError:
    config_mapping = None

try:
    config_mapping_seat = json.load(
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), './config_mapping_seat.json'), 'rt'))
except FileNotFoundError:
    config_mapping_seat = None

try:
    config_array = json.load(
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), './config_array.json'), 'rt'))
except FileNotFoundError:
    config_array = None

try:
    config_multiple = json.load(
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), './config_multiple.json'), 'rt', encoding='utf-8'))
except FileNotFoundError:
    config_multiple = None

try:
    config_void_list = json.load(
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), './config_void_list.json'), 'rt'))

except FileNotFoundError:
    config_void_list = None


def save_config():
    json.dump(config, open(config_path, 'wt'))
