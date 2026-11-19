"""
PC Guardian — Microphone (FIXED)
- stop_stream actually works now via threading Event
- Panic listener reliable
- Live stream chunks sent properly
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
        self.cfg          = cfg
        self.lock_engine  = lock_engine
        self._panic_cb    = None

        # Proper stop events — this is what was missing
        self._stream_stop  = threading.Event()
        self._panic_stop   = threading.Event()

        # Start panic listener
        if cfg.panic_detection.get("voice_enabled", True):
            self._start_panic_listener()

    # ── PUBLIC ────────────────────────────────────────────────────────────────

    def record_clip(self, seconds: int = 15) -> str:
        """Record N seconds. Returns wav path."""
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
        """Stream mic in chunks to callback(path). Properly stoppable."""
        self._stream_stop.clear()

        def _run():
            try:
                import sounddevice as sd
                import scipy.io.wavfile as wav

                while not self._stream_stop.is_set():
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
        """Stop live stream — actually works now."""
        self._stream_stop.set()
        logger.info("Mic stream stop signal sent.")

    def set_panic_callback(self, fn):
        """fn(clip_path, reason) called on panic detection."""
        self._panic_cb = fn

    # ── PANIC LISTENER ────────────────────────────────────────────────────────

    def _start_panic_listener(self):
        self._panic_stop.clear()
        t = threading.Thread(
            target=self._panic_loop,
            daemon=True,
            name="PanicMic"
        )
        t.start()
        logger.info("Panic mic listener started.")

    def stop_panic_listener(self):
        self._panic_stop.set()

    def _panic_loop(self):
        try:
            import sounddevice as sd

            threshold  = self.cfg.panic_detection.get("volume_threshold", 0.7)
            clip_secs  = 10
            check_secs = 1.0
            cooldown   = 30
            last_alert = 0

            while not self._panic_stop.is_set():
                try:
                    audio = sd.rec(
                        int(check_secs * SAMPLE_RATE),
                        samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype="float32"
                    )
                    sd.wait()

                    if self._panic_stop.is_set():
                        break

                    volume     = float(np.abs(audio).mean())
                    normalized = min(volume * 100, 1.0)

                    if normalized > threshold:
                        now = time.time()
                        if now - last_alert > cooldown:
                            last_alert = now
                            logger.warning(f"Raised voice! vol={normalized:.2f}")
                            clip = self.record_clip(clip_secs)
                            if self._panic_cb and clip:
                                self._panic_cb(clip, "raised_voice")

                except Exception:
                    time.sleep(1)

        except Exception as e:
            logger.error(f"Panic loop failed: {e}")
