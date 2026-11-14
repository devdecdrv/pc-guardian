"""
PC Guardian — Main Entry Point (FIXED)
- Installs startup on first run
- All subsystems wired correctly
"""

import sys
import os
import threading
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from logs.logger import setup_logger
from core.lock_engine import LockEngine
from core.watchdog import Watchdog
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

FIRST_RUN_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".installed")


def ensure_startup():
    """Install startup entries if not already done."""
    if not os.path.exists(FIRST_RUN_FLAG):
        try:
            from core.startup import install_all
            if install_all():
                with open(FIRST_RUN_FLAG, "w") as f:
                    f.write("1")
                logger.info("Startup entries installed.")
        except Exception as e:
            logger.warning(f"Startup install failed: {e}")


def start_guardian():
    cfg = Config.load()

    ensure_startup()

    lock_engine = LockEngine(cfg)
    speaker     = SpeakerSystem(cfg)
    camera      = CameraSystem(cfg)
    mic         = MicrophoneSystem(cfg, lock_engine)
    activity    = ActivityMonitor(cfg)
    behavior    = BehaviorMonitor(cfg, lock_engine, mic)
    reporter    = Reporter(cfg, activity)
    scheduler   = ScheduleEngine(cfg, lock_engine)
    tamper      = TamperDetect(cfg)

    bot = GuardianBot(
        cfg=cfg,
        lock_engine=lock_engine,
        camera=camera,
        mic=mic,
        speaker=speaker,
        activity=activity,
        scheduler=scheduler,
    )

    threads = [
        threading.Thread(target=activity.start,     daemon=True, name="Activity"),
        threading.Thread(target=behavior.start,     daemon=True, name="Behavior"),
        threading.Thread(target=scheduler.start,    daemon=True, name="Scheduler"),
        threading.Thread(target=reporter.start,     daemon=True, name="Reporter"),
        threading.Thread(target=tamper.start,       daemon=True, name="Tamper"),
        threading.Thread(
            target=KeywordListener(cfg, lock_engine).start,
            daemon=True, name="Keyword"
        ),
    ]

    for t in threads:
        t.start()
        logger.info(f"Thread started: {t.name}")

    logger.info("PC Guardian fully operational.")
    bot.run()  # blocking


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--install-service":
            from core.service import install_service
            install_service()
        elif sys.argv[1] == "--remove-service":
            from core.service import remove_service
            remove_service()
        elif sys.argv[1] == "--setup":
            from setup import run_setup
            run_setup()
        elif sys.argv[1] == "--install-startup":
            from core.startup import install_all
            install_all()
            print("Startup installed.")
    else:
        start_guardian()
