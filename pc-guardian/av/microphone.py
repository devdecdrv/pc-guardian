"""
PC Guardian — Microphone System
Recording, live streaming, always-on voice/panic detection
"""

import os
import time
import threading
import logging
import tempfile
import numpy as np

logger = logging.getLogger("microphone")

AUDIO_DIR = os.path.join(tempfile.gettempdir(), "pcguardian_mic")
os.makedirs(AUDIO_DIR, exist_ok=True)

SAMPLE_RATE = 16000
CHANNELS = 1


class MicrophoneSystem:
    def __init__(self, cfg, lock_engine=None):
        self.cfg = cfg
        self.lock_engine = lock_engine
        self._recording = False
        self._stream_active = False
        self._panic_listening = False
        self._panic_thread = None
        self._panic_callback = None
        self._stream_callback = None

        # Start always-on panic listener
        panic_cfg = cfg.panic_detection
        if panic_cfg.get("voice_enabled", True):
            self.start_panic_listener()

    def record_clip(self, seconds: int = 15) -> str:
        """Record N seconds from mic. Returns wav file path."""
        try:
            import sounddevice as sd
            import scipy.io.wavfile as wav

            path = os.path.join(AUDIO_DIR, f"clip_{int(time.time())}.wav")
            audio = sd.rec(
                int(seconds * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16"
            )
            sd.wait()
            wav.write(path, SAMPLE_RATE, audio)
            logger.info(f"Clip saved: {path}")
            return path
        except Exception as e:
            logger.error(f"Record failed: {e}")
            return None

    def start_live_stream(self, callback, chunk_seconds: float = 3.0):
        """Stream mic in chunks to callback(path)."""
        self._stream_active = True
        self._stream_callback = callback

        def _run():
            try:
                import sounddevice as sd
                import scipy.io.wavfile as wav

                while self._stream_active:
                    audio = sd.rec(
                        int(chunk_seconds * SAMPLE_RATE),
                        samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype="int16"
                    )
                    sd.wait()
                    path = os.path.join(AUDIO_DIR, f"live_{int(time.time())}.wav")
                    wav.write(path, SAMPLE_RATE, audio)
                    if self._stream_callback:
                        self._stream_callback(path)
            except Exception as e:
                logger.error(f"Live stream failed: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def stop_stream(self):
        self._stream_active = False

    def start_panic_listener(self):
        """Always-on background listener for raised voice / distress."""
        self._panic_listening = True
        self._panic_thread = threading.Thread(
            target=self._panic_loop,
            daemon=True,
            name="PanicMicListener"
        )
        self._panic_thread.start()
        logger.info("Panic mic listener started.")

    def set_panic_callback(self, fn):
        """fn(clip_path, reason) called on detection."""
        self._panic_callback = fn

    def _panic_loop(self):
        try:
            import sounddevice as sd

            threshold = self.cfg.panic_detection.get("volume_threshold", 0.7)
            clip_duration = 10  # seconds to record when panic detected
            check_interval = 1.0  # seconds between volume checks
            cooldown = 30  # seconds between alerts

            last_alert = 0

            while self._panic_listening:
                try:
                    audio = sd.rec(
                        int(check_interval * SAMPLE_RATE),
                        samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype="float32"
                    )
                    sd.wait()
                    volume = float(np.abs(audio).mean())
                    normalized = min(volume * 100, 1.0)

                    if normalized > threshold:
                        now = time.time()
                        if now - last_alert > cooldown:
                            last_alert = now
                            logger.warning(f"Raised voice detected! Volume: {normalized:.2f}")
                            # Record clip for evidence
                            clip_path = self.record_clip(clip_duration)
                            if self._panic_callback:
                                self._panic_callback(clip_path, "raised_voice")
                except Exception:
                    time.sleep(1)

        except Exception as e:
            logger.error(f"Panic listener failed: {e}")

    def stop_panic_listener(self):
        self._panic_listening = False
