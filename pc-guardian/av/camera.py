"""
PC Guardian — Camera System (FIXED)
set_bot method added. Live stream works via direct bot send.
"""

import cv2
import os
import time
import threading
import logging
import tempfile
import asyncio

logger = logging.getLogger("camera")

SNAP_DIR = os.path.join(tempfile.gettempdir(), "pcguardian_cam")
os.makedirs(SNAP_DIR, exist_ok=True)


class CameraSystem:
    def __init__(self, cfg):
        self.cfg        = cfg
        self._streaming = False
        self._bot       = None
        self._loop      = None

    def set_bot(self, bot, loop):
        """Called by GuardianBot after app starts."""
        self._bot  = bot
        self._loop = loop

    # kept for backwards compat
    def set_bot_app(self, app):
        try:
            self._bot  = app.bot
            self._loop = asyncio.get_event_loop()
        except Exception:
            pass

    def _open(self):
        for idx in range(3):
            for backend in [cv2.CAP_DSHOW, cv2.CAP_ANY]:
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    for _ in range(3):
                        cap.read()
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return cap
                cap.release()
        return None

    def capture_snapshot(self) -> str:
        cap = self._open()
        if not cap:
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return None
        path = os.path.join(SNAP_DIR, f"snap_{int(time.time())}.jpg")
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return path

    def capture_burst(self, count=5, interval=2.0) -> list:
        cap = self._open()
        if not cap:
            return []
        paths = []
        for i in range(count):
            ret, frame = cap.read()
            if ret and frame is not None:
                p = os.path.join(SNAP_DIR, f"burst_{int(time.time())}_{i}.jpg")
                cv2.imwrite(p, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                paths.append(p)
            time.sleep(interval)
        cap.release()
        return paths

    def start_stream(self, chat_id: int, interval: float = 3.0):
        self._streaming = True

        def _run():
            cap = self._open()
            if not cap:
                logger.error("Stream: no camera.")
                return
            while self._streaming:
                ret, frame = cap.read()
                if ret and frame is not None:
                    path = os.path.join(SNAP_DIR, f"stream_{int(time.time())}.jpg")
                    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    self._send_photo(chat_id, path)
                time.sleep(interval)
            cap.release()

        threading.Thread(target=_run, daemon=True, name="CamStream").start()

    def _send_photo(self, chat_id: int, path: str):
        if not self._bot or not self._loop or not self._loop.is_running():
            return
        try:
            async def _do():
                try:
                    with open(path, "rb") as f:
                        await self._bot.send_photo(chat_id=chat_id, photo=f)
                    try: os.remove(path)
                    except: pass
                except Exception as e:
                    logger.error(f"Cam send: {e}")
            asyncio.run_coroutine_threadsafe(_do(), self._loop)
        except Exception as e:
            logger.error(f"Cam schedule: {e}")

    def stop_stream(self):
        self._streaming = False

    def capture_panic_snapshot(self) -> str:
        return self.capture_snapshot()
