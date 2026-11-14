"""
PC Guardian — Speaker System
TTS, audio playback, volume control, media control
"""

import os
import logging
import threading
import tempfile

logger = logging.getLogger("speaker")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


class SpeakerSystem:
    def __init__(self, cfg):
        self.cfg = cfg
        self._engine = None
        self._init_tts()

    def _init_tts(self):
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 160)
            self._engine.setProperty("volume", 1.0)
            # Try to find a good English voice
            voices = self._engine.getProperty("voices")
            for v in voices:
                if "english" in v.name.lower() or "zira" in v.name.lower():
                    self._engine.setProperty("voice", v.id)
                    break
            logger.info("TTS engine initialized.")
        except Exception as e:
            logger.error(f"TTS init failed: {e}")

    def speak(self, text: str):
        """Speak text through PC speakers."""
        def _run():
            try:
                if self._engine:
                    self._engine.say(text)
                    self._engine.runAndWait()
            except Exception as e:
                logger.error(f"TTS speak failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def play_alert(self, mode: str = "loud"):
        """Play attention chime."""
        sounds = {
            "loud": os.path.join(ASSETS_DIR, "alert.wav"),
            "soft": os.path.join(ASSETS_DIR, "soft_chime.wav"),
        }
        path = sounds.get(mode, sounds["loud"])
        if os.path.exists(path):
            self.play_audio_file(path)
        else:
            # Fallback: use Windows beep
            try:
                import winsound
                freq = 1000 if mode == "loud" else 600
                winsound.Beep(freq, 500)
            except Exception:
                self.speak("Attention!")

    def play_audio_file(self, path: str):
        """Play any audio file (wav/ogg/mp3)."""
        def _run():
            try:
                # Convert ogg/mp3 to wav if needed
                if path.endswith(".ogg") or path.endswith(".mp3"):
                    wav_path = self._convert_to_wav(path)
                    if wav_path:
                        self._play_wav(wav_path)
                else:
                    self._play_wav(path)
            except Exception as e:
                logger.error(f"Audio play failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def _convert_to_wav(self, path: str) -> str:
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(path)
            wav_path = path.replace(".ogg", ".wav").replace(".mp3", ".wav")
            audio.export(wav_path, format="wav")
            return wav_path
        except Exception as e:
            logger.error(f"Audio convert failed: {e}")
            return None

    def _play_wav(self, path: str):
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME)
        except Exception:
            try:
                import playsound
                playsound.playsound(path)
            except Exception as e:
                logger.error(f"WAV play failed: {e}")

    def set_volume(self, level: int):
        """Set system volume 0-100."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            # Convert 0-100 to 0.0-1.0
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            logger.info(f"Volume set to {level}%")
        except Exception as e:
            logger.error(f"Volume set failed: {e}")

    def mute(self):
        self.set_volume(0)

    def unmute(self):
        self.set_volume(70)

    def stop_media(self):
        """Simulate media stop key."""
        try:
            import pyautogui
            pyautogui.press("stop")
        except Exception:
            pass

    def pause_media(self):
        """Simulate media pause key."""
        try:
            import pyautogui
            pyautogui.press("playpause")
        except Exception:
            pass
