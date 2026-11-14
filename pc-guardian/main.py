"""
PC Guardian — Main Entry Point
Starts all subsystems: service, bot, monitor, scheduler, AV, dashboard
"""

import sys
import os
import threading
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from config.crypto import encrypt_config
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


def _auto_setup():
    """Write pre-filled config on first run — no wizard needed."""
    encrypt_config({
        "bot_token": "8901039134:AAEBI8Wn-HKC1b3IG9qzz4hIwKnKv_UyIcA",
        "allowed_user_id": 8889476230,
        "uninstall_password": "decdrv",
        "lock_keyword": "lockson",
        "child_name": "Son",
        "lock_message": "Take a breath, Son. Dad is watching.",
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
            "password": "decdrv"
        },
        "camera_enabled": True,
        "mic_enabled": True,
        "speaker_enabled": True,
    })
    logger.info("First run — config auto-generated.")


def start_guardian():
    # Auto-setup on first run if no config exists
    try:
        cfg = Config.load()
    except FileNotFoundError:
        logger.info("No config found — running auto-setup.")
        _auto_setup()
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
        threading.Thread(target=activity.start,  daemon=True, name="ActivityMonitor"),
        threading.Thread(target=behavior.start,  daemon=True, name="BehaviorMonitor"),
        threading.Thread(target=scheduler.start, daemon=True, name="Scheduler"),
        threading.Thread(target=reporter.start,  daemon=True, name="Reporter"),
        threading.Thread(target=tamper.start,    daemon=True, name="TamperDetect"),
    ]

    keyword_listener = KeywordListener(cfg, lock_engine)
    threads.append(threading.Thread(target=keyword_listener.start, daemon=True, name="KeywordListener"))

    for t in threads:
        t.start()
        logger.info(f"Started thread: {t.name}")

    logger.info("PC Guardian fully operational.")
    bot.run()


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
    else:
        start_guardian()
