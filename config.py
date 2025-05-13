import json
import os

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './config.json')

config = json.load(
    open(config_path, 'rt'))

def get_config_mapping(suffix):

    try:
        config_mapping = json.load(
            open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f'interfaces/config_mapping/config_mapping_{suffix}.json'), 'rt',
                 encoding='utf-8'),
        )
    except FileNotFoundError:
        config_mapping = None

    return config_mapping

def save_config():
    try:
        json.dump(config, open(config_path, 'wt'))
    except PermissionError:
        print('无法保存配置文件')
        pass
    except Exception:
        print('未知错误')
        pass

