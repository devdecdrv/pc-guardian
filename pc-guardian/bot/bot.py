"""
PC Guardian — Telegram Bot (FIXED)
- Live stream loop injection fixed
- File manager commands registered
- Startup install on first run
"""

import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from bot.commands import Commands
from bot.auth import set_allowed_id

logger = logging.getLogger("bot")


class GuardianBot:
    def __init__(self, cfg, lock_engine, camera, mic, speaker, activity, scheduler):
        self.cfg = cfg
        self.camera = camera
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
        app = Application.builder().token(self.cfg.bot_token).build()

        # Pass bot's event loop to camera for live stream
        loop = asyncio.get_event_loop()
        self.camera.set_event_loop(loop)

        self._register(app)

        # Initialize alerts system
        from bot.alerts import init_alerts
        init_alerts(self.cfg.bot_token, self.cfg.allowed_user_id)

        logger.info("Telegram bot started.")
        app.run_polling(drop_pending_updates=True)

    def _register(self, app):
        c = self.commands

        # Lock
        app.add_handler(CommandHandler("lock",       c.cmd_lock))
        app.add_handler(CommandHandler("unlock",     c.cmd_unlock))
        app.add_handler(CommandHandler("softlock",   c.cmd_softlock))
        app.add_handler(CommandHandler("status",     c.cmd_status))

        # Speaker
        app.add_handler(CommandHandler("speak",      c.cmd_speak))
        app.add_handler(CommandHandler("alert",      c.cmd_alert))
        app.add_handler(CommandHandler("msg",        c.cmd_msg))
        app.add_handler(CommandHandler("volume",     c.cmd_volume))
        app.add_handler(CommandHandler("music",      c.cmd_music))

        # Camera
        app.add_handler(CommandHandler("cam",        c.cmd_cam))

        # Mic
        app.add_handler(CommandHandler("listen",     c.cmd_listen))

        # Monitor
        app.add_handler(CommandHandler("screen",     c.cmd_screen))
        app.add_handler(CommandHandler("apps",       c.cmd_apps))
        app.add_handler(CommandHandler("top",        c.cmd_top))
        app.add_handler(CommandHandler("history",    c.cmd_history))
        app.add_handler(CommandHandler("week",       c.cmd_week))

        # Schedule
        app.add_handler(CommandHandler("schedule",   c.cmd_schedule))
        app.add_handler(CommandHandler("homework",   c.cmd_homework))
        app.add_handler(CommandHandler("break_time", c.cmd_break))
        app.add_handler(CommandHandler("reward",     c.cmd_reward))

        # System
        app.add_handler(CommandHandler("shutdown",   c.cmd_shutdown))
        app.add_handler(CommandHandler("restart",    c.cmd_restart))
        app.add_handler(CommandHandler("kill",       c.cmd_kill))

        # Files
        app.add_handler(CommandHandler("ls",         c.cmd_ls))
        app.add_handler(CommandHandler("readfile",   c.cmd_readfile))
        app.add_handler(CommandHandler("writefile",  c.cmd_writefile))
        app.add_handler(CommandHandler("deletefile", c.cmd_deletefile))
        app.add_handler(CommandHandler("findfile",   c.cmd_findfile))

        # Settings
        app.add_handler(CommandHandler("lockword",   c.cmd_lockword))
        app.add_handler(CommandHandler("password",   c.cmd_password))
        app.add_handler(CommandHandler("settings",   c.cmd_settings))
        app.add_handler(CommandHandler("help",       c.cmd_help))

        # Voice message → plays on PC
        app.add_handler(MessageHandler(filters.VOICE, c.handle_voice_message))
