"""
PC Guardian — Quick Setup
Run this once before main.py to create the encrypted config.
Usage: python setup_quick.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.crypto import encrypt_config

config_data = {
    "bot_token": "8901039134:AAEBI8Wn-HKC1b3IG9qzz4hIwKnKv_UyIcA",
    "allowed_user_id": 8889476230,
    "uninstall_password": "decdrv",
    "lock_keyword": "lockson",
    "child_name": "Son",
    "lock_message": "Take a breath. Dad is watching.",
    "daily_report_time": "21:00",
    "school_schedule": {
        "enabled": False,
        "lock_time": "08:00",
        "unlock_time": "15:00"
    },
    "bedtime_schedule": {
        "enabled": False,
        "lock_time": "21:00",
        "unlock_time": "16:00"
    },
    "panic_detection": {
        "voice_enabled": True,
        "behavior_enabled": True,
        "volume_threshold": 0.7
    },
    "web_dashboard": {
        "enabled": True,
        "port": 8080,
        "password": "decdrv"
    },
    "camera_enabled": True,
    "mic_enabled": True,
    "speaker_enabled": True,
}

encrypt_config(config_data)
print("Config created successfully. Now run: python main.py")
