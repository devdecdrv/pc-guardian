"""
PC Guardian — Camera (FIXED)
Live stream using polling loop + direct async scheduling
"""

import cv2
import os
import time
import threading
import logging
import tempfile

logger = logging.getLogger("camera")

SNAP_DIR = os.path.join(tempfile.gettempdir(), "pcguardian_cam")
os.makedirs(SNAP_DIR, exist_ok=True)


class CameraSystem:
    def __init__(self, cfg):
        self.cfg = cfg
        self._streaming = False
        self._bot_app   = None  # telegram Application reference

    def set_bot_app(self, app):
        """Bot passes itself so camera can send photos directly."""
        self._bot_app = app

    def _open(self):
        for idx in range(3):
            for backend in [cv2.CAP_DSHOW, cv2.CAP_ANY]:
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    for _ in range(3): cap.read()  # warm up
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return cap
                cap.release()
        return None

    def capture_snapshot(self) -> str:
        cap = self._open()
        if not cap: return None
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None: return None
        path = os.path.join(SNAP_DIR, f"snap_{int(time.time())}.jpg")
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return path

    def capture_burst(self, count=5, interval=2.0) -> list:
        cap = self._open()
        if not cap: return []
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
        """Stream frames by sending directly via bot."""
        self._streaming = True

        def _run():
            cap = self._open()
            if not cap:
                logger.error("Stream: no camera found.")
                return
            while self._streaming:
                ret, frame = cap.read()
                if ret and frame is not None:
                    path = os.path.join(SNAP_DIR, f"stream_{int(time.time())}.jpg")
                    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if self._bot_app:
                        try:
                            import asyncio
                            future = asyncio.run_coroutine_threadsafe(
                                self._send_photo(chat_id, path),
                                self._bot_app.bot._loop
                            )
                            future.result(timeout=10)
                        except Exception as e:
                            logger.error(f"Stream send failed: {e}")
                time.sleep(interval)
            cap.release()

        threading.Thread(target=_run, daemon=True, name="CamStream").start()

    async def _send_photo(self, chat_id: int, path: str):
        try:
            with open(path, "rb") as f:
                await self._bot_app.bot.send_photo(chat_id=chat_id, photo=f)
        except Exception as e:
            logger.error(f"Photo send: {e}")

    def stop_stream(self):
        self._streaming = False

    def capture_panic_snapshot(self) -> str:
        return self.capture_snapshot()
