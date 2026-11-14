"""
PC Guardian — Config Encryption
Fernet symmetric encryption for config storage
"""

import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.enc")
KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".key")
SALT = b"pcguardian_salt_v1_secure"


def _get_or_create_key():
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            return f.read()
    # Generate machine-specific key
    machine_id = _get_machine_id()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
    with open(KEY_PATH, "wb") as f:
        f.write(key)
    # Hide the key file
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(KEY_PATH, 2)  # FILE_ATTRIBUTE_HIDDEN
    except Exception:
        pass
    return key


def _get_machine_id():
    try:
        import subprocess
        result = subprocess.check_output(
            "wmic csproduct get UUID", shell=True
        ).decode().split("\n")[1].strip()
        return result
    except Exception:
        return "pcguardian_fallback_machine_id_2024"


def encrypt_config(data: dict):
    key = _get_or_create_key()
    f = Fernet(key)
    plaintext = json.dumps(data).encode()
    encrypted = f.encrypt(plaintext)
    with open(CONFIG_PATH, "wb") as fp:
        fp.write(encrypted)


def decrypt_config() -> dict:
    key = _get_or_create_key()
    f = Fernet(key)
    with open(CONFIG_PATH, "rb") as fp:
        encrypted = fp.read()
    plaintext = f.decrypt(encrypted)
    return json.loads(plaintext.decode())
