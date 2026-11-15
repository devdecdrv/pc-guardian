"""
PC Guardian — Main Entry Point
First launch: Ubuntu-style black screen setup.
After setup: runs hidden in background.
"""

import sys
import os
import ctypes
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.enc")
SETUP_FLAG  = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".setup_done")


def hide_console():
    """Hide the console window — run silently."""
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

    # Install startup entries once
    flag = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".installed")
    if not os.path.exists(flag):
        try:
            from core.startup import install_all
            if install_all():
                with open(flag, "w") as f: f.write("1")
        except Exception as e:
            logger.warning(f"Startup install: {e}")

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

    # MCP server
    try:
        import mcp_server
        mcp_server.init(cfg, lock_engine, camera, mic, speaker, activity)
        mcp_server.start_mcp_thread()
    except Exception as e:
        logger.warning(f"MCP: {e}")

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
    # ── Special args ──────────────────────────────────────────────────────────
    if "--change" in sys.argv:
        # Change credentials: python main.py --change
        from first_run import change_credentials
        change_credentials()
        sys.exit(0)

    if "--install-service" in sys.argv:
        from core.service import install_service
        install_service()
        sys.exit(0)

    if "--install-startup" in sys.argv:
        from core.startup import install_all
        install_all()
        print("Startup installed.")
        sys.exit(0)

    # ── First run setup ───────────────────────────────────────────────────────
    if needs_setup():
        from first_run import run_first_setup
        run_first_setup()

    # ── Hide console and start ────────────────────────────────────────────────
    hide_console()
    start_guardian()
