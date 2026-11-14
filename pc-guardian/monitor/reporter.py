"""
PC Guardian — Reporter
Sends daily and weekly summaries to Telegram automatically
"""

import time
import logging
from datetime import datetime
from logs.logger import get_today_events, get_all_events
from bot.alerts import send_alert

logger = logging.getLogger("reporter")


class Reporter:
    def __init__(self, cfg, activity):
        self.cfg = cfg
        self.activity = activity
        self._last_report_day = None

    def start(self):
        logger.info("Reporter started.")
        while True:
            self._check_daily_report()
            time.sleep(60)  # check every minute

    def _check_daily_report(self):
        now = datetime.now()
        report_time = self.cfg.daily_report_time  # e.g. "21:00"
        h, m = map(int, report_time.split(":"))

        if now.hour == h and now.minute == m:
            today = now.date()
            if self._last_report_day != today:
                self._last_report_day = today
                self._send_daily_report()

    def _send_daily_report(self):
        events = get_today_events()
        lock_count = sum(1 for e in events if e.get("event") in ("LOCK", "BOT_LOCK", "KEYWORD_LOCK"))
        unlock_count = sum(1 for e in events if e.get("event") in ("UNLOCK", "BOT_UNLOCK"))
        panic_count = sum(1 for e in events if "PANIC" in e.get("event", ""))
        tamper_count = sum(1 for e in events if "TAMPER" in e.get("event", ""))
        top = self.activity.get_top_apps_today()
        top_str = "\n".join(f"  • {n}: {m}min" for n, m in top) or "  No data"

        msg = (
            f"📊 *Daily Report — {datetime.now().strftime('%d %b %Y')}*\n\n"
            f"🔒 Locks today: {lock_count}\n"
            f"🔓 Unlocks today: {unlock_count}\n"
            f"🚨 Panic alerts: {panic_count}\n"
            f"🛡 Tamper attempts: {tamper_count}\n\n"
            f"📱 *Top Apps:*\n{top_str}\n\n"
            f"Session time: {self.activity.get_session_duration()}"
        )

        send_alert(msg)
        logger.info("Daily report sent.")
