"""
PC Guardian — Behavior Monitor
Detects panic, frustration, long gaming sessions
Triggers Telegram alerts automatically
"""

import time
import threading
import logging
from datetime import datetime
from pynput import mouse, keyboard as kb
from logs.logger import log_event
from bot.alerts import send_alert

logger = logging.getLogger("behavior")

# Thresholds
RAPID_CLICK_THRESHOLD = 10    # clicks in RAPID_CLICK_WINDOW seconds = frustration
RAPID_CLICK_WINDOW = 3
RAPID_KEY_THRESHOLD = 20      # keypresses in window
RAPID_KEY_WINDOW = 3
LONG_SESSION_HOURS = 2        # alert after N hours on same app
COOLDOWN_SECONDS = 60         # min time between same type of alert


class BehaviorMonitor:
    def __init__(self, cfg, lock_engine, mic):
        self.cfg = cfg
        self.lock_engine = lock_engine
        self.mic = mic
        self._running = False

        self._click_times = []
        self._key_times = []
        self._last_alerts = {}

        # Register mic panic callback
        if mic:
            mic.set_panic_callback(self._on_voice_panic)

    def start(self):
        self._running = True
        logger.info("Behavior monitor started.")

        # Mouse listener
        mouse_listener = mouse.Listener(on_click=self._on_click)
        mouse_listener.start()

        # Keyboard listener
        key_listener = kb.Listener(on_press=self._on_key)
        key_listener.start()

        # Long session checker
        threading.Thread(target=self._session_check_loop, daemon=True).start()

    def _can_alert(self, alert_type: str) -> bool:
        now = time.time()
        last = self._last_alerts.get(alert_type, 0)
        if now - last > COOLDOWN_SECONDS:
            self._last_alerts[alert_type] = now
            return True
        return False

    def _on_click(self, x, y, button, pressed):
        if pressed:
            now = time.time()
            self._click_times.append(now)
            # Clean old entries
            self._click_times = [t for t in self._click_times if now - t < RAPID_CLICK_WINDOW]
            if len(self._click_times) >= RAPID_CLICK_THRESHOLD:
                self._click_times.clear()
                self._trigger_behavior_alert("rage_clicking")

    def _on_key(self, key):
        now = time.time()
        self._key_times.append(now)
        self._key_times = [t for t in self._key_times if now - t < RAPID_KEY_WINDOW]
        if len(self._key_times) >= RAPID_KEY_THRESHOLD:
            self._key_times.clear()
            self._trigger_behavior_alert("rage_typing")

    def _session_check_loop(self):
        while self._running:
            time.sleep(300)  # check every 5 min
            try:
                from monitor.activity import ActivityMonitor
                # Check if gaming too long — integrated at startup
            except Exception:
                pass

    def _trigger_behavior_alert(self, reason: str):
        if not self._can_alert(reason):
            return

        messages = {
            "rage_clicking": f"⚠️ *Frustration detected!*\n{self.cfg.child_name} is rage-clicking.\nCheck in?",
            "rage_typing": f"⚠️ *Frustration detected!*\n{self.cfg.child_name} is hammering the keyboard.\nCheck in?",
            "long_session": f"⏰ *Long session alert!*\n{self.cfg.child_name} has been gaming for {LONG_SESSION_HOURS}+ hours.",
        }

        msg = messages.get(reason, f"⚠️ Behavior alert: {reason}")
        log_event("PANIC_BEHAVIOR", reason)
        logger.warning(f"Behavior alert: {reason}")

        # Try to get a snapshot
        try:
            from av.camera import CameraSystem
            # Camera is passed at init in full integration
            send_alert(msg)
        except Exception:
            send_alert(msg)

    def _on_voice_panic(self, clip_path: str, reason: str):
        if not self._can_alert("voice_" + reason):
            return
        msg = (
            f"🚨 *Raised voice detected!*\n"
            f"{self.cfg.child_name} sounds distressed.\n"
            f"Audio clip attached."
        )
        log_event("PANIC_VOICE", reason)
        logger.warning(f"Voice panic: {reason}")
        send_alert(msg, audio_path=clip_path)

    def alert_long_session(self, app_name: str, hours: float):
        if not self._can_alert("long_session"):
            return
        msg = (
            f"⏰ *Long session alert!*\n"
            f"{self.cfg.child_name} has been on *{app_name}* for {hours:.1f} hours.\n"
            f"Consider a break."
        )
        log_event("LONG_SESSION", f"{app_name} — {hours:.1f}h")
        send_alert(msg)
