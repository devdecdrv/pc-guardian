"""
PC Guardian — Startup Registration (FIXED)
Adds to Windows registry + Task Scheduler so it runs at every boot
even before user login (SYSTEM level)
"""

import os
import sys
import subprocess
import logging

logger = logging.getLogger("startup")

APP_NAME     = "PCGuardian"
REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"


def get_exe_path() -> str:
    """Return path to the exe or python launcher."""
    dist_exe = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "dist", "pc-guardian.exe"
    )
    if os.path.exists(dist_exe):
        return dist_exe
    # Running as script
    return f'"{sys.executable}" "{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")}"'


def install_registry():
    """HKCU Run — starts when user logs in."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_exe_path())
        winreg.CloseKey(key)
        logger.info("Registry startup entry added.")
        return True
    except Exception as e:
        logger.error(f"Registry install failed: {e}")
        return False


def install_task_scheduler():
    """
    Task Scheduler — SYSTEM level, runs at boot before login.
    Most reliable method on Windows.
    """
    exe = get_exe_path()
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
      <Command>{exe.strip('"').split('" "')[0]}</Command>
      <Arguments>{' '.join(exe.strip('"').split('" "')[1:])}</Arguments>
    </Exec>
  </Actions>
</Task>"""

    xml_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "pcguardian_task.xml")
    try:
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml)
        result = subprocess.run(
            f'schtasks /Create /TN "{APP_NAME}" /XML "{xml_path}" /F',
            shell=True, capture_output=True, text=True
        )
        os.remove(xml_path)
        if result.returncode == 0:
            logger.info("Task Scheduler entry created.")
            return True
        else:
            logger.error(f"Task Scheduler failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Task Scheduler error: {e}")
        return False


def remove_startup():
    """Remove both registry and task scheduler entries."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except Exception:
        pass
    try:
        subprocess.run(
            f'schtasks /Delete /TN "{APP_NAME}" /F',
            shell=True, capture_output=True
        )
    except Exception:
        pass
    logger.info("Startup entries removed.")


def install_all():
    """Install both methods — belt and suspenders."""
    r = install_registry()
    t = install_task_scheduler()
    return r or t  # success if either worked
