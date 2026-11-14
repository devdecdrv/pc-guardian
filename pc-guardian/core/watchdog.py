"""
PC Guardian — Watchdog
Monitors and restarts the main service if killed
"""

import os
import sys
import time
import subprocess
import logging
import psutil

logger = logging.getLogger("watchdog")

MAIN_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
CHECK_INTERVAL = 5  # seconds


class Watchdog:
    def __init__(self):
        self._running = True
        self._main_pid = os.getpid()

    def start(self):
        logger.info(f"Watchdog active. Watching PID {self._main_pid}")
        while self._running:
            time.sleep(CHECK_INTERVAL)
            if not self._is_running():
                logger.warning("Main process died. Restarting...")
                self._restart()

    def _is_running(self):
        try:
            proc = psutil.Process(self._main_pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    def _restart(self):
        try:
            subprocess.Popen(
                [sys.executable, MAIN_SCRIPT],
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32" else 0,
            )
            logger.info("Main process restarted.")
        except Exception as e:
            logger.error(f"Restart failed: {e}")


class SelfWatchdog:
    """
    Standalone watchdog process — launched separately.
    Monitors the guardian exe and restarts if killed.
    """
    def __init__(self, target_name: str = "pc-guardian.exe"):
        self.target_name = target_name
        self._running = True

    def start(self):
        logger.info(f"SelfWatchdog monitoring: {self.target_name}")
        while self._running:
            time.sleep(CHECK_INTERVAL)
            if not self._find_target():
                logger.warning(f"{self.target_name} not found. Relaunching...")
                self._relaunch()

    def _find_target(self):
        for proc in psutil.process_iter(["name"]):
            try:
                if self.target_name.lower() in proc.info["name"].lower():
                    return True
            except Exception:
                pass
        return False

    def _relaunch(self):
        exe_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "dist", self.target_name
        )
        if os.path.exists(exe_path):
            try:
                subprocess.Popen(
                    [exe_path],
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32" else 0,
                )
            except Exception as e:
                logger.error(f"Relaunch failed: {e}")
