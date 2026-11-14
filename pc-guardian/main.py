"""
PC Guardian — Main Entry Point
Auto-creates config if missing, then starts everything.
"""

import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── AUTO SETUP IF CONFIG MISSING ─────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.enc")

if not os.path.exists(CONFIG_PATH):
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config"), exist_ok=True)
    from config.crypto import encrypt_config
    encrypt_config({
        "bot_token": "8901039134:AAEBI8Wn-HKC1b3IG9qzz4hIwKnKv_UyIcA",
        "allowed_user_id": 8889476230,
        "uninstall_password": "decdrv",
        "lock_keyword": "lockson",
        "child_name": "Son",
        "lock_message": "Take a breath. Dad is watching.",
        "daily_report_time": "21:00",
        "school_schedule": {"enabled": False, "lock_time": "08:00", "unlock_time": "15:00"},
        "bedtime_schedule": {"enabled": False, "lock_time": "21:00", "unlock_time": "16:00"},
        "panic_detection": {"voice_enabled": True, "behavior_enabled": True, "volume_threshold": 0.7},
        "web_dashboard": {"enabled": True, "port": 8080, "password": "decdrv"},
        "camera_enabled": True,
        "mic_enabled": True,
        "speaker_enabled": True,
    })

# ── STARTUP ───────────────────────────────────────────────────────────────────
from config.config import Config
from logs.logger import setup_logger
from core.lock_engine import LockEngine
from core.keyword_listener import KeywordListener
from core.watchdog import Watchdog
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
        logger.info(f"Thread started: {t.name}")

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
        elif sys.argv[1] == "--install-startup":
            from core.startup import install_all
            install_all()
            print("Startup installed.")
    else:
        start_guardian()
