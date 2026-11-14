"""
PC Guardian — Tamper Detection
Detects and alerts on attempts to kill, modify, or uninstall the guardian
"""

import os
import sys
import time
import psutil
import logging
import threading
from logs.logger import log_event
from bot.alerts import send_alert

logger = logging.getLogger("tamper")

CHECK_INTERVAL = 5  # seconds


class TamperDetect:
    def __init__(self, cfg):
        self.cfg = cfg
        self._running = False
        self._own_pid = os.getpid()
        self._wrong_password_count = 0

    def start(self):
        self._running = True
        logger.info("Tamper detection active.")
        threading.Thread(target=self._watch_process, daemon=True).start()
        threading.Thread(target=self._watch_registry, daemon=True).start()

    def _watch_process(self):
        """Alert if our process count drops (someone killed a component)."""
        while self._running:
            time.sleep(CHECK_INTERVAL)
            # Check if critical process is still running
            try:
                proc = psutil.Process(self._own_pid)
                if not proc.is_running():
                    self._alert("Process killed")
            except psutil.NoSuchProcess:
                self._alert("Guardian process killed!")

    def _watch_registry(self):
        """Watch startup registry key for modifications."""
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            value_name = "PCGuardian"

            while self._running:
                time.sleep(30)
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                    winreg.QueryValueEx(key, value_name)
                    winreg.CloseKey(key)
                except FileNotFoundError:
                    self._alert("⚠️ Startup registry entry removed! Someone may have tampered.")
                except Exception:
                    pass
        except ImportError:
            pass

    def check_uninstall_password(self, attempt: str) -> bool:
        correct = self.cfg.uninstall_password
        if attempt == correct:
            self._wrong_password_count = 0
            return True
        self._wrong_password_count += 1
        log_event("TAMPER_PASSWORD", f"Wrong uninstall password attempt #{self._wrong_password_count}")
        if self._wrong_password_count >= 3:
            self._alert(
                f"🚨 *Tamper Alert!*\n"
                f"Someone tried to uninstall PC Guardian {self._wrong_password_count} times with wrong password!\n"
                f"PC is still protected."
            )
        return False

    def _alert(self, message: str):
        full_msg = f"🚨 *TAMPER ALERT*\n{message}"
        log_event("TAMPER", message)
        logger.warning(f"Tamper detected: {message}")
        send_alert(full_msg)
