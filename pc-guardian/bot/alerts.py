"""
PC Guardian — Alert Sender
Sends automatic alerts to Telegram when events are detected
"""

import asyncio
import logging
import threading
from telegram import Bot

logger = logging.getLogger("alerts")

_bot_instance: Bot = None
_user_id: int = None
_loop = None


def init_alerts(token: str, user_id: int):
    global _bot_instance, _user_id, _loop
    _bot_instance = Bot(token=token)
    _user_id = user_id
    _loop = asyncio.new_event_loop()
    t = threading.Thread(target=_loop.run_forever, daemon=True)
    t.start()


def send_alert(message: str, photo_path: str = None, audio_path: str = None):
    if not _bot_instance or not _user_id:
        logger.warning("Alerts not initialized.")
        return

    async def _send():
        try:
            if photo_path:
                with open(photo_path, "rb") as f:
                    await _bot_instance.send_photo(
                        chat_id=_user_id,
                        photo=f,
                        caption=message
                    )
            elif audio_path:
                with open(audio_path, "rb") as f:
                    await _bot_instance.send_voice(
                        chat_id=_user_id,
                        voice=f,
                        caption=message
                    )
            else:
                await _bot_instance.send_message(
                    chat_id=_user_id,
                    text=message,
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Alert send failed: {e}")

    asyncio.run_coroutine_threadsafe(_send(), _loop)
