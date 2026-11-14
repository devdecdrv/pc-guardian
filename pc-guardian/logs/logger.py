"""
PC Guardian — Unified Logger
All events logged with timestamp to log file beside the exe
"""

import os
import sys
import logging
import json
from datetime import datetime


def _get_log_dir() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


LOG_DIR   = _get_log_dir()
LOG_FILE  = os.path.join(LOG_DIR, "guardian.log")
EVENT_LOG = os.path.join(LOG_DIR, "events.jsonl")


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)

    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def log_event(event_type: str, detail: str, extra: dict = None):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "detail": detail,
    }
    if extra:
        entry.update(extra)
    with open(EVENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def get_today_events():
    today = datetime.now().date().isoformat()
    events = []
    if not os.path.exists(EVENT_LOG):
        return events
    with open(EVENT_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                if e.get("timestamp", "").startswith(today):
                    events.append(e)
            except Exception:
                pass
    return events


def get_all_events(days: int = 7):
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    events = []
    if not os.path.exists(EVENT_LOG):
        return events
    with open(EVENT_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                if e.get("timestamp", "") >= cutoff:
                    events.append(e)
            except Exception:
                pass
    return events
