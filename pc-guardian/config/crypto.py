"""
PC Guardian — Encryption
Fernet (AES-128-CBC) — reliable, works everywhere.
Salsa20+RSA was causing failures — this always works.
"""

import os
import json
import base64

CONFIG_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.enc")
KEY_PATH    = os.path.join(CONFIG_DIR, ".key")


def _get_key() -> bytes:
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            return f.read()

    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(KEY_PATH, "wb") as f:
        f.write(key)

    # Hide key file
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(KEY_PATH, 0x02)
    except Exception:
        pass

    return key


def encrypt_config(data: dict):
    from cryptography.fernet import Fernet
    os.makedirs(CONFIG_DIR, exist_ok=True)
    key = _get_key()
    f   = Fernet(key)
    enc = f.encrypt(json.dumps(data).encode())
    with open(CONFIG_PATH, "wb") as fp:
        fp.write(enc)


def decrypt_config() -> dict:
    from cryptography.fernet import Fernet
    key = _get_key()
    f   = Fernet(key)
    with open(CONFIG_PATH, "rb") as fp:
        enc = fp.read()
    return json.loads(f.decrypt(enc).decode())
