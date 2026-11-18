"""
PC Guardian — Encryption
Salsa20 + RSA-2048 + PBKDF2
Password DECDRV used everywhere.
"""

import os
import json
import struct
import hashlib
import logging

logger = logging.getLogger("crypto")

_DIR        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DIR, "config.enc")
RSA_PRIV    = os.path.join(_DIR, ".rsa_priv.pem")
RSA_PUB     = os.path.join(_DIR, ".rsa_pub.pem")

MASTER_PASSWORD = "DECDRV"
SALT            = b"PCGuardian_v2_Salsa20_RSA2048_DECDRV"


def _derive_key(password: str = MASTER_PASSWORD) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=600000,
    )
    return kdf.derive(password.encode())


def _get_machine_id() -> bytes:
    try:
        import subprocess
        raw = subprocess.check_output(
            "wmic csproduct get UUID", shell=True
        ).decode(errors="ignore").split("\n")[1].strip()
        return raw.encode()
    except Exception:
        return b"PCGuardian_fallback_DECDRV"


def _get_or_create_rsa():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    if os.path.exists(RSA_PRIV) and os.path.exists(RSA_PUB):
        with open(RSA_PRIV, "rb") as f:
            priv = serialization.load_pem_private_key(f.read(), password=None)
        with open(RSA_PUB, "rb") as f:
            pub = serialization.load_pem_public_key(f.read())
        return priv, pub

    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub  = priv.public_key()

    with open(RSA_PRIV, "wb") as f:
        f.write(priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ))
    with open(RSA_PUB, "wb") as f:
        f.write(pub.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ))

    # Hide key files
    try:
        import ctypes
        for p in [RSA_PRIV, RSA_PUB]:
            ctypes.windll.kernel32.SetFileAttributesW(p, 0x02)
    except Exception:
        pass

    return priv, pub


def _salsa20_encrypt(data: bytes, password: str = MASTER_PASSWORD) -> bytes:
    key   = _derive_key(password)
    nonce = os.urandom(8)
    try:
        from Crypto.Cipher import Salsa20
        c = Salsa20.new(key=key, nonce=nonce)
        return nonce + c.encrypt(data)
    except ImportError:
        from cryptography.hazmat.primitives.ciphers.algorithms import ChaCha20
        from cryptography.hazmat.primitives.ciphers import Cipher
        c = Cipher(ChaCha20(key, b'\x00'*4 + nonce), mode=None)
        return nonce + c.encryptor().update(data)


def _salsa20_decrypt(data: bytes, password: str = MASTER_PASSWORD) -> bytes:
    key        = _derive_key(password)
    nonce      = data[:8]
    ciphertext = data[8:]
    try:
        from Crypto.Cipher import Salsa20
        c = Salsa20.new(key=key, nonce=nonce)
        return c.decrypt(ciphertext)
    except ImportError:
        from cryptography.hazmat.primitives.ciphers.algorithms import ChaCha20
        from cryptography.hazmat.primitives.ciphers import Cipher
        c = Cipher(ChaCha20(key, b'\x00'*4 + nonce), mode=None)
        return c.decryptor().update(ciphertext)


def _rsa_encrypt_key(key: bytes, pub) -> bytes:
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes
    return pub.encrypt(
        key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def _rsa_decrypt_key(enc_key: bytes, priv) -> bytes:
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes
    return priv.decrypt(
        enc_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def encrypt_config(data: dict):
    """Salsa20 + RSA-2048 config encryption. Password: DECDRV everywhere."""
    os.makedirs(_DIR, exist_ok=True)
    priv, pub = _get_or_create_rsa()

    # Derive Salsa20 key from DECDRV password + machine ID
    combined  = MASTER_PASSWORD.encode() + _get_machine_id()
    salsa_key = hashlib.pbkdf2_hmac("sha256", combined, SALT, 600000, 32)

    plaintext = json.dumps(data).encode()
    encrypted = _salsa20_encrypt(plaintext, MASTER_PASSWORD)

    # Encrypt the Salsa20 key with RSA-2048
    enc_key   = _rsa_encrypt_key(salsa_key, pub)
    key_len   = struct.pack(">I", len(enc_key))
    payload   = key_len + enc_key + encrypted

    with open(CONFIG_PATH, "wb") as f:
        f.write(payload)

    logger.info("Config encrypted with Salsa20+RSA-2048.")


def decrypt_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        payload = f.read()

    key_len   = struct.unpack(">I", payload[:4])[0]
    enc_key   = payload[4: 4 + key_len]
    encrypted = payload[4 + key_len:]

    priv, _   = _get_or_create_rsa()
    _          = _rsa_decrypt_key(enc_key, priv)  # verify RSA
    plaintext  = _salsa20_decrypt(encrypted, MASTER_PASSWORD)

    return json.loads(plaintext.decode())
