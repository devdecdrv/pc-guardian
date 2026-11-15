"""
PC Guardian — Tamper Detection (FIXED)
- False positive on startup registry fixed
- Cooldown between same alert type
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

CHECK_INTERVAL  = 10
REGISTRY_CHECK  = 60   # check registry every 60s not 30s
ALERT_COOLDOWN  = 300  # 5 min between same alert


class TamperDetect:
    def __init__(self, cfg):
        self.cfg  = cfg
        self._own_pid     = os.getpid()
        self._wrong_pw    = 0
        self._last_alerts = {}
        self._startup_grace = time.time() + 30  # 30s grace on boot — ignore registry alerts

    def start(self):
        logger.info("Tamper detection active.")
        threading.Thread(target=self._watch_registry, daemon=True).start()

    def _can_alert(self, key: str) -> bool:
        now = time.time()
        if now - self._last_alerts.get(key, 0) > ALERT_COOLDOWN:
            self._last_alerts[key] = now
            return True
        return False

    def _watch_registry(self):
        try:
            import winreg
            key_path   = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            value_name = "PCGuardian"

            while True:
                time.sleep(REGISTRY_CHECK)

                # Skip during startup grace period
                if time.time() < self._startup_grace:
                    continue

                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                    winreg.QueryValueEx(key, value_name)
                    winreg.CloseKey(key)
                    # Entry exists — good, re-arm grace
                except FileNotFoundError:
                    if self._can_alert("registry"):
                        self._alert("⚠️ Startup registry entry removed! Someone may have tampered.")
                        # Re-add it
                        try:
                            from core.startup import install_registry
                            install_registry()
                            logger.info("Registry entry restored.")
                        except Exception:
                            pass
                except Exception:
                    pass
        except ImportError:
            pass

    def check_uninstall_password(self, attempt: str) -> bool:
        if attempt == self.cfg.uninstall_password:
            self._wrong_pw = 0
            return True
        self._wrong_pw += 1
        log_event("TAMPER_PASSWORD", f"Wrong password attempt #{self._wrong_pw}")
        if self._wrong_pw >= 3:
            self._alert(
                f"🚨 *Tamper Alert!*\n"
                f"Someone tried to uninstall PC Guardian {self._wrong_pw}x with wrong password!"
            )
        return False

    def _alert(self, message: str):
        log_event("TAMPER", message)
        logger.warning(f"Tamper: {message}")
        send_alert(f"🚨 *TAMPER ALERT*\n{message}")
