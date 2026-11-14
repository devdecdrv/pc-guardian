"""
PC Guardian — Telegram Bot
Main bot runner with all command registrations
"""

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from bot.commands import Commands
from bot.auth import auth_required

logger = logging.getLogger("bot")


class GuardianBot:
    def __init__(self, cfg, lock_engine, camera, mic, speaker, activity, scheduler):
        self.cfg = cfg
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
        self._register_handlers(app)
        logger.info("Telegram bot started.")
        app.run_polling(drop_pending_updates=True)

    def _register_handlers(self, app):
        c = self.commands

        # Lock commands
        app.add_handler(CommandHandler("lock", c.cmd_lock))
        app.add_handler(CommandHandler("unlock", c.cmd_unlock))
        app.add_handler(CommandHandler("softlock", c.cmd_softlock))
        app.add_handler(CommandHandler("status", c.cmd_status))

        # Speaker commands
        app.add_handler(CommandHandler("speak", c.cmd_speak))
        app.add_handler(CommandHandler("alert", c.cmd_alert))
        app.add_handler(CommandHandler("msg", c.cmd_msg))
        app.add_handler(CommandHandler("volume", c.cmd_volume))
        app.add_handler(CommandHandler("music", c.cmd_music))

        # Camera commands
        app.add_handler(CommandHandler("cam", c.cmd_cam))

        # Mic commands
        app.add_handler(CommandHandler("listen", c.cmd_listen))

        # Monitor commands
        app.add_handler(CommandHandler("screen", c.cmd_screen))
        app.add_handler(CommandHandler("apps", c.cmd_apps))
        app.add_handler(CommandHandler("top", c.cmd_top))
        app.add_handler(CommandHandler("history", c.cmd_history))
        app.add_handler(CommandHandler("week", c.cmd_week))

        # Schedule commands
        app.add_handler(CommandHandler("schedule", c.cmd_schedule))
        app.add_handler(CommandHandler("homework", c.cmd_homework))
        app.add_handler(CommandHandler("break_time", c.cmd_break))
        app.add_handler(CommandHandler("reward", c.cmd_reward))

        # System commands
        app.add_handler(CommandHandler("shutdown", c.cmd_shutdown))
        app.add_handler(CommandHandler("restart", c.cmd_restart))
        app.add_handler(CommandHandler("kill", c.cmd_kill))

        # Settings
        app.add_handler(CommandHandler("lockword", c.cmd_lockword))
        app.add_handler(CommandHandler("password", c.cmd_password))
        app.add_handler(CommandHandler("settings", c.cmd_settings))
        app.add_handler(CommandHandler("help", c.cmd_help))

        # Voice message handler (plays on PC speakers)
        app.add_handler(MessageHandler(filters.VOICE, c.handle_voice_message))
