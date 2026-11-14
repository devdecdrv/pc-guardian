"""
PC Guardian — Camera System
Webcam capture: snapshot, burst, live stream
"""

import cv2
import os
import time
import threading
import logging
import tempfile

logger = logging.getLogger("camera")

SNAPSHOT_DIR = os.path.join(tempfile.gettempdir(), "pcguardian_cam")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


class CameraSystem:
    def __init__(self, cfg):
        self.cfg = cfg
        self._streaming = False
        self._stream_thread = None
        self._stream_callback = None

    def _get_camera(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.warning("No camera found.")
            return None
        # Warm up
        for _ in range(5):
            cap.read()
        return cap

    def capture_snapshot(self) -> str:
        """Capture one photo. Returns file path."""
        cap = self._get_camera()
        if not cap:
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        path = os.path.join(SNAPSHOT_DIR, f"snap_{int(time.time())}.jpg")
        cv2.imwrite(path, frame)
        logger.info(f"Snapshot saved: {path}")
        return path

    def capture_burst(self, count: int = 5, interval: float = 2.0) -> list:
        """Capture N photos with interval. Returns list of paths."""
        cap = self._get_camera()
        if not cap:
            return []
        paths = []
        for i in range(count):
            ret, frame = cap.read()
            if ret:
                path = os.path.join(SNAPSHOT_DIR, f"burst_{int(time.time())}_{i}.jpg")
                cv2.imwrite(path, frame)
                paths.append(path)
            time.sleep(interval)
        cap.release()
        return paths

    def start_stream(self, callback, interval: float = 3.0):
        """Send a photo every N seconds to callback(path)."""
        self._streaming = True
        self._stream_callback = callback

        def _run():
            cap = self._get_camera()
            if not cap:
                return
            while self._streaming:
                ret, frame = cap.read()
                if ret:
                    path = os.path.join(SNAPSHOT_DIR, f"stream_{int(time.time())}.jpg")
                    cv2.imwrite(path, frame)
                    if self._stream_callback:
                        self._stream_callback(path)
                time.sleep(interval)
            cap.release()

        self._stream_thread = threading.Thread(target=_run, daemon=True)
        self._stream_thread.start()

    def stop_stream(self):
        self._streaming = False

    def capture_panic_snapshot(self) -> str:
        """High-priority snapshot for panic alerts."""
        return self.capture_snapshot()
