"""
PC Guardian — First Run Setup
Credentials hardcoded below — change and push to build new exe.
"""

import os
import sys
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.enc")
SETUP_FLAG  = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".setup_done")

# ══════════════════════════════════════════════════════════════
#   PUT YOUR CREDENTIALS HERE
#   Change these values, push to GitHub, download new .exe
# ══════════════════════════════════════════════════════════════

BOT_TOKEN         = "9210089363:AAEIbLdw_XzM7cibtONb3FhqKjnNWE3798s"
TELEGRAM_USER_ID  = "7505093216"         # your numeric Telegram ID
CHILD_NAME        = "Son"
LOCK_KEYWORD      = "lockson"
UNINSTALL_PASSWORD = "decdrv"
BEDTIME_ENABLED   = False
BEDTIME_LOCK_TIME = "21:00"
BEDTIME_UNLOCK_TIME = "16:00"

# ══════════════════════════════════════════════════════════════


def needs_setup() -> bool:
    return not os.path.exists(CONFIG_PATH) or not os.path.exists(SETUP_FLAG)


def run_first_setup():
    os.makedirs(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config"),
        exist_ok=True
    )

    from config.crypto import encrypt_config
    encrypt_config({
        "bot_token":          BOT_TOKEN,
        "allowed_user_id":    TELEGRAM_USER_ID,
        "uninstall_password": UNINSTALL_PASSWORD,
        "lock_keyword":       LOCK_KEYWORD,
        "child_name":         CHILD_NAME,
        "lock_message":       f"Take a breath {CHILD_NAME}. Dad is watching.",
        "daily_report_time":  "21:00",
        "school_schedule":    {"enabled": False, "lock_time": "08:00", "unlock_time": "15:00"},
        "bedtime_schedule":   {
            "enabled":      BEDTIME_ENABLED,
            "lock_time":    BEDTIME_LOCK_TIME,
            "unlock_time":  BEDTIME_UNLOCK_TIME
        },
        "panic_detection":    {"voice_enabled": True, "behavior_enabled": True, "volume_threshold": 0.7},
        "web_dashboard":      {"enabled": True, "port": 8080, "password": UNINSTALL_PASSWORD},
        "camera_enabled":     True,
        "mic_enabled":        True,
        "speaker_enabled":    True,
        "anthropic_api_key":  "",
    })

    with open(SETUP_FLAG, "w") as f:
        f.write("1")

    protect_from_deletion()


def protect_from_deletion():
    try:
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
        subprocess.run(
            f'icacls "{config_dir}" /deny Everyone:(D,DC)',
            shell=True, capture_output=True
        )
    except Exception:
        pass


if __name__ == "__main__":
    if needs_setup():
        run_first_setup()
