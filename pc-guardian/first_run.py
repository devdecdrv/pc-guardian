"""
PC Guardian — First Run Setup
Ubuntu-style black terminal screen on first launch.
Collects credentials, saves encrypted, then hides itself.
Delete protection: requires password DECDRV
"""

import os
import sys
import ctypes
import subprocess
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.enc")
SETUP_FLAG  = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".setup_done")
DELETE_PASSWORD = "DECDRV"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Relaunch as administrator if not already."""
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit(0)


def clear():
    os.system("cls")


def print_header():
    clear()
    print("\033[90m" + "="*60 + "\033[0m")
    print("\033[97m\033[1m        PC GUARDIAN — FIRST TIME SETUP\033[0m")
    print("\033[90m" + "="*60 + "\033[0m")
    print()


def prompt(label: str, secret: bool = False) -> str:
    if secret:
        import getpass
        return getpass.getpass(f"  \033[93m{label}:\033[0m ").strip()
    return input(f"  \033[93m{label}:\033[0m ").strip()


def run_first_setup():
    """Ubuntu-style black screen setup."""
    run_as_admin()

    print_header()
    print("  \033[90mThis screen appears only once.\033[0m")
    print("  \033[90mFill in your details to activate PC Guardian.\033[0m")
    print()

    # ── Telegram Bot Token ────────────────────────────────────────────────────
    print("  \033[96mStep 1: Telegram Bot Token\033[0m")
    print("  \033[90m  → Open Telegram → @BotFather → /newbot → copy token\033[0m")
    print()
    while True:
        token = prompt("Bot Token")
        if len(token) > 20 and ":" in token:
            break
        print("  \033[91m  Invalid token. Try again.\033[0m")

    # ── Telegram User ID ──────────────────────────────────────────────────────
    print()
    print("  \033[96mStep 2: Your Telegram User ID\033[0m")
    print("  \033[90m  → Open Telegram → @userinfobot → copy your numeric ID\033[0m")
    print()
    while True:
        uid = prompt("Your Telegram User ID")
        if uid.isdigit():
            break
        print("  \033[91m  Must be numbers only. Try again.\033[0m")

    # ── Child Name ────────────────────────────────────────────────────────────
    print()
    print("  \033[96mStep 3: Child's Name\033[0m")
    print("  \033[90m  → Shown on lock screen and in messages\033[0m")
    print()
    child_name = prompt("Child's name (default: Son)")
    if not child_name:
        child_name = "Son"

    # ── Lock Keyword ──────────────────────────────────────────────────────────
    print()
    print("  \033[96mStep 4: Lock Keyword\033[0m")
    print("  \033[90m  → Type this word anywhere to instantly lock the PC\033[0m")
    print()
    keyword = prompt("Lock keyword (default: lockson)")
    if not keyword:
        keyword = "lockson"

    # ── Uninstall Password ────────────────────────────────────────────────────
    print()
    print("  \033[96mStep 5: Uninstall Password\033[0m")
    print("  \033[90m  → Required to delete or uninstall PC Guardian\033[0m")
    print()
    while True:
        pw1 = prompt("Set password", secret=True)
        pw2 = prompt("Confirm password", secret=True)
        if pw1 == pw2 and len(pw1) >= 4:
            uninstall_pw = pw1
            break
        print("  \033[91m  Passwords don't match or too short. Try again.\033[0m")

    # ── Bedtime Schedule ──────────────────────────────────────────────────────
    print()
    print("  \033[96mStep 6: Bedtime Schedule (optional)\033[0m")
    print("  \033[90m  → Auto-lock every night at set time\033[0m")
    print()
    enable_bed = prompt("Enable bedtime lock? (y/n, default: n)").lower()
    bedtime_enabled = enable_bed == "y"
    bedtime_lock    = "21:00"
    bedtime_unlock  = "16:00"
    if bedtime_enabled:
        bedtime_lock   = prompt("Lock time (default: 21:00)") or "21:00"
        bedtime_unlock = prompt("Unlock time (default: 16:00)") or "16:00"

    # ── Save ──────────────────────────────────────────────────────────────────
    print()
    print("  \033[90mSaving configuration...\033[0m")

    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config"), exist_ok=True)

    from config.crypto import encrypt_config
    encrypt_config({
        "bot_token":          token,
        "allowed_user_id":    int(uid),
        "uninstall_password": uninstall_pw,
        "lock_keyword":       keyword,
        "child_name":         child_name,
        "lock_message":       f"Take a breath {child_name}. Dad is watching.",
        "daily_report_time":  "21:00",
        "school_schedule":    {"enabled": False, "lock_time": "08:00", "unlock_time": "15:00"},
        "bedtime_schedule":   {"enabled": bedtime_enabled, "lock_time": bedtime_lock, "unlock_time": bedtime_unlock},
        "panic_detection":    {"voice_enabled": True, "behavior_enabled": True, "volume_threshold": 0.7},
        "web_dashboard":      {"enabled": True, "port": 8080, "password": uninstall_pw},
        "camera_enabled":     True,
        "mic_enabled":        True,
        "speaker_enabled":    True,
        "anthropic_api_key":  "",
    })

    # Mark setup done
    with open(SETUP_FLAG, "w") as f:
        f.write("1")

    print("  \033[92m✓ Configuration saved.\033[0m")
    print()
    print("  \033[97mPC Guardian is now active.\033[0m")
    print("  \033[90mThis window will close in 3 seconds...\033[0m")
    time.sleep(3)
    clear()


def change_credentials():
    """
    Change any credential — requires current uninstall password.
    Called via: python first_run.py --change
    """
    run_as_admin()
    print_header()
    print("  \033[96mCHANGE CREDENTIALS\033[0m")
    print()

    # Verify identity
    from config.crypto import decrypt_config, encrypt_config
    try:
        cfg = decrypt_config()
    except Exception:
        print("  \033[91mNo config found. Run setup first.\033[0m")
        time.sleep(2)
        return

    entered = prompt("Enter current password to continue", secret=True)
    if entered != cfg.get("uninstall_password", ""):
        print("  \033[91mWrong password. Access denied.\033[0m")
        time.sleep(2)
        return

    print()
    print("  \033[90mWhat do you want to change?\033[0m")
    print("  1. Bot Token")
    print("  2. Telegram User ID")
    print("  3. Child Name")
    print("  4. Lock Keyword")
    print("  5. Uninstall Password")
    print("  6. Bedtime Schedule")
    print("  7. Show current settings")
    print()

    choice = prompt("Choice (1-7)")

    if choice == "1":
        cfg["bot_token"] = prompt("New Bot Token")
    elif choice == "2":
        uid = prompt("New Telegram User ID")
        if uid.isdigit():
            cfg["allowed_user_id"] = int(uid)
    elif choice == "3":
        cfg["child_name"] = prompt("New child name")
    elif choice == "4":
        cfg["lock_keyword"] = prompt("New lock keyword")
    elif choice == "5":
        pw1 = prompt("New password", secret=True)
        pw2 = prompt("Confirm", secret=True)
        if pw1 == pw2:
            cfg["uninstall_password"] = pw1
            cfg["web_dashboard"]["password"] = pw1
        else:
            print("  \033[91mPasswords don't match.\033[0m")
            time.sleep(2)
            return
    elif choice == "6":
        enable = prompt("Enable bedtime? (y/n)").lower() == "y"
        cfg["bedtime_schedule"]["enabled"] = enable
        if enable:
            cfg["bedtime_schedule"]["lock_time"]   = prompt("Lock time (HH:MM)") or "21:00"
            cfg["bedtime_schedule"]["unlock_time"] = prompt("Unlock time (HH:MM)") or "16:00"
    elif choice == "7":
        print()
        print(f"  Bot token:    {cfg['bot_token'][:20]}...")
        print(f"  User ID:      {cfg['allowed_user_id']}")
        print(f"  Child name:   {cfg['child_name']}")
        print(f"  Lock keyword: {cfg['lock_keyword']}")
        print(f"  Bedtime:      {'ON' if cfg['bedtime_schedule'].get('enabled') else 'OFF'}")
        print()
        input("  Press Enter to exit...")
        return

    encrypt_config(cfg)
    print()
    print("  \033[92m✓ Updated. Restart PC Guardian to apply.\033[0m")
    time.sleep(2)
    clear()


def protect_from_deletion():
    """
    Make the exe and config hard to delete without password.
    Sets ACL via icacls to deny delete for non-admin.
    """
    try:
        exe = sys.executable if getattr(sys, "frozen", False) else __file__
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

        # Deny delete permission for Everyone except SYSTEM
        subprocess.run(
            f'icacls "{exe}" /deny Everyone:(D)',
            shell=True, capture_output=True
        )
        subprocess.run(
            f'icacls "{config_dir}" /deny Everyone:(D,DC)',
            shell=True, capture_output=True
        )
    except Exception:
        pass


def hide_process():
    """Hide the console window after setup."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def needs_setup() -> bool:
    return not os.path.exists(CONFIG_PATH) or not os.path.exists(SETUP_FLAG)


if __name__ == "__main__":
    if "--change" in sys.argv:
        change_credentials()
    elif "--protect" in sys.argv:
        protect_from_deletion()
        print("Protection applied.")
    else:
        if needs_setup():
            run_first_setup()
        protect_from_deletion()
