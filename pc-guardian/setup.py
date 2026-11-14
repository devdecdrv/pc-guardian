"""
PC Guardian — First Run Setup Wizard
Collects bot token, user ID, password, and preferences
"""

import os
import sys
import json
import getpass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.crypto import encrypt_config


def run_setup():
    print("\n" + "="*50)
    print("   PC GUARDIAN — FIRST TIME SETUP")
    print("="*50)
    print()

    print("Step 1: Telegram Bot Token")
    print("  → Go to Telegram, open @BotFather")
    print("  → Send /newbot, follow instructions")
    print("  → Copy the token it gives you")
    bot_token = input("\nPaste your Bot Token: ").strip()

    print("\nStep 2: Your Telegram User ID")
    print("  → Open @userinfobot on Telegram")
    print("  → It will show your numeric ID")
    user_id = input("\nPaste your User ID (numbers only): ").strip()

    print("\nStep 3: Set Uninstall Password")
    print("  → This protects the app from being removed")
    while True:
        password = getpass.getpass("Set password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password == confirm:
            break
        print("  Passwords don't match. Try again.")

    print("\nStep 4: Lock Keyword")
    print("  → Type this word anywhere to instantly lock the PC")
    keyword = input("Set lock keyword (default: lockson): ").strip()
    if not keyword:
        keyword = "lockson"

    print("\nStep 5: Child's Name (shown on lock screen)")
    child_name = input("Child's name: ").strip()
    if not child_name:
        child_name = "Son"

    config_data = {
        "bot_token": bot_token,
        "allowed_user_id": int(user_id),
        "uninstall_password": password,
        "lock_keyword": keyword,
        "child_name": child_name,
        "lock_message": f"Take a breath, {child_name}. Dad is watching.",
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
            "password": password
        },
        "camera_enabled": True,
        "mic_enabled": True,
        "speaker_enabled": True,
    }

    encrypt_config(config_data)
    print("\n✓ Configuration saved and encrypted.")
    print("\nPC Guardian is ready. Run main.py to start.\n")


if __name__ == "__main__":
    run_setup()
