"""
PC Guardian — Commands (FIXED)
- Live stream passes chat_id to camera
- Speaker uses fixed system
- File manager commands
- AI command via Claude API
"""

import os
import logging
import tempfile
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from bot.auth import set_allowed_id
from logs.logger import log_event

logger = logging.getLogger("commands")


class Commands:
    def __init__(self, cfg, lock_engine, camera, mic, speaker, activity, scheduler):
        self.cfg      = cfg
        self.lock     = lock_engine
        self.camera   = camera
        self.mic      = mic
        self.speaker  = speaker
        self.activity = activity
        self.scheduler= scheduler
        set_allowed_id(cfg.allowed_user_id)

    def _auth(self, update: Update) -> bool:
        return update.effective_user.id == self.cfg.allowed_user_id

    # ── LOCK ──────────────────────────────────────────────────────────────────

    async def cmd_lock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        args = context.args
        duration = int(args[0]) if args and args[0].isdigit() else None
        self.lock.lock(duration_minutes=duration)
        msg = f"🔒 PC Locked{f' for {duration} minutes' if duration else ''}."
        await update.message.reply_text(msg)
        log_event("BOT_LOCK", msg)

    async def cmd_unlock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        self.lock.unlock()
        await update.message.reply_text("🔓 PC Unlocked.")

    async def cmd_softlock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        self.lock.soft_lock()
        await update.message.reply_text("🔐 Soft lock ON — games/YouTube blocked.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        st  = self.lock.status
        dur = self.activity.get_session_duration()
        top = self.activity.get_active_apps_summary()
        await update.message.reply_text(
            f"📊 *Status*\nLock: {'🔒 Locked' if st=='locked' else '🔓 Unlocked'}\n"
            f"Session: {dur}\nActive: {top}",
            parse_mode="Markdown"
        )

    # ── SPEAKER ───────────────────────────────────────────────────────────────

    async def cmd_speak(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        text = " ".join(context.args)
        if not text:
            await update.message.reply_text("Usage: /speak [message]")
            return
        self.speaker.speak(text)
        await update.message.reply_text(f"🔊 Playing: \"{text}\"")

    async def cmd_alert(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        mode = context.args[0] if context.args else "loud"
        self.speaker.play_alert(mode)
        await update.message.reply_text(f"🔔 Alert played.")

    async def cmd_msg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        name = self.cfg.child_name
        presets = {
            "calm":  f"Calm down {name}, take a breath. Dad is here.",
            "break": f"Time for a break {name}. Come eat something.",
            "bed":   f"Bedtime {name}. Shut down the PC now.",
            "good":  f"Good job today {name}. I am proud of you.",
            "study": f"{name}, time to study now. Games later.",
            "eat":   f"{name}, come have your food. PC will wait.",
        }
        key = context.args[0].lower() if context.args else ""
        msg = presets.get(key)
        if not msg:
            await update.message.reply_text(f"Presets: {', '.join(presets.keys())}")
            return
        self.speaker.speak(msg)
        await update.message.reply_text(f"🔊 Played: *{key}*", parse_mode="Markdown")

    async def cmd_volume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        arg = context.args[0] if context.args else ""
        if arg == "mute":
            self.speaker.mute()
            await update.message.reply_text("🔇 Muted.")
        elif arg == "unmute":
            self.speaker.unmute()
            await update.message.reply_text("🔊 Unmuted.")
        elif arg.isdigit():
            self.speaker.set_volume(int(arg))
            await update.message.reply_text(f"🔊 Volume: {arg}%")
        else:
            await update.message.reply_text("Usage: /volume [0-100 | mute | unmute]")

    async def cmd_music(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        arg = context.args[0] if context.args else ""
        if arg == "stop":
            self.speaker.stop_media()
            await update.message.reply_text("⏹ Media stopped.")
        elif arg == "pause":
            self.speaker.pause_media()
            await update.message.reply_text("⏸ Media paused.")

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        file = await context.bot.get_file(update.message.voice.file_id)
        path = os.path.join(tempfile.gettempdir(), "dad_voice.ogg")
        await file.download_to_drive(path)
        self.speaker.play_audio_file(path)
        await update.message.reply_text("🔊 Voice message played on PC.")

    # ── CAMERA ────────────────────────────────────────────────────────────────

    async def cmd_cam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        arg = context.args[0].lower() if context.args else "snapshot"
        chat_id = update.effective_chat.id

        if arg in ("snapshot", ""):
            await update.message.reply_text("📷 Capturing...")
            path = self.camera.capture_snapshot()
            if path:
                with open(path, "rb") as f:
                    await update.message.reply_photo(f, caption=f"📷 {datetime.now().strftime('%H:%M:%S')}")
            else:
                await update.message.reply_text("❌ Camera not available.")

        elif arg == "burst":
            await update.message.reply_text("📷 Taking 5 photos...")
            paths = self.camera.capture_burst(5, 2)
            for p in paths:
                with open(p, "rb") as f:
                    await update.message.reply_photo(f)

        elif arg == "live":
            await update.message.reply_text("📡 Live stream started (photo every 3s).\nSend /cam stop to end.")
            self.camera.start_stream(chat_id=chat_id, interval=3.0)

        elif arg == "stop":
            self.camera.stop_stream()
            await update.message.reply_text("📷 Stream stopped.")

    # ── MIC ───────────────────────────────────────────────────────────────────

    async def cmd_listen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        arg = context.args[0].lower() if context.args else "15"
        chat_id = update.effective_chat.id

        if arg == "stop":
            self.mic.stop_stream()
            await update.message.reply_text("🎤 Mic stopped.")
        elif arg == "live":
            await update.message.reply_text("🎤 Live mic stream started.")
            self.mic.start_live_stream(
                callback=lambda path: self._send_audio_sync(context, chat_id, path)
            )
        else:
            secs = int(arg) if arg.isdigit() else 15
            await update.message.reply_text(f"🎤 Recording {secs}s...")
            path = self.mic.record_clip(secs)
            if path:
                with open(path, "rb") as f:
                    await update.message.reply_voice(f, caption=f"🎤 {secs}s clip")
            else:
                await update.message.reply_text("❌ Mic not available.")

    def _send_audio_sync(self, context, chat_id, path):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._send_audio(context, chat_id, path))
        except Exception:
            pass

    async def _send_audio(self, context, chat_id, path):
        try:
            with open(path, "rb") as f:
                await context.bot.send_voice(chat_id=chat_id, voice=f)
        except Exception as e:
            logger.error(f"Audio send: {e}")

    # ── MONITOR ───────────────────────────────────────────────────────────────

    async def cmd_screen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        await update.message.reply_text("🖥 Capturing...")
        try:
            from PIL import ImageGrab
            img  = ImageGrab.grab()
            path = os.path.join(tempfile.gettempdir(), "pcg_screen.png")
            img.save(path)
            with open(path, "rb") as f:
                await update.message.reply_photo(f, caption=f"🖥 {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            await update.message.reply_text(f"❌ Screenshot failed: {e}")

    async def cmd_apps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        apps = self.activity.get_running_apps()
        lines = "\n".join(f"• {a}" for a in apps[:20])
        await update.message.reply_text(f"🖥 *Running:*\n{lines}", parse_mode="Markdown")

    async def cmd_top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        top = self.activity.get_top_apps_today()
        if not top:
            await update.message.reply_text("No data yet.")
            return
        lines = "\n".join(f"• {n}: {m}min" for n, m in top)
        await update.message.reply_text(f"📊 *Top Apps:*\n{lines}", parse_mode="Markdown")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        from logs.logger import get_today_events
        events = get_today_events()
        if not events:
            await update.message.reply_text("No events today.")
            return
        lines = [f"{e['timestamp'][-8:][:5]} — {e['event']}: {e.get('detail','')}" for e in events[-20:]]
        await update.message.reply_text("📋 *Log:*\n" + "\n".join(lines), parse_mode="Markdown")

    async def cmd_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        report = self.activity.get_weekly_summary()
        await update.message.reply_text(f"📆 *Weekly:*\n{report}", parse_mode="Markdown")

    # ── SCHEDULE ──────────────────────────────────────────────────────────────

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        await update.message.reply_text(
            f"⏰ *Schedule:*\n{self.scheduler.get_schedule_info()}",
            parse_mode="Markdown"
        )

    async def cmd_homework(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        arg = context.args[0].lower() if context.args else "on"
        if arg == "on":
            self.lock.soft_lock()
            await update.message.reply_text("📚 Homework mode ON.")
        else:
            self.lock.soft_unlock()
            await update.message.reply_text("📚 Homework mode OFF.")

    async def cmd_break(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        mins = int(context.args[0]) if context.args and context.args[0].isdigit() else 30
        self.lock.unlock()
        self.lock.lock(
            message=f"Break over {self.cfg.child_name}! Back to routine.",
            duration_minutes=mins
        )
        await update.message.reply_text(f"⏱ {mins} min break started. Auto-locks after.")

    async def cmd_reward(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        mins = int(context.args[0]) if context.args and context.args[0].isdigit() else 60
        self.lock.unlock()
        self.speaker.speak(f"Dad gave you {mins} minutes of free time {self.cfg.child_name}! Enjoy!")
        self.lock.lock(
            message=f"Reward time over {self.cfg.child_name}. Great job!",
            duration_minutes=mins
        )
        await update.message.reply_text(f"🎁 {mins} min reward granted!")

    # ── FILES ─────────────────────────────────────────────────────────────────

    async def cmd_ls(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        path = " ".join(context.args) if context.args else r"C:\Users"
        from core.file_manager import FileManager
        listing, err = FileManager(self.cfg).list_dir(path)
        if err:
            await update.message.reply_text(f"❌ {err}")
        else:
            await update.message.reply_text(f"📁 `{path}`\n{listing}", parse_mode="Markdown")

    async def cmd_readfile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        path = " ".join(context.args)
        if not path:
            await update.message.reply_text("Usage: /readfile [path]")
            return
        from core.file_manager import FileManager
        import io
        data, err = FileManager(self.cfg).read_file(path)
        if err:
            await update.message.reply_text(f"❌ {err}")
        else:
            await update.message.reply_document(
                document=io.BytesIO(data),
                filename=os.path.basename(path),
                caption=f"📄 {path}"
            )

    async def cmd_writefile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        path = " ".join(context.args)
        if not path:
            await update.message.reply_text("Reply to a file with /writefile [destination]")
            return
        msg = update.message.reply_to_message
        if msg and msg.document:
            file = await context.bot.get_file(msg.document.file_id)
            tmp  = tempfile.mktemp()
            await file.download_to_drive(tmp)
            with open(tmp, "rb") as f:
                content = f.read()
            from core.file_manager import FileManager
            ok, result = FileManager(self.cfg).write_file(path, content)
            await update.message.reply_text(f"{'✅' if ok else '❌'} {result}")
        else:
            await update.message.reply_text("Reply to a file with this command.")

    async def cmd_deletefile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        path = " ".join(context.args)
        if not path:
            await update.message.reply_text("Usage: /deletefile [path]")
            return
        from core.file_manager import FileManager
        ok, msg = FileManager(self.cfg).delete_file(path)
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

    async def cmd_findfile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        if not context.args:
            await update.message.reply_text("Usage: /findfile [pattern]  e.g. /findfile *.txt")
            return
        pattern = context.args[0]
        root    = context.args[1] if len(context.args) > 1 else r"C:\Users"
        from core.file_manager import FileManager
        results = FileManager(self.cfg).search_files(pattern, root)
        if not results:
            await update.message.reply_text(f"No files matching `{pattern}`.", parse_mode="Markdown")
        else:
            lines = "\n".join(f"• {r}" for r in results)
            await update.message.reply_text(f"🔍 *Found:*\n{lines}", parse_mode="Markdown")

    # ── AI ────────────────────────────────────────────────────────────────────

    async def cmd_ai(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /ai [question] — Ask Claude anything from Telegram.
        Responds in Telegram chat.
        """
        if not self._auth(update): return
        question = " ".join(context.args)
        if not question:
            await update.message.reply_text("Usage: /ai [your question]")
            return
        await update.message.reply_text("🤖 Thinking...")
        try:
            import urllib.request, json
            payload = json.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": question}]
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.cfg.get("anthropic_api_key", ""),
                    "anthropic-version": "2023-06-01"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data   = json.loads(resp.read())
                answer = data["content"][0]["text"]
            await update.message.reply_text(f"🤖 {answer}")
        except Exception as e:
            await update.message.reply_text(
                f"❌ AI unavailable. Add your Anthropic API key to config to enable this.\n`/ai` needs `anthropic_api_key` in settings.",
                parse_mode="Markdown"
            )

    # ── SYSTEM ────────────────────────────────────────────────────────────────

    async def cmd_shutdown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        await update.message.reply_text("⚠️ Shutting down in 10s...")
        import subprocess, time
        time.sleep(10)
        subprocess.run("shutdown /s /t 0", shell=True)

    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        await update.message.reply_text("🔄 Restarting in 10s...")
        import subprocess, time
        time.sleep(10)
        subprocess.run("shutdown /r /t 0", shell=True)

    async def cmd_kill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        name = " ".join(context.args)
        if not name:
            await update.message.reply_text("Usage: /kill [app name]")
            return
        import psutil
        killed = []
        for proc in psutil.process_iter(["name"]):
            try:
                if name.lower() in proc.info["name"].lower():
                    proc.kill()
                    killed.append(proc.info["name"])
            except Exception:
                pass
        await update.message.reply_text(
            f"💀 Killed: {', '.join(killed)}" if killed else f"❌ No process matching '{name}'."
        )

    # ── SETTINGS ─────────────────────────────────────────────────────────────

    async def cmd_lockword(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        if not context.args:
            await update.message.reply_text(f"Current keyword: `{self.cfg.lock_keyword}`", parse_mode="Markdown")
            return
        self.cfg.set("lock_keyword", context.args[0].lower())
        await update.message.reply_text(f"✅ Keyword changed to: `{context.args[0]}`", parse_mode="Markdown")

    async def cmd_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        if context.args and context.args[0] == "change" and len(context.args) > 1:
            self.cfg.set("uninstall_password", context.args[1])
            await update.message.reply_text("✅ Password updated.")
        else:
            await update.message.reply_text("Usage: /password change [newpassword]")

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        await update.message.reply_text(
            f"⚙️ *Settings*\n"
            f"Keyword: `{self.cfg.lock_keyword}`\n"
            f"Child: {self.cfg.child_name}\n"
            f"Report time: {self.cfg.daily_report_time}\n"
            f"Dashboard: localhost:{self.cfg.web_dashboard.get('port',8080)}",
            parse_mode="Markdown"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        await update.message.reply_text(
            "🛡 *PC GUARDIAN*\n\n"
            "*LOCK*\n/lock · /lock [min] · /unlock · /softlock · /status\n\n"
            "*SPEAK*\n/speak [text] · /alert · /msg [calm|break|bed|good|study|eat]\n"
            "/volume [0-100|mute|unmute] · Send voice note → plays on PC\n\n"
            "*CAMERA*\n/cam · /cam burst · /cam live · /cam stop\n\n"
            "*MIC*\n/listen [sec] · /listen live · /listen stop\n\n"
            "*MONITOR*\n/screen · /apps · /top · /history · /week\n\n"
            "*SCHEDULE*\n/schedule · /homework on|off · /break_time [min] · /reward [min]\n\n"
            "*FILES*\n/ls [path] · /readfile [path] · /writefile [path]\n"
            "/deletefile [path] · /findfile [pattern]\n\n"
            "*AI*\n/ai [question] — Ask Claude anything\n\n"
            "*SYSTEM*\n/shutdown · /restart · /kill [app]\n\n"
            "*SETTINGS*\n/lockword · /password change · /settings",
            parse_mode="Markdown"
        )


# ── LOCATION (appended) ───────────────────────────────────────────────────────

    async def cmd_location(self, update, context):
        if not self._auth(update): return
        await update.message.reply_text("📍 Getting location...")
        from monitor.location import LocationTracker
        tracker = LocationTracker(self.cfg)
        loc = tracker.get_location()
        msg = tracker.format_message(loc)
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_track(self, update, context):
        """Auto location tracking."""
        if not self._auth(update): return
        arg = context.args[0].lower() if context.args else "status"

        from monitor.location import LocationTracker
        from bot.alerts import send_alert

        if arg == "start":
            mins = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 30
            tracker = LocationTracker(self.cfg)
            tracker.start_auto_track(
                interval_minutes=mins,
                alert_fn=lambda msg: send_alert(msg)
            )
            await update.message.reply_text(f"📡 Location tracking every {mins} min.")
        elif arg == "stop":
            await update.message.reply_text("📍 Tracking stopped.")
        else:
            await update.message.reply_text(
                "Usage:\n/track start [minutes]\n/track stop"
            )

    # ── SCREEN STREAM (appended) ──────────────────────────────────────────────

    async def cmd_screenstream(self, update, context):
        if not self._auth(update): return
        arg = context.args[0].lower() if context.args else "start"
        chat_id = update.effective_chat.id

        from monitor.screen_stream import get_streamer
        streamer = get_streamer()

        if arg == "stop":
            streamer.stop()
            await update.message.reply_text("🖥 Screen stream stopped.")
            return

        # Parse interval and quality
        interval = 3.0
        quality  = 60

        if context.args:
            for a in context.args:
                if a.replace(".", "").isdigit():
                    interval = float(a)
                elif a.startswith("q"):
                    try: quality = int(a[1:])
                    except Exception: pass

        # Minimum 1s for fast mode
        if interval < 1.0:
            interval = 1.0
            await update.message.reply_text(
                "⚡ Fast mode: 1s interval. Send /screenstream stop to end."
            )
        else:
            await update.message.reply_text(
                f"🖥 Screen stream: every {interval}s. Send /screenstream stop to end."
            )

        streamer.start(chat_id=chat_id, interval=interval, quality=quality)
