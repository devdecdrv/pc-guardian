"""
PC Guardian — Bot (FIXED)
Properly wires screen streamer bot reference and event loop.
"""

import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from bot.commands import Commands
from bot.auth import set_allowed_id

logger = logging.getLogger("bot")


class GuardianBot:
    def __init__(self, cfg, lock_engine, camera, mic, speaker, activity, scheduler):
        self.cfg      = cfg
        self.camera   = camera
        self.mic      = mic
        self.commands = Commands(
            cfg=cfg,
            lock_engine=lock_engine,
            camera=camera,
            mic=mic,
            speaker=speaker,
            activity=activity,
            scheduler=scheduler,
        )

    def run(self):
        app  = Application.builder().token(self.cfg.bot_token).build()
        loop = asyncio.get_event_loop()

        # Wire camera
        self.camera.set_bot(app.bot, loop)

        # Wire screen streamer
        try:
            from monitor.screen_stream import get_streamer
            get_streamer().set_bot(app.bot, loop)
        except Exception as e:
            logger.warning(f"Screen streamer wire: {e}")

        self._register(app)

        from bot.alerts import init_alerts
        init_alerts(self.cfg.bot_token, self.cfg.allowed_user_id)

        logger.info("Bot started.")
        app.run_polling(drop_pending_updates=True)

    def _register(self, app):
        c = self.commands

        # Lock
        app.add_handler(CommandHandler("lock",         c.cmd_lock))
        app.add_handler(CommandHandler("unlock",       c.cmd_unlock))
        app.add_handler(CommandHandler("softlock",     c.cmd_softlock))
        app.add_handler(CommandHandler("status",       c.cmd_status))

        # Speaker
        app.add_handler(CommandHandler("speak",        c.cmd_speak))
        app.add_handler(CommandHandler("alert",        c.cmd_alert))
        app.add_handler(CommandHandler("msg",          c.cmd_msg))
        app.add_handler(CommandHandler("volume",       c.cmd_volume))
        app.add_handler(CommandHandler("music",        c.cmd_music))

        # Camera
        app.add_handler(CommandHandler("cam",          c.cmd_cam))

        # Mic
        app.add_handler(CommandHandler("listen",       c.cmd_listen))

        # Screen stream
        app.add_handler(CommandHandler("screenstream", c.cmd_screenstream))

        # Monitor
        app.add_handler(CommandHandler("screen",       c.cmd_screen))
        app.add_handler(CommandHandler("apps",         c.cmd_apps))
        app.add_handler(CommandHandler("top",          c.cmd_top))
        app.add_handler(CommandHandler("history",      c.cmd_history))
        app.add_handler(CommandHandler("week",         c.cmd_week))

        # Location
        app.add_handler(CommandHandler("location",     c.cmd_location))
        app.add_handler(CommandHandler("track",        c.cmd_track))

        # Schedule
        app.add_handler(CommandHandler("schedule",     c.cmd_schedule))
        app.add_handler(CommandHandler("homework",     c.cmd_homework))
        app.add_handler(CommandHandler("break_time",   c.cmd_break))
        app.add_handler(CommandHandler("reward",       c.cmd_reward))

        # Files
        app.add_handler(CommandHandler("ls",           c.cmd_ls))
        app.add_handler(CommandHandler("readfile",     c.cmd_readfile))
        app.add_handler(CommandHandler("writefile",    c.cmd_writefile))
        app.add_handler(CommandHandler("deletefile",   c.cmd_deletefile))
        app.add_handler(CommandHandler("findfile",     c.cmd_findfile))

        # AI
        app.add_handler(CommandHandler("ai",           c.cmd_ai))

        # System
        app.add_handler(CommandHandler("shutdown",     c.cmd_shutdown))
        app.add_handler(CommandHandler("restart",      c.cmd_restart))
        app.add_handler(CommandHandler("kill",         c.cmd_kill))

        # Settings
        app.add_handler(CommandHandler("lockword",     c.cmd_lockword))
        app.add_handler(CommandHandler("password",     c.cmd_password))
        app.add_handler(CommandHandler("settings",     c.cmd_settings))
        app.add_handler(CommandHandler("help",         c.cmd_help))

        # Voice message → plays on PC
        app.add_handler(MessageHandler(filters.VOICE,  c.handle_voice_message))
