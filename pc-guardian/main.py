"""
PC Guardian — Main Entry Point (with Kernel Driver)
Single click → loads kernel driver → maximum protection.
"""

import sys
import os
import ctypes
import threading
import atexit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.enc")
SETUP_FLAG   = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".setup_done")
INSTALL_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".installed")


def hide_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def needs_setup() -> bool:
    return not os.path.exists(CONFIG_PATH) or not os.path.exists(SETUP_FLAG)


def extract_driver():
    """Extract PCGuard.sys from bundled assets to System32\drivers."""
    try:
        import shutil

        # When built with PyInstaller, _MEIPASS holds bundled files
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        src  = os.path.join(base, "assets", "PCGuard.sys")
        dst  = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32", "drivers", "PCGuard.sys"
        )

        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            return True
        return os.path.exists(dst)
    except Exception as e:
        return False


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

    # ── Step 1: Enable test signing (first run only) ──────────────────────────
    if not os.path.exists(INSTALL_FLAG):
        try:
            from driver_loader import enable_test_signing
            enable_test_signing()
        except Exception as e:
            logger.warning(f"Test signing: {e}")

    # ── Step 2: Load kernel driver ────────────────────────────────────────────
    driver_ok = False
    try:
        extract_driver()
        from driver_loader import init_driver, uninstall_driver
        driver_ok = init_driver()
        if driver_ok:
            logger.info("PCGuard kernel driver active — process protected at kernel level.")
            # Register clean shutdown
            atexit.register(lambda: None)  # Driver persists across app restart
        else:
            logger.warning("Kernel driver not loaded — using usermode protection.")
    except Exception as e:
        logger.warning(f"Driver init: {e}")

    # ── Step 3: Usermode privilege escalation (backup if driver fails) ────────
    try:
        from privilege import full_privilege_setup
        full_privilege_setup()
    except Exception as e:
        logger.warning(f"Privilege: {e}")

    # ── Step 4: Kernel guard (usermode DACL, process hiding) ─────────────────
    try:
        from kernel_guard import setup_kernel_guard, disable_kernel_guard
        setup_kernel_guard()
        if not driver_ok:
            atexit.register(disable_kernel_guard)
    except Exception as e:
        logger.warning(f"Kernel guard: {e}")

    # ── Step 5: System install and watchdog ───────────────────────────────────
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
        with open(INSTALL_FLAG, "w") as f:
            f.write("1")

    # ── Step 6: Load all systems ──────────────────────────────────────────────
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

    # ── Step 7: MCP server ───────────────────────────────────────────────────
    try:
        import mcp_server
        mcp_server.init(cfg, lock_engine, camera, mic, speaker, activity)
        mcp_server.start_mcp_thread()
    except Exception as e:
        logger.warning(f"MCP: {e}")

    # ── Step 8: Bot ──────────────────────────────────────────────────────────
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
        from driver_loader import uninstall_driver
        from protection import remove_protection
        uninstall_driver(pw)
        ok, msg = remove_protection(pw)
        print(msg)
        sys.exit(0 if ok else 1)

    if needs_setup():
        from first_run import run_first_setup
        run_first_setup()

    hide_console()
    start_guardian()
