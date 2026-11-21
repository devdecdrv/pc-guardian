"""
PC Guardian — Microphone (FIXED v4)
threading.Event used everywhere — stop actually works.
"""

import os
import time
import threading
import logging
import tempfile
import numpy as np

logger = logging.getLogger("microphone")

AUDIO_DIR   = os.path.join(tempfile.gettempdir(), "pcguardian_mic")
os.makedirs(AUDIO_DIR, exist_ok=True)

SAMPLE_RATE = 16000
CHANNELS    = 1


class MicrophoneSystem:
    def __init__(self, cfg, lock_engine=None):
        self.cfg         = cfg
        self.lock_engine = lock_engine
        self._panic_cb   = None

        # Events for reliable stopping
        self._stream_stop = threading.Event()
        self._panic_stop  = threading.Event()
        self._stream_stop.set()   # not streaming initially
        self._panic_stop.clear()  # panic listener runs

        if cfg.panic_detection.get("voice_enabled", True):
            threading.Thread(
                target=self._panic_loop,
                daemon=True,
                name="PanicMic"
            ).start()

    def record_clip(self, seconds: int = 15) -> str:
        try:
            import sounddevice as sd
            import scipy.io.wavfile as wav
            path  = os.path.join(AUDIO_DIR, f"clip_{int(time.time())}.wav")
            audio = sd.rec(
                int(seconds * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16"
            )
            sd.wait()
            wav.write(path, SAMPLE_RATE, audio)
            return path
        except Exception as e:
            logger.error(f"Record failed: {e}")
            return None

    def start_live_stream(self, callback, chunk_seconds: float = 3.0):
        # Stop any existing stream first
        self.stop_stream()
        time.sleep(0.3)

        self._stream_stop.clear()   # clear = running

        def _run():
            try:
                import sounddevice as sd
                import scipy.io.wavfile as wav

                while not self._stream_stop.is_set():
                    # Record chunk
                    audio = sd.rec(
                        int(chunk_seconds * SAMPLE_RATE),
                        samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype="int16"
                    )
                    sd.wait()

                    if self._stream_stop.is_set():
                        break

                    path = os.path.join(AUDIO_DIR, f"live_{int(time.time())}.wav")
                    wav.write(path, SAMPLE_RATE, audio)
                    if callback:
                        callback(path)

            except Exception as e:
                logger.error(f"Live stream error: {e}")

        threading.Thread(target=_run, daemon=True, name="MicStream").start()
        logger.info("Mic live stream started.")

    def stop_stream(self):
        """Actually stops the stream — sets event and waits."""
        self._stream_stop.set()
        time.sleep(0.1)
        logger.info("Mic stream stopped.")

    def set_panic_callback(self, fn):
        self._panic_cb = fn

    def stop_panic_listener(self):
        self._panic_stop.set()

    def _panic_loop(self):
        try:
            import sounddevice as sd

            threshold  = self.cfg.panic_detection.get("volume_threshold", 0.7)
            cooldown   = 30
            last_alert = 0

            while not self._panic_stop.is_set():
                try:
                    audio = sd.rec(
                        int(1.0 * SAMPLE_RATE),
                        samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype="float32"
                    )
                    sd.wait()

                    if self._panic_stop.is_set():
                        break

                    vol = float(np.abs(audio).mean())
                    normalized = min(vol * 100, 1.0)

                    if normalized > threshold:
                        now = time.time()
                        if now - last_alert > cooldown:
                            last_alert = now
                            logger.warning(f"Raised voice! vol={normalized:.2f}")
                            clip = self.record_clip(10)
                            if self._panic_cb and clip:
                                self._panic_cb(clip, "raised_voice")

                except Exception:
                    time.sleep(1)

        except Exception as e:
            logger.error(f"Panic loop: {e}")
