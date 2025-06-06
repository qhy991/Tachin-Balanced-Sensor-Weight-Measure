# algorithm_class 是 sensor_calibrate.py 中 Algorithm 的子类
eps = 1e-12

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import os
import base64


class SecureEncryption:
    def __init__(self):
        # 加密的密钥（加密后存储）
        self.encrypted_key = b'ENCRYPTED_KEY_HERE'  # 替换为实际加密后的密钥
        self.salt = b'SALT_VALUE_HERE'  # 替换为实际盐值
        self.backend = default_backend()

    def _decrypt_key(self, passphrase: str) -> bytes:
        """解密存储的密钥并确保长度符合 AES 要求"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 确保生成的密钥长度为 32 字节
            salt=self.salt,
            iterations=100000,
            backend=self.backend
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def encrypt(self, plaintext: str, passphrase: str) -> str:
        """加密数据"""
        key = self._decrypt_key(passphrase)
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=self.backend)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
        return base64.b64encode(iv + ciphertext).decode()

    def decrypt(self, encrypted_data: str, passphrase: str) -> str:
        """解密数据"""
        key = self._decrypt_key(passphrase)
        encrypted_data = base64.b64decode(encrypted_data)
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=self.backend)
        decryptor = cipher.decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode()


class CalibrateAdaptor:

    def __init__(self, sensor_class, algorithm_class, *args, **kwargs):
        sensor_shape = sensor_class.SENSOR_SHAPE
        self.algorithm_class = algorithm_class
        self.algorithm = algorithm_class(sensor_class, None, *args, **kwargs)
        self.__sensor_shape = sensor_shape

    def range(self):
        return self.algorithm.get_range()

    def load(self, path, forced_to_use_clb):
        is_encrypted = None
        if path.endswith('.clb'):
            is_encrypted = True
        elif path.endswith('.csv'):
            is_encrypted = False
        else:
            raise ValueError('Unsupported file format. Only .clb and .csv are supported.')
        if is_encrypted or forced_to_use_clb:
            content = ''.join([_.decode() for _ in open(path, 'rb').readlines()])
            se = SecureEncryption()
            content = se.decrypt(content, '-')
        else:
            content = ''.join(open(path, 'rt').readlines())
        assert self.algorithm.load(content)

    def transform_frame(self, voltage_frame):
        # 将一帧从原始数据变为标定结果
        # 原始数据为量化电压
        force_frame = self.algorithm.transform_streaming(voltage_frame)
        # force_frame = average_2x2_blocks(force_frame)
        return force_frame

    def __bool__(self):
        return self.algorithm_class.IS_NOT_IDLE


if __name__ == '__main__':

    # transform '.csv' to '.clb'
    folder = os.path.join(os.path.dirname(__file__), '../calibrate_files')
    for file in os.listdir(folder):
        if file.endswith('.csv'):
            path = os.path.join(folder, file)
            se = SecureEncryption()
            with open(path, 'rt') as f:
                content = ''.join(f.readlines())
            encrypted_content = se.encrypt(content, '-')
            with open(path.replace('.csv', '.clb'), 'wb') as f:
                f.write(encrypted_content.encode())
            print(f"Encrypted {file} to {file.replace('.csv', '.clb')}")


