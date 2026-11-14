"""
PC Guardian — Config Manager
Loads and manages encrypted configuration
"""

import os
import json
from config.crypto import decrypt_config, encrypt_config

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.enc")


class Config:
    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls):
        if not os.path.exists(CONFIG_PATH):
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
