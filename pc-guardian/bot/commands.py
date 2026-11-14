"""
PC Guardian — Command Handlers
Every Telegram command implemented here
"""

import os
import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from bot.auth import set_allowed_id
from logs.logger import log_event

logger = logging.getLogger("commands")


class Commands:
    def __init__(self, cfg, lock_engine, camera, mic, speaker, activity, scheduler):
        self.cfg = cfg
        self.lock = lock_engine
        self.camera = camera
        self.mic = mic
        self.speaker = speaker
        self.activity = activity
        self.scheduler = scheduler
        set_allowed_id(cfg.allowed_user_id)

    def _authorized(self, update: Update) -> bool:
        return update.effective_user.id == self.cfg.allowed_user_id

    # ─── LOCK ─────────────────────────────────────────────────────────────────

    async def cmd_lock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        args = context.args
        duration = int(args[0]) if args and args[0].isdigit() else None
        msg = f"🔒 PC Locked{f' for {duration} minutes' if duration else ''}."
        self.lock.lock(duration_minutes=duration)
        await update.message.reply_text(msg)
        log_event("BOT_LOCK", f"Locked via Telegram. Duration: {duration}")

    async def cmd_unlock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        self.lock.unlock()
        await update.message.reply_text("🔓 PC Unlocked.")
        log_event("BOT_UNLOCK", "Unlocked via Telegram.")

    async def cmd_softlock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        self.lock.soft_lock()
        await update.message.reply_text("🔐 Soft lock enabled — games/YouTube blocked.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        status = self.lock.status
        active_apps = self.activity.get_active_apps_summary()
        uptime = self.activity.get_session_duration()
        msg = (
            f"📊 *PC Status*\n"
            f"Lock: {'🔒 Locked' if status == 'locked' else '🔓 Unlocked'}\n"
            f"Session: {uptime}\n"
            f"Active: {active_apps}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    # ─── SPEAKER ──────────────────────────────────────────────────────────────

    async def cmd_speak(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        text = " ".join(context.args)
        if not text:
            await update.message.reply_text("Usage: /speak [message]")
            return
        self.speaker.speak(text)
        await update.message.reply_text(f"🔊 Playing: \"{text}\"")
        log_event("SPEAK", text)

    async def cmd_alert(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        mode = context.args[0] if context.args else "loud"
        self.speaker.play_alert(mode)
        await update.message.reply_text(f"🔔 Alert played ({mode}).")

    async def cmd_msg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        presets = {
            "calm": f"Calm down {self.cfg.child_name}, take a breath. Dad is here.",
            "break": f"Time for a break {self.cfg.child_name}. Come eat something.",
            "bed": f"Bedtime {self.cfg.child_name}. Shut down the PC now.",
            "good": f"Good job today {self.cfg.child_name}. I am proud of you.",
            "study": f"{self.cfg.child_name}, time to study now. Games later.",
            "eat": f"{self.cfg.child_name}, come have your food. PC will wait.",
        }
        key = context.args[0].lower() if context.args else ""
        msg = presets.get(key)
        if not msg:
            keys = ", ".join(presets.keys())
            await update.message.reply_text(f"Available presets: {keys}")
            return
        self.speaker.speak(msg)
        await update.message.reply_text(f"🔊 Played preset: *{key}*", parse_mode="Markdown")

    async def cmd_volume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        arg = context.args[0] if context.args else ""
        if arg == "mute":
            self.speaker.mute()
            await update.message.reply_text("🔇 Muted.")
        elif arg == "unmute":
            self.speaker.unmute()
            await update.message.reply_text("🔊 Unmuted.")
        elif arg.isdigit():
            self.speaker.set_volume(int(arg))
            await update.message.reply_text(f"🔊 Volume set to {arg}%.")
        else:
            await update.message.reply_text("Usage: /volume [0-100 | mute | unmute]")

    async def cmd_music(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        arg = context.args[0] if context.args else ""
        if arg == "stop":
            self.speaker.stop_media()
            await update.message.reply_text("⏹ Media stopped.")
        elif arg == "pause":
            self.speaker.pause_media()
            await update.message.reply_text("⏸ Media paused.")

    # ─── CAMERA ───────────────────────────────────────────────────────────────

    async def cmd_cam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        arg = context.args[0].lower() if context.args else "snapshot"

        if arg == "snapshot" or arg == "":
            await update.message.reply_text("📷 Capturing...")
            path = self.camera.capture_snapshot()
            if path:
                with open(path, "rb") as f:
                    await update.message.reply_photo(f, caption=f"📷 {datetime.now().strftime('%H:%M:%S')}")
            else:
                await update.message.reply_text("❌ Camera not available.")

        elif arg == "burst":
            await update.message.reply_text("📷 Capturing 5 photos...")
            paths = self.camera.capture_burst(count=5, interval=2)
            for path in paths:
                with open(path, "rb") as f:
                    await update.message.reply_photo(f)

        elif arg == "live":
            await update.message.reply_text("📡 Starting live stream (photo every 3s). Send /cam stop to end.")
            self.camera.start_stream(
                callback=lambda path: asyncio.create_task(
                    self._send_photo(update, path)
                )
            )

        elif arg == "stop":
            self.camera.stop_stream()
            await update.message.reply_text("📷 Stream stopped.")

    async def _send_photo(self, update: Update, path: str):
        try:
            with open(path, "rb") as f:
                await update.message.reply_photo(f)
        except Exception as e:
            logger.error(f"Photo send failed: {e}")

    # ─── MICROPHONE ───────────────────────────────────────────────────────────

    async def cmd_listen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        arg = context.args[0].lower() if context.args else "15"

        if arg == "live":
            await update.message.reply_text("🎤 Live mic stream started. Send /listen stop to end.")
            self.mic.start_live_stream(
                callback=lambda path: asyncio.create_task(
                    self._send_audio(update, path)
                )
            )
        elif arg == "stop":
            self.mic.stop_stream()
            await update.message.reply_text("🎤 Mic stopped.")
        else:
            seconds = int(arg) if arg.isdigit() else 15
            await update.message.reply_text(f"🎤 Recording {seconds}s...")
            path = self.mic.record_clip(seconds)
            if path:
                with open(path, "rb") as f:
                    await update.message.reply_voice(f, caption=f"🎤 {seconds}s recording")
            else:
                await update.message.reply_text("❌ Mic not available.")

    async def _send_audio(self, update: Update, path: str):
        try:
            with open(path, "rb") as f:
                await update.message.reply_voice(f)
        except Exception as e:
            logger.error(f"Audio send failed: {e}")

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Voice message from dad → plays on PC speakers."""
        if not self._authorized(update): return
        file = await context.bot.get_file(update.message.voice.file_id)
        path = "/tmp/dad_voice.ogg"
        await file.download_to_drive(path)
        self.speaker.play_audio_file(path)
        await update.message.reply_text("🔊 Voice message played on PC.")
        log_event("VOICE_MSG", "Dad's voice played on PC.")

    # ─── MONITOR ──────────────────────────────────────────────────────────────

    async def cmd_screen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        from PIL import ImageGrab
        import tempfile
        await update.message.reply_text("🖥 Capturing screen...")
        try:
            img = ImageGrab.grab()
            path = tempfile.mktemp(suffix=".png")
            img.save(path)
            with open(path, "rb") as f:
                await update.message.reply_photo(f, caption=f"🖥 Screen @ {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            await update.message.reply_text(f"❌ Screenshot failed: {e}")

    async def cmd_apps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        apps = self.activity.get_running_apps()
        if not apps:
            await update.message.reply_text("No apps detected.")
            return
        lines = "\n".join(f"• {a}" for a in apps[:20])
        await update.message.reply_text(f"🖥 *Running Apps:*\n{lines}", parse_mode="Markdown")

    async def cmd_top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        top = self.activity.get_top_apps_today()
        if not top:
            await update.message.reply_text("No data yet today.")
            return
        lines = "\n".join(f"• {name}: {mins}min" for name, mins in top)
        await update.message.reply_text(f"📊 *Today's Top Apps:*\n{lines}", parse_mode="Markdown")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        from logs.logger import get_today_events
        events = get_today_events()
        if not events:
            await update.message.reply_text("No events today.")
            return
        lines = []
        for e in events[-20:]:
            t = e.get("timestamp", "")[-8:][:5]
            lines.append(f"{t} — {e.get('event')}: {e.get('detail', '')}")
        await update.message.reply_text(
            f"📋 *Today's Log:*\n" + "\n".join(lines),
            parse_mode="Markdown"
        )

    async def cmd_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        report = self.activity.get_weekly_summary()
        await update.message.reply_text(f"📆 *Weekly Summary:*\n{report}", parse_mode="Markdown")

    # ─── SCHEDULE ─────────────────────────────────────────────────────────────

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        info = self.scheduler.get_schedule_info()
        await update.message.reply_text(f"⏰ *Schedule:*\n{info}", parse_mode="Markdown")

    async def cmd_homework(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        arg = context.args[0].lower() if context.args else "on"
        if arg == "on":
            self.lock.soft_lock()
            await update.message.reply_text("📚 Homework mode ON — games/YouTube blocked.")
            log_event("HOMEWORK", "Homework mode enabled.")
        else:
            self.lock.soft_unlock()
            await update.message.reply_text("📚 Homework mode OFF.")

    async def cmd_break(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        minutes = int(context.args[0]) if context.args and context.args[0].isdigit() else 30
        self.lock.unlock()
        self.lock.lock(
            message=f"Break time is over {self.cfg.child_name}! Back to your routine.",
            duration_minutes=minutes
        )
        await update.message.reply_text(f"⏱ Break started — {minutes} minutes free time. Auto-locks after.")
        log_event("BREAK", f"{minutes} min break granted.")

    async def cmd_reward(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        minutes = int(context.args[0]) if context.args and context.args[0].isdigit() else 60
        self.lock.unlock()
        self.speaker.speak(f"Dad gave you {minutes} minutes of free time {self.cfg.child_name}! Enjoy!")
        self.lock.lock(
            message=f"Reward time over {self.cfg.child_name}. Great job today!",
            duration_minutes=minutes
        )
        await update.message.reply_text(f"🎁 Reward: {minutes} min free time granted + voice message played!")
        log_event("REWARD", f"{minutes} min reward granted.")

    # ─── SYSTEM ───────────────────────────────────────────────────────────────

    async def cmd_shutdown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        await update.message.reply_text("⚠️ Shutting down PC in 10 seconds...")
        import subprocess, time
        time.sleep(10)
        subprocess.run("shutdown /s /t 0", shell=True)

    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        await update.message.reply_text("🔄 Restarting PC in 10 seconds...")
        import subprocess, time
        time.sleep(10)
        subprocess.run("shutdown /r /t 0", shell=True)

    async def cmd_kill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        app_name = " ".join(context.args)
        if not app_name:
            await update.message.reply_text("Usage: /kill [app name]")
            return
        import psutil
        killed = []
        for proc in psutil.process_iter(["name"]):
            try:
                if app_name.lower() in proc.info["name"].lower():
                    proc.kill()
                    killed.append(proc.info["name"])
            except Exception:
                pass
        if killed:
            await update.message.reply_text(f"💀 Killed: {', '.join(killed)}")
        else:
            await update.message.reply_text(f"❌ No process found matching '{app_name}'.")

    # ─── SETTINGS ─────────────────────────────────────────────────────────────

    async def cmd_lockword(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        if not context.args:
            await update.message.reply_text(f"Current keyword: `{self.cfg.lock_keyword}`", parse_mode="Markdown")
            return
        word = context.args[0].lower()
        self.cfg.set("lock_keyword", word)
        await update.message.reply_text(f"✅ Lock keyword changed to: `{word}`", parse_mode="Markdown")

    async def cmd_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        if context.args and context.args[0] == "change":
            new_pass = context.args[1] if len(context.args) > 1 else None
            if not new_pass:
                await update.message.reply_text("Usage: /password change [newpassword]")
                return
            self.cfg.set("uninstall_password", new_pass)
            await update.message.reply_text("✅ Password updated.")

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        s = (
            f"⚙️ *Settings*\n"
            f"Lock keyword: `{self.cfg.lock_keyword}`\n"
            f"Child name: {self.cfg.child_name}\n"
            f"Daily report: {self.cfg.daily_report_time}\n"
            f"Panic detection: {'ON' if self.cfg.panic_detection.get('voice_enabled') else 'OFF'}\n"
            f"Dashboard port: {self.cfg.web_dashboard.get('port', 8080)}"
        )
        await update.message.reply_text(s, parse_mode="Markdown")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update): return
        help_text = (
            "🛡 *PC GUARDIAN COMMANDS*\n\n"
            "*LOCK*\n"
            "/lock — Lock PC\n"
            "/lock [min] — Lock for N minutes\n"
            "/unlock — Unlock PC\n"
            "/softlock — Block games/YouTube only\n"
            "/status — PC status\n\n"
            "*SPEAK*\n"
            "/speak [text] — Say message on PC\n"
            "/alert — Attention chime\n"
            "/msg [calm|break|bed|good|study|eat]\n"
            "/volume [0-100|mute|unmute]\n"
            "/music [stop|pause]\n\n"
            "*CAMERA*\n"
            "/cam — Quick snapshot\n"
            "/cam burst — 5 photos\n"
            "/cam live — Stream\n"
            "/cam stop — Stop stream\n\n"
            "*MIC*\n"
            "/listen [seconds] — Record clip\n"
            "/listen live — Live stream\n"
            "/listen stop — Stop\n\n"
            "*MONITOR*\n"
            "/screen — Screenshot\n"
            "/apps — Running apps\n"
            "/top — Top apps today\n"
            "/history — Today's log\n"
            "/week — Weekly report\n\n"
            "*SCHEDULE*\n"
            "/schedule — View schedule\n"
            "/homework [on|off]\n"
            "/break_time [minutes]\n"
            "/reward [minutes]\n\n"
            "*SYSTEM*\n"
            "/shutdown — Shut down PC\n"
            "/restart — Restart PC\n"
            "/kill [app] — Force close app\n\n"
            "*SETTINGS*\n"
            "/lockword [word]\n"
            "/password change [new]\n"
            "/settings — View all\n"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")


# ─── FILE MANAGER (appended) ──────────────────────────────────────────────────

    async def cmd_ls(self, update, context):
        if not self._authorized(update): return
        path = " ".join(context.args) if context.args else "C:\\Users"
        from core.file_manager import FileManager
        fm = FileManager(self.cfg)
        listing, err = fm.list_dir(path)
        if err:
            await update.message.reply_text(f"❌ {err}")
        else:
            await update.message.reply_text(f"📁 `{path}`\n{listing}", parse_mode="Markdown")

    async def cmd_readfile(self, update, context):
        if not self._authorized(update): return
        path = " ".join(context.args)
        if not path:
            await update.message.reply_text("Usage: /readfile [path]")
            return
        from core.file_manager import FileManager
        fm = FileManager(self.cfg)
        data, err = fm.read_file(path)
        if err:
            await update.message.reply_text(f"❌ {err}")
            return
        # Send as document
        import io
        filename = os.path.basename(path)
        await update.message.reply_document(
            document=io.BytesIO(data),
            filename=filename,
            caption=f"📄 {path}"
        )

    async def cmd_writefile(self, update, context):
        """Write an uploaded file to a PC path: /writefile C:\\path\\file.txt"""
        if not self._authorized(update): return
        path = " ".join(context.args)
        if not path:
            await update.message.reply_text("Send a file and reply to it with /writefile [destination_path]")
            return
        # Check if replying to a document
        if update.message.reply_to_message and update.message.reply_to_message.document:
            doc = update.message.reply_to_message.document
            file = await context.bot.get_file(doc.file_id)
            import tempfile as tf
            tmp = tf.mktemp()
            await file.download_to_drive(tmp)
            with open(tmp, "rb") as f:
                content = f.read()
            from core.file_manager import FileManager
            fm = FileManager(self.cfg)
            ok, msg = fm.write_file(path, content)
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
        else:
            await update.message.reply_text("Reply to a file with this command.")

    async def cmd_deletefile(self, update, context):
        if not self._authorized(update): return
        path = " ".join(context.args)
        if not path:
            await update.message.reply_text("Usage: /deletefile [path]")
            return
        from core.file_manager import FileManager
        fm = FileManager(self.cfg)
        ok, msg = fm.delete_file(path)
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

    async def cmd_findfile(self, update, context):
        if not self._authorized(update): return
        if not context.args:
            await update.message.reply_text("Usage: /findfile [pattern] e.g. /findfile *.txt")
            return
        pattern = context.args[0]
        root = context.args[1] if len(context.args) > 1 else "C:\\Users"
        from core.file_manager import FileManager
        fm = FileManager(self.cfg)
        results = fm.search_files(pattern, root)
        if not results:
            await update.message.reply_text(f"No files matching `{pattern}` found.", parse_mode="Markdown")
        else:
            lines = "\n".join(f"• {r}" for r in results)
            await update.message.reply_text(f"🔍 *Found:*\n{lines}", parse_mode="Markdown")
