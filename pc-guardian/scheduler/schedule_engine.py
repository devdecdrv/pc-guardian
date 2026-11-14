"""
PC Guardian — Schedule Engine
Auto-lock/unlock at set times, school mode, weekend mode
"""

import time
import logging
from datetime import datetime
from logs.logger import log_event

logger = logging.getLogger("scheduler")


class ScheduleEngine:
    def __init__(self, cfg, lock_engine):
        self.cfg = cfg
        self.lock = lock_engine
        self._last_tick = {}

    def start(self):
        logger.info("Schedule engine started.")
        while True:
            self._tick()
            time.sleep(30)  # check every 30 seconds

    def _tick(self):
        now = datetime.now()
        weekday = now.weekday()  # 0=Mon, 6=Sun
        is_weekend = weekday >= 5
        time_str = now.strftime("%H:%M")

        # School schedule (weekdays only)
        school = self.cfg.school_schedule
        if school.get("enabled") and not is_weekend:
            lock_t = school.get("lock_time", "08:00")
            unlock_t = school.get("unlock_time", "15:00")
            self._check_trigger("school_lock", time_str, lock_t, self._do_lock, "School hours — PC locked.")
            self._check_trigger("school_unlock", time_str, unlock_t, self.lock.unlock)

        # Bedtime schedule (every day)
        bedtime = self.cfg.bedtime_schedule
        if bedtime.get("enabled"):
            lock_t = bedtime.get("lock_time", "21:00")
            unlock_t = bedtime.get("unlock_time", "16:00")
            self._check_trigger("bed_lock", time_str, lock_t, self._do_lock, "Bedtime! PC locked.")
            self._check_trigger("bed_unlock", time_str, unlock_t, self.lock.unlock)

    def _check_trigger(self, key: str, current: str, target: str, fn, msg: str = None):
        if current == target:
            today = datetime.now().date().isoformat()
            tick_key = f"{key}_{today}"
            if tick_key not in self._last_tick:
                self._last_tick[tick_key] = True
                logger.info(f"Schedule trigger: {key}")
                log_event("SCHEDULE", key)
                if msg:
                    fn(message=msg) if msg else fn()
                else:
                    fn()

    def _do_lock(self, message: str = None):
        self.lock.lock(message=message or self.cfg.lock_message)

    def get_schedule_info(self) -> str:
        lines = []
        school = self.cfg.school_schedule
        if school.get("enabled"):
            lines.append(f"School (weekdays): Lock {school.get('lock_time')} → Unlock {school.get('unlock_time')}")
        else:
            lines.append("School schedule: OFF")

        bedtime = self.cfg.bedtime_schedule
        if bedtime.get("enabled"):
            lines.append(f"Bedtime (daily): Lock {bedtime.get('lock_time')} → Unlock {bedtime.get('unlock_time')}")
        else:
            lines.append("Bedtime schedule: OFF")

        return "\n".join(lines) if lines else "No schedules set."
