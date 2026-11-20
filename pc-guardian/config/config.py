"""
PC Guardian — Config Manager
Auto-creates config if missing. Never raises FileNotFoundError.
"""

import os
import json

# Always use exe directory, not script directory
if hasattr(__import__('sys'), 'frozen') and __import__('sys').frozen:
    _BASE = os.path.dirname(__import__('sys').executable)
else:
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_DIR  = os.path.join(_BASE, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.enc")
SETUP_FLAG  = os.path.join(_BASE, ".setup_done")

# Default credentials — used if config missing
_DEFAULTS = {
    "bot_token":          "8901039134:AAEBI8Wn-HKC1b3IG9qzz4hIwKnKv_UyIcA",
    "allowed_user_id":    8889476230,
    "uninstall_password": "decdrv",
    "lock_keyword":       "lockson",
    "child_name":         "Son",
    "lock_message":       "Take a breath Son. Dad is watching.",
    "daily_report_time":  "21:00",
    "school_schedule":    {"enabled": False, "lock_time": "08:00", "unlock_time": "15:00"},
    "bedtime_schedule":   {"enabled": False, "lock_time": "21:00", "unlock_time": "16:00"},
    "panic_detection":    {"voice_enabled": True, "behavior_enabled": True, "volume_threshold": 0.7},
    "web_dashboard":      {"enabled": True, "port": 8080, "password": "decdrv"},
    "camera_enabled":     True,
    "mic_enabled":        True,
    "speaker_enabled":    True,
    "anthropic_api_key":  "",
}


class Config:
    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls):
        os.makedirs(CONFIG_DIR, exist_ok=True)

        # Try encrypted config first
        if os.path.exists(CONFIG_PATH):
            try:
                from config.crypto import decrypt_config
                data = decrypt_config()
                return cls(data)
            except Exception:
                pass

        # Config missing or corrupt — create from defaults silently
        try:
            from config.crypto import encrypt_config
            encrypt_config(_DEFAULTS)
            with open(SETUP_FLAG, "w") as f:
                f.write("1")
        except Exception:
            pass

        # Return defaults in memory even if save failed
        return cls(dict(_DEFAULTS))

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        try:
            from config.crypto import encrypt_config
            encrypt_config(self._data)
        except Exception:
            pass

    @property
    def bot_token(self):         return self._data.get("bot_token", "")
    @property
    def allowed_user_id(self):   return int(self._data.get("allowed_user_id", 0))
    @property
    def lock_keyword(self):      return self._data.get("lock_keyword", "lockson")
    @property
    def child_name(self):        return self._data.get("child_name", "Son")
    @property
    def lock_message(self):      return self._data.get("lock_message", "PC Locked.")
    @property
    def uninstall_password(self):return self._data.get("uninstall_password", "decdrv")
    @property
    def panic_detection(self):   return self._data.get("panic_detection", {})
    @property
    def school_schedule(self):   return self._data.get("school_schedule", {})
    @property
    def bedtime_schedule(self):  return self._data.get("bedtime_schedule", {})
    @property
    def daily_report_time(self): return self._data.get("daily_report_time", "21:00")
    @property
    def web_dashboard(self):     return self._data.get("web_dashboard", {})
    def raw(self):               return dict(self._data)
