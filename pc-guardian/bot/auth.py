"""
PC Guardian — Auth
Ensures only the authorized user can control the bot
"""

import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger("auth")

_allowed_id = None


def set_allowed_id(user_id: int):
    global _allowed_id
    _allowed_id = user_id


def auth_required(func):
    @wraps(func)
    async def wrapper(self_or_update, update_or_ctx=None, context=None):
        # Handle both method and function forms
        if isinstance(self_or_update, Update):
            update = self_or_update
            ctx = update_or_ctx
        else:
            update = update_or_ctx
            ctx = context

        if update and update.effective_user:
            uid = update.effective_user.id
            if _allowed_id and uid != _allowed_id:
                logger.warning(f"Unauthorized access attempt from user ID: {uid}")
                await update.message.reply_text("⛔ Unauthorized.")
                return

        if isinstance(self_or_update, Update):
            return await func(self_or_update, update_or_ctx)
        else:
            return await func(self_or_update, update_or_ctx, context)

    return wrapper
