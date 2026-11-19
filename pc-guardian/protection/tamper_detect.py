"""
PC Guardian — Tamper Detection (FIXED v3)
- Grace period 30s → 120s
- Registry check only after full startup confirmed
- Self-heal: re-adds registry if missing instead of just alerting
- Cooldown 5 min between same alert
"""

import os
import time
import logging
import threading
from logs.logger import log_event
from bot.alerts import send_alert

logger = logging.getLogger("tamper")

ALERT_COOLDOWN   = 300   # 5 min between same alert type
REGISTRY_INTERVAL = 120  # check every 2 min
STARTUP_GRACE    = 120   # 2 min grace on boot — no false alerts


class TamperDetect:
    def __init__(self, cfg):
        self.cfg          = cfg
        self._wrong_pw    = 0
        self._last_alerts = {}
        self._boot_time   = time.time()
        self._reg_ok      = False   # True once we confirm registry is set

    def start(self):
        logger.info("Tamper detection active.")
        # Wait for full startup before watching anything
        threading.Thread(
            target=self._delayed_start,
            daemon=True, name="TamperInit"
        ).start()

    def _delayed_start(self):
        # Wait full grace period before starting any checks
        time.sleep(STARTUP_GRACE)
        logger.info("Tamper detection checks active.")

        # First confirm registry entry exists (and add it if missing silently)
        self._ensure_registry()
        self._reg_ok = True

        # Now start watching
        threading.Thread(target=self._watch_registry, daemon=True).start()

    def _can_alert(self, key: str) -> bool:
        now  = time.time()
        last = self._last_alerts.get(key, 0)
        if now - last > ALERT_COOLDOWN:
            self._last_alerts[key] = now
            return True
        return False

    def _ensure_registry(self):
        """Add registry entry if missing — silent, no alert."""
        try:
            import winreg
            key_path  = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            value     = "WindowsSecurityService"

            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                winreg.QueryValueEx(k, value)
                winreg.CloseKey(k)
                # Entry exists — good
            except FileNotFoundError:
                # Missing — add silently, no alert
                from core.startup import install_registry
                install_registry()
                logger.info("Registry entry re-added silently.")
        except Exception as e:
            logger.warning(f"Registry ensure: {e}")

    def _watch_registry(self):
        """Watch registry — only alert if entry disappears AFTER startup."""
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            value    = "WindowsSecurityService"

            while True:
                time.sleep(REGISTRY_INTERVAL)

                # Only check after registry confirmed OK at startup
                if not self._reg_ok:
                    continue

                try:
                    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                    winreg.QueryValueEx(k, value)
                    winreg.CloseKey(k)
                    # Still there — good

                except FileNotFoundError:
                    # Actually missing AFTER startup — real tamper
                    logger.warning("Registry entry removed after startup — restoring.")
                    self._ensure_registry()

                    if self._can_alert("registry"):
                        self._alert(
                            "⚠️ Startup registry entry was removed and restored.\n"
                            "Someone may have tried to disable PC Guardian."
                        )
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Registry watch error: {e}")

    def check_uninstall_password(self, attempt: str) -> bool:
        correct = self.cfg.uninstall_password
        if attempt == correct:
            self._wrong_pw = 0
            return True
        self._wrong_pw += 1
        log_event("TAMPER_PASSWORD", f"Wrong password attempt #{self._wrong_pw}")
        if self._wrong_pw >= 3 and self._can_alert("wrong_password"):
            self._alert(
                f"🚨 Someone tried to uninstall PC Guardian {self._wrong_pw}x "
                f"with wrong password!"
            )
        return False

    def _alert(self, message: str):
        log_event("TAMPER", message)
        logger.warning(f"Tamper: {message}")
        send_alert(f"🚨 *TAMPER ALERT*\n{message}")
