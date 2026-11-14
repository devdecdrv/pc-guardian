"""
PC Guardian — Windows Service
Runs guardian as a SYSTEM-level Windows service
"""

import sys
import os
import time
import logging

logger = logging.getLogger("service")

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

SERVICE_NAME = "PCGuardianService"
SERVICE_DISPLAY = "PC Guardian Parental Control"
SERVICE_DESC = "PC Guardian — Parental monitoring and lock service."


if HAS_WIN32:
    class PCGuardianService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY
        _svc_description_ = SERVICE_DESC

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self._running = True

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.hWaitStop)
            self._running = False

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )
            self._main()

        def _main(self):
            # Import here to avoid circular at module load
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from main import start_guardian
            import threading
            t = threading.Thread(target=start_guardian, daemon=True)
            t.start()
            while self._running:
                time.sleep(1)


def install_service():
    if not HAS_WIN32:
        print("pywin32 not installed. Cannot install service.")
        return
    win32serviceutil.InstallService(
        PCGuardianService._svc_reg_class_,
        SERVICE_NAME,
        SERVICE_DISPLAY,
        startType=win32service.SERVICE_AUTO_START,
        description=SERVICE_DESC,
    )
    win32serviceutil.StartService(SERVICE_NAME)
    print(f"Service '{SERVICE_NAME}' installed and started.")


def remove_service():
    if not HAS_WIN32:
        print("pywin32 not installed.")
        return
    try:
        win32serviceutil.StopService(SERVICE_NAME)
    except Exception:
        pass
    win32serviceutil.RemoveService(SERVICE_NAME)
    print(f"Service '{SERVICE_NAME}' removed.")


if __name__ == "__main__":
    if HAS_WIN32:
        win32serviceutil.HandleCommandLine(PCGuardianService)
