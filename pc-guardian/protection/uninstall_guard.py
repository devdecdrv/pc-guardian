"""
PC Guardian — Uninstall Guard
Blocks removal without correct password
Removes startup entries, service, and files only on correct auth
"""

import os
import sys
import shutil
import logging

logger = logging.getLogger("uninstall_guard")

INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE_NAME = "PCGuardianService"
REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_VALUE = "PCGuardian"


def attempt_uninstall(password: str, correct_password: str) -> tuple:
    """
    Returns (success: bool, message: str)
    """
    if password != correct_password:
        logger.warning("Uninstall attempted with wrong password.")
        return False, "Wrong password. PC Guardian remains installed."

    errors = []

    # Stop and remove Windows service
    try:
        import subprocess
        subprocess.run(f"sc stop {SERVICE_NAME}", shell=True, capture_output=True)
        subprocess.run(f"sc delete {SERVICE_NAME}", shell=True, capture_output=True)
        logger.info("Service removed.")
    except Exception as e:
        errors.append(f"Service: {e}")

    # Remove registry startup entry
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, REGISTRY_VALUE)
        winreg.CloseKey(key)
        logger.info("Registry entry removed.")
    except Exception as e:
        errors.append(f"Registry: {e}")

    # Remove config files
    try:
        config_enc = os.path.join(INSTALL_DIR, "config", "config.enc")
        key_file = os.path.join(INSTALL_DIR, "config", ".key")
        for f in [config_enc, key_file]:
            if os.path.exists(f):
                os.remove(f)
        logger.info("Config files removed.")
    except Exception as e:
        errors.append(f"Config: {e}")

    if errors:
        return True, f"Uninstalled with some errors: {'; '.join(errors)}"
    return True, "PC Guardian fully uninstalled."


def install_startup():
    """Add to Windows startup via registry."""
    try:
        import winreg
        exe_path = os.path.join(INSTALL_DIR, "dist", "pc-guardian.exe")
        if not os.path.exists(exe_path):
            # Fallback to python script
            exe_path = f'"{sys.executable}" "{os.path.join(INSTALL_DIR, "main.py")}"'
        else:
            exe_path = f'"{exe_path}"'

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, REGISTRY_VALUE, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        logger.info("Startup registry entry added.")
        return True
    except Exception as e:
        logger.error(f"Startup install failed: {e}")
        return False
