"""
PC Guardian — Speaker System (FIXED)
- Uses winsound + pyttsx3 with threading fix
- Fallback chain: winsound -> pyttsx3 -> powershell TTS
- Password: decdrv unlocks speaker settings
"""

import os
import logging
import threading
import subprocess
import tempfile
import time

logger = logging.getLogger("speaker")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
UNLOCK_PASSWORD = "decdrv"

# Global engine lock — pyttsx3 crashes if called from multiple threads
_tts_lock = threading.Lock()
_engine = None
_engine_ready = threading.Event()


def _init_engine():
    global _engine
    try:
        import pyttsx3
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 155)
        _engine.setProperty("volume", 1.0)
        voices = _engine.getProperty("voices")
        for v in voices:
            if "zira" in v.name.lower() or "english" in v.name.lower():
                _engine.setProperty("voice", v.id)
                break
        _engine_ready.set()
        logger.info("TTS engine ready.")
    except Exception as e:
        logger.error(f"TTS init failed: {e}")
        _engine_ready.set()  # set anyway so callers don't block


# Init engine in its own thread and keep it alive
_tts_thread = threading.Thread(target=_init_engine, daemon=True)
_tts_thread.start()


def _powershell_speak(text: str):
    """Fallback TTS via PowerShell — always works on Windows."""
    try:
        safe = text.replace("'", "").replace('"', '')
        cmd = (
            f'powershell -Command "Add-Type -AssemblyName System.Speech; '
            f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
            f'$s.Volume = 100; $s.Rate = 0; $s.Speak(\\"{safe}\\")"'
        )
        subprocess.run(cmd, shell=True, timeout=30)
    except Exception as e:
        logger.error(f"PowerShell TTS failed: {e}")


class SpeakerSystem:
    def __init__(self, cfg):
        self.cfg = cfg
        self._muted = False
        self._volume = 100

    def speak(self, text: str):
        """Speak text. Tries pyttsx3 first, falls back to PowerShell."""
        if self._muted:
            return

        def _run():
            _engine_ready.wait(timeout=5)
            with _tts_lock:
                try:
                    if _engine:
                        _engine.say(text)
                        _engine.runAndWait()
                        return
                except Exception as e:
                    logger.warning(f"pyttsx3 failed, using PowerShell: {e}")
            # Fallback
            _powershell_speak(text)

        threading.Thread(target=_run, daemon=True).start()

    def play_alert(self, mode: str = "loud"):
        """Play chime. Falls back to winsound beep."""
        sounds = {
            "loud": os.path.join(ASSETS_DIR, "alert.wav"),
            "soft": os.path.join(ASSETS_DIR, "soft_chime.wav"),
        }
        path = sounds.get(mode, sounds["loud"])

        def _run():
            if os.path.exists(path):
                try:
                    import winsound
                    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    return
                except Exception:
                    pass
            # Fallback beep
            try:
                import winsound
                freq = 1200 if mode == "loud" else 700
                for _ in range(3 if mode == "loud" else 1):
                    winsound.Beep(freq, 300)
                    time.sleep(0.1)
            except Exception:
                _powershell_speak("Attention!")

        threading.Thread(target=_run, daemon=True).start()

    def play_audio_file(self, path: str):
        """Play any audio file sent from Telegram."""
        def _run():
            try:
                # Convert ogg to wav (Telegram voice messages are ogg)
                wav_path = path
                if path.endswith(".ogg") or path.endswith(".mp3"):
                    wav_path = self._convert_to_wav(path)
                if wav_path:
                    import winsound
                    winsound.PlaySound(wav_path, winsound.SND_FILENAME)
            except Exception as e:
                logger.error(f"Audio file play failed: {e}")
                # Last resort
                _powershell_speak("New voice message from Dad.")

        threading.Thread(target=_run, daemon=True).start()

    def _convert_to_wav(self, path: str) -> str:
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(path)
            wav_path = path.rsplit(".", 1)[0] + ".wav"
            audio.export(wav_path, format="wav")
            return wav_path
        except Exception:
            try:
                # ffmpeg fallback
                wav_path = path.rsplit(".", 1)[0] + ".wav"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", path, wav_path],
                    capture_output=True, timeout=15
                )
                return wav_path if os.path.exists(wav_path) else None
            except Exception as e:
                logger.error(f"Convert failed: {e}")
                return None

    def set_volume(self, level: int):
        """Set system volume 0–100."""
        self._volume = level
        try:
            subprocess.run(
                f'powershell -Command "[audio]::Volume = {level / 100}"',
                shell=True, capture_output=True
            )
        except Exception:
            pass
        # pycaw method
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        except Exception as e:
            logger.warning(f"pycaw volume failed: {e}")

    def mute(self):
        self._muted = True
        self.set_volume(0)

    def unmute(self):
        self._muted = False
        self.set_volume(self._volume or 70)

    def stop_media(self):
        try:
            import pyautogui
            pyautogui.press("stop")
        except Exception:
            subprocess.run(
                'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]178)"',
                shell=True, capture_output=True
            )

    def pause_media(self):
        try:
            import pyautogui
            pyautogui.press("playpause")
        except Exception:
            subprocess.run(
                'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]179)"',
                shell=True, capture_output=True
            )
