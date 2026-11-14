"""
PC Guardian — Config Encryption
Fernet symmetric encryption for config storage
"""

import os
import sys
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT = b"pcguardian_salt_v1_secure"


def _get_config_dir() -> str:
    """
    Returns a stable, writable config directory whether running
    from source or as a PyInstaller onefile bundle.
    """
    if getattr(sys, "frozen", False):
        # Exe — write beside the exe in a config/ subfolder
        base = os.path.dirname(sys.executable)
    else:
        # Source — write in config/ alongside this file
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "config")
    os.makedirs(path, exist_ok=True)
    return path


def _get_paths():
    d = _get_config_dir()
    return (
        os.path.join(d, "config.enc"),
        os.path.join(d, ".key"),
    )


def _get_or_create_key():
    _, key_path = _get_paths()
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    machine_id = _get_machine_id()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
    with open(key_path, "wb") as f:
        f.write(key)
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(key_path, 2)
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
    config_path, _ = _get_paths()
    key = _get_or_create_key()
    f = Fernet(key)
    encrypted = f.encrypt(json.dumps(data).encode())
    with open(config_path, "wb") as fp:
        fp.write(encrypted)


def decrypt_config() -> dict:
    config_path, _ = _get_paths()
    key = _get_or_create_key()
    f = Fernet(key)
    with open(config_path, "rb") as fp:
        encrypted = fp.read()
    return json.loads(f.decrypt(encrypted).decode())
