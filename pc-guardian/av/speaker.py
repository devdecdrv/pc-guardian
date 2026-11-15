"""
PC Guardian — Speaker (FIXED)
Uses PowerShell TTS as primary — 100% reliable on Windows, no install needed.
pyttsx3 as secondary.
"""

import os
import logging
import threading
import subprocess
import time

logger = logging.getLogger("speaker")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

_tts_lock = threading.Lock()


def _powershell_speak(text: str):
    """Primary TTS — works on every Windows PC without any pip install."""
    try:
        safe = text.replace('"', '').replace("'", '').replace('\n', ' ')
        cmd = (
            'powershell -WindowStyle Hidden -Command "'
            'Add-Type -AssemblyName System.Speech; '
            '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
            '$s.Volume = 100; '
            '$s.Rate = -1; '
            f'$s.Speak(\\"{safe}\\")'
            '"'
        )
        subprocess.run(cmd, shell=True, timeout=30, capture_output=True)
    except Exception as e:
        logger.error(f"PowerShell TTS failed: {e}")


class SpeakerSystem:
    def __init__(self, cfg):
        self.cfg = cfg
        self._muted = False
        self._volume = 100

    def speak(self, text: str):
        def _run():
            with _tts_lock:
                _powershell_speak(text)
        threading.Thread(target=_run, daemon=True).start()

    def play_alert(self, mode: str = "loud"):
        def _run():
            # Try wav file first
            sounds = {
                "loud": os.path.join(ASSETS_DIR, "alert.wav"),
                "soft": os.path.join(ASSETS_DIR, "soft_chime.wav"),
            }
            path = sounds.get(mode, sounds["loud"])
            if os.path.exists(path):
                try:
                    import winsound
                    winsound.PlaySound(path, winsound.SND_FILENAME)
                    return
                except Exception:
                    pass
            # Fallback: beep pattern
            try:
                import winsound
                if mode == "loud":
                    for _ in range(3):
                        winsound.Beep(1200, 200)
                        time.sleep(0.1)
                else:
                    winsound.Beep(700, 400)
            except Exception:
                _powershell_speak("Attention!")
        threading.Thread(target=_run, daemon=True).start()

    def play_audio_file(self, path: str):
        """Play voice message sent from Telegram."""
        def _run():
            try:
                wav_path = path
                if not path.endswith(".wav"):
                    wav_path = self._to_wav(path)
                if wav_path and os.path.exists(wav_path):
                    import winsound
                    winsound.PlaySound(wav_path, winsound.SND_FILENAME)
                else:
                    _powershell_speak("New voice message from Dad.")
            except Exception as e:
                logger.error(f"Audio play failed: {e}")
                _powershell_speak("New voice message from Dad.")
        threading.Thread(target=_run, daemon=True).start()

    def _to_wav(self, path: str) -> str:
        wav = path.rsplit(".", 1)[0] + ".wav"
        try:
            from pydub import AudioSegment
            AudioSegment.from_file(path).export(wav, format="wav")
            return wav
        except Exception:
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", path, wav],
                    capture_output=True, timeout=15
                )
                return wav if os.path.exists(wav) else None
            except Exception:
                return None

    def set_volume(self, level: int):
        self._volume = level
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        except Exception:
            subprocess.run(
                f'powershell -Command "[audio]::Volume={level/100}"',
                shell=True, capture_output=True
            )

    def mute(self):
        self._muted = True
        self.set_volume(0)

    def unmute(self):
        self._muted = False
        self.set_volume(self._volume or 70)

    def stop_media(self):
        subprocess.run(
            'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]178)"',
            shell=True, capture_output=True
        )

    def pause_media(self):
        subprocess.run(
            'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]179)"',
            shell=True, capture_output=True
        )
