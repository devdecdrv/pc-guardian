"""
PC Guardian — Activity Monitor
Tracks app usage, session time, running processes
"""

import psutil
import time
import threading
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from logs.logger import log_event

logger = logging.getLogger("activity")

GAME_KEYWORDS = [
    "steam", "epicgames", "roblox", "minecraft", "fortnite",
    "valorant", "csgo", "pubg", "gta", "league", "dota",
    "battlenet", "origin", "uplay", "gameoverlayui"
]

VIDEO_KEYWORDS = ["youtube", "netflix", "prime", "disney", "vlc", "mpv"]


class ActivityMonitor:
    def __init__(self, cfg):
        self.cfg = cfg
        self._running = False
        self._app_times = defaultdict(float)   # app_name -> minutes today
        self._session_start = datetime.now()
        self._check_interval = 10  # seconds
        self._last_active_app = None

    def start(self):
        self._running = True
        logger.info("Activity monitor started.")
        while self._running:
            self._tick()
            time.sleep(self._check_interval)

    def stop(self):
        self._running = False

    def _tick(self):
        try:
            active = self._get_active_window_name()
            if active:
                self._app_times[active] += self._check_interval / 60.0
                self._last_active_app = active
        except Exception:
            pass

    def _get_active_window_name(self) -> str:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc = psutil.Process(pid.value)
            return proc.name().replace(".exe", "").lower()
        except Exception:
            return None

    def get_running_apps(self) -> list:
        apps = set()
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info["name"]
                if name and not name.lower() in [
                    "system", "svchost.exe", "csrss.exe",
                    "lsass.exe", "smss.exe", "wininit.exe"
                ]:
                    apps.add(name)
            except Exception:
                pass
        return sorted(list(apps))

    def get_top_apps_today(self, n: int = 5) -> list:
        sorted_apps = sorted(
            self._app_times.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [(name, round(mins)) for name, mins in sorted_apps[:n]]

    def get_active_apps_summary(self) -> str:
        top = self.get_top_apps_today(3)
        if not top:
            return "Nothing tracked yet."
        return ", ".join(f"{n}({m}m)" for n, m in top)

    def get_session_duration(self) -> str:
        delta = datetime.now() - self._session_start
        h = int(delta.total_seconds() // 3600)
        m = int((delta.total_seconds() % 3600) // 60)
        return f"{h}h {m}m"

    def get_app_duration(self, app_name: str) -> float:
        """Minutes spent on a specific app today."""
        for key, mins in self._app_times.items():
            if app_name.lower() in key.lower():
                return mins
        return 0.0

    def is_gaming(self) -> bool:
        for app in self._app_times:
            for kw in GAME_KEYWORDS:
                if kw in app.lower():
                    return True
        return False

    def get_weekly_summary(self) -> str:
        from logs.logger import get_all_events
        events = get_all_events(days=7)
        lock_count = sum(1 for e in events if e.get("event") == "LOCK")
        panic_count = sum(1 for e in events if "PANIC" in e.get("event", ""))
        top = self.get_top_apps_today()
        lines = [
            f"Locks this week: {lock_count}",
            f"Panic alerts: {panic_count}",
            f"Top apps today: {', '.join(n for n, _ in top)}",
        ]
        return "\n".join(lines)
