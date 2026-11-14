"""
PC Guardian — Main Entry Point
Starts all subsystems: service, bot, monitor, scheduler, AV, dashboard
"""

import sys
import os
import threading
import logging
import asyncio
import time

# Add project root to path
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


def start_guardian():
    cfg = Config.load()

    # Core systems
    lock_engine = LockEngine(cfg)
    speaker = SpeakerSystem(cfg)
    camera = CameraSystem(cfg)
    mic = MicrophoneSystem(cfg, lock_engine)
    activity = ActivityMonitor(cfg)
    behavior = BehaviorMonitor(cfg, lock_engine, mic)
    reporter = Reporter(cfg, activity)
    scheduler = ScheduleEngine(cfg, lock_engine)
    tamper = TamperDetect(cfg)

    # Telegram bot — owns the event loop
    bot = GuardianBot(
        cfg=cfg,
        lock_engine=lock_engine,
        camera=camera,
        mic=mic,
        speaker=speaker,
        activity=activity,
        scheduler=scheduler,
    )

    # Start background threads
    threads = [
        threading.Thread(target=activity.start, daemon=True, name="ActivityMonitor"),
        threading.Thread(target=behavior.start, daemon=True, name="BehaviorMonitor"),
        threading.Thread(target=scheduler.start, daemon=True, name="Scheduler"),
        threading.Thread(target=reporter.start, daemon=True, name="Reporter"),
        threading.Thread(target=tamper.start, daemon=True, name="TamperDetect"),
    ]

    keyword_listener = KeywordListener(cfg, lock_engine)
    threads.append(threading.Thread(target=keyword_listener.start, daemon=True, name="KeywordListener"))

    for t in threads:
        t.start()
        logger.info(f"Started thread: {t.name}")

    logger.info("PC Guardian fully operational.")

    # Run bot (blocking — owns main thread event loop)
    bot.run()


if __name__ == "__main__":
    # Check if running as service installer
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
    else:
        start_guardian()
