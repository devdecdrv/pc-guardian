"""
PC Guardian — Camera System (FIXED)
- Live stream now works via async loop injection
- Snapshot reliable with proper warm-up
- Fallback to DirectShow if default index fails
"""

import cv2
import os
import time
import threading
import logging
import tempfile
import asyncio

logger = logging.getLogger("camera")

SNAPSHOT_DIR = os.path.join(tempfile.gettempdir(), "pcguardian_cam")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


class CameraSystem:
    def __init__(self, cfg):
        self.cfg = cfg
        self._streaming  = False
        self._stream_cb  = None
        self._stream_loop = None  # asyncio loop from bot thread

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Bot passes its loop so we can schedule sends from camera thread."""
        self._stream_loop = loop

    def _open_camera(self):
        """Try camera index 0, 1, 2 with DirectShow backend."""
        for idx in range(3):
            for backend in [cv2.CAP_DSHOW, cv2.CAP_ANY]:
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    # Warm up — discard first 5 frames
                    for _ in range(5):
                        cap.read()
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        logger.info(f"Camera opened: index={idx} backend={backend}")
                        return cap
                cap.release()
        logger.error("No camera found on any index.")
        return None

    def capture_snapshot(self) -> str:
        cap = self._open_camera()
        if not cap:
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return None
        path = os.path.join(SNAPSHOT_DIR, f"snap_{int(time.time())}.jpg")
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return path

    def capture_burst(self, count: int = 5, interval: float = 2.0) -> list:
        cap = self._open_camera()
        if not cap:
            return []
        paths = []
        for i in range(count):
            ret, frame = cap.read()
            if ret and frame is not None:
                path = os.path.join(SNAPSHOT_DIR, f"burst_{int(time.time())}_{i}.jpg")
                cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                paths.append(path)
            time.sleep(interval)
        cap.release()
        return paths

    def start_stream(self, callback, interval: float = 3.0):
        """
        Stream frames to callback(path).
        callback is an async coroutine function — scheduled onto bot's loop.
        """
        self._streaming = True
        self._stream_cb = callback

        def _run():
            cap = self._open_camera()
            if not cap:
                logger.error("Stream: no camera.")
                return
            while self._streaming:
                ret, frame = cap.read()
                if ret and frame is not None:
                    path = os.path.join(SNAPSHOT_DIR, f"stream_{int(time.time())}.jpg")
                    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if self._stream_cb:
                        if self._stream_loop and self._stream_loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                self._stream_cb(path), self._stream_loop
                            )
                        else:
                            try: self._stream_cb(path)
                            except Exception: pass
                time.sleep(interval)
            cap.release()
            logger.info("Camera stream stopped.")

        threading.Thread(target=_run, daemon=True, name="CameraStream").start()

    def stop_stream(self):
        self._streaming = False

    def capture_panic_snapshot(self) -> str:
        return self.capture_snapshot()
