"""
PC Guardian — Config Manager
Loads and manages encrypted configuration
"""

import os
import sys
import json
from config.crypto import decrypt_config, encrypt_config


def _get_config_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config", "config.enc")


class Config:
    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls):
        config_path = _get_config_path()
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                "Config not found. Run: python main.py --setup"
            )
        data = decrypt_config()
        return cls(data)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        encrypt_config(self._data)

    @property
    def bot_token(self):
        return self._data["bot_token"]

    @property
    def allowed_user_id(self):
        return int(self._data["allowed_user_id"])

    @property
    def lock_keyword(self):
        return self._data.get("lock_keyword", "lockson")

    @property
    def child_name(self):
        return self._data.get("child_name", "Son")

    @property
    def lock_message(self):
        return self._data.get("lock_message", "Take a breath. Dad is watching.")

    @property
    def uninstall_password(self):
        return self._data.get("uninstall_password", "")

    @property
    def panic_detection(self):
        return self._data.get("panic_detection", {})

    @property
    def school_schedule(self):
        return self._data.get("school_schedule", {})

    @property
    def bedtime_schedule(self):
        return self._data.get("bedtime_schedule", {})

    @property
    def daily_report_time(self):
        return self._data.get("daily_report_time", "21:00")

    @property
    def web_dashboard(self):
        return self._data.get("web_dashboard", {})

    def raw(self):
        return dict(self._data)
