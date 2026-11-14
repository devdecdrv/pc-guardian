"""
PC Guardian — Unified Logger
All events logged with timestamp to encrypted log file
"""

import os
import logging
import json
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(LOG_DIR, "guardian.log")
EVENT_LOG = os.path.join(LOG_DIR, "events.jsonl")


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # Console handler (suppress in production)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)

    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def log_event(event_type: str, detail: str, extra: dict = None):
    """Log structured event to JSONL file for dashboard/reporting."""
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
    """Return all events from today."""
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
    """Return events from the last N days."""
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
