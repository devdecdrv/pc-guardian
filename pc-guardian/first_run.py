"""
PC Guardian — First Run
Credentials hardcoded here. No popup, no input needed.
Change values below → push → new exe builds automatically.
"""

import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ══════════════════════════════════════════════
#   CHANGE YOUR CREDENTIALS HERE
# ══════════════════════════════════════════════
BOT_TOKEN          = "8901039134:AAEBI8Wn-HKC1b3IG9qzz4hIwKnKv_UyIcA"
TELEGRAM_USER_ID   = 8889476230
CHILD_NAME         = "Son"
LOCK_KEYWORD       = "lockson"
UNINSTALL_PASSWORD = "decdrv"
BEDTIME_ENABLED    = False
BEDTIME_LOCK       = "21:00"
BEDTIME_UNLOCK     = "16:00"
# ══════════════════════════════════════════════

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR  = os.path.join(BASE_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.enc")
SETUP_FLAG  = os.path.join(BASE_DIR, ".setup_done")


def needs_setup() -> bool:
    return not os.path.exists(CONFIG_PATH) or not os.path.exists(SETUP_FLAG)


def run_first_setup():
    os.makedirs(CONFIG_DIR, exist_ok=True)

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
            "enabled":     BEDTIME_ENABLED,
            "lock_time":   BEDTIME_LOCK,
            "unlock_time": BEDTIME_UNLOCK,
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

    _protect_config()


def _protect_config():
    try:
        subprocess.run(
            f'icacls "{CONFIG_DIR}" /deny Everyone:(D,DC)',
            shell=True, capture_output=True
        )
    except Exception:
        pass


if __name__ == "__main__":
    run_first_setup()
    print("Config created.")
