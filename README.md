# 🛡 PC Guardian

**Advanced parental control system for Windows — controlled entirely via Telegram.**

Lock the PC, watch through the camera, listen through the mic, speak through the speakers, monitor app usage, detect panic/frustration, and schedule everything automatically.

---

## Features

| Category | Features |
|---|---|
| 🔒 Lock | Full-screen overlay, all monitors, blocks all input |
| 🤖 Telegram | Complete remote control from your phone |
| 📷 Camera | Snapshot, burst, live stream |
| 🎤 Mic | Record clips, live stream, auto-panic detection |
| 🔊 Speaker | Text-to-speech, play your voice, preset messages |
| 📊 Monitor | App tracking, session time, usage reports |
| ⏰ Schedule | School hours, bedtime, homework mode, break timer |
| 🚨 Panic | Raised voice detection, rage-clicking, long session alerts |
| 🛡 Protection | Windows Service, watchdog, tamper detection, password uninstall |
| 🌐 Dashboard | Local web panel at http://localhost:8080 |

---

## Quick Start

### 1. Install Python 3.11+
Download from https://python.org

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create Telegram Bot
- Open Telegram → search **@BotFather**
- Send `/newbot` → follow instructions → copy the token
- Open **@userinfobot** → copy your numeric user ID

### 4. Run Setup
```bash
python main.py --setup
```
Enter your bot token, user ID, password, and preferences.

### 5. Start PC Guardian
```bash
python main.py
```

### 6. Install as Windows Service (runs at boot, survives logout)
```bash
python main.py --install-service
```

---

## Telegram Commands

```
LOCK
/lock              — Lock PC now
/lock 30           — Lock for 30 minutes
/unlock            — Unlock PC
/softlock          — Block games/YouTube only
/status            — Current status

SPEAK TO YOUR SON
/speak [text]      — Say message on PC
/alert             — Attention chime
/msg calm          — "Calm down son, take a breath"
/msg break         — "Time for a break"
/msg bed           — "Bedtime, shut down now"
/msg good          — "Good job today, proud of you"
/msg study         — "Time to study now"
/msg eat           — "Come have your food"
/volume 80         — Set volume to 80%
/volume mute       — Mute PC
Send a voice note  — Plays your actual voice on PC

CAMERA
/cam               — Quick photo
/cam burst         — 5 photos in 10 seconds
/cam live          — Stream (photo every 3s)
/cam stop          — Stop stream

MICROPHONE
/listen 30         — Record 30 seconds
/listen live       — Live mic stream
/listen stop       — Stop

MONITOR
/screen            — Screenshot right now
/apps              — All running apps
/top               — Top apps today by time
/history           — Today's full event log
/week              — Weekly summary

SCHEDULE
/schedule          — View current schedule
/homework on       — Block games/YouTube
/homework off      — Restore normal access
/break_time 30     — 30 min free time, then auto-locks
/reward 60         — 60 min reward with voice message

SYSTEM
/shutdown          — Shut down PC
/restart           — Restart PC
/kill roblox       — Force close any app by name

SETTINGS
/lockword lockson  — Change lock trigger word
/password change X — Change uninstall password
/settings          — View all settings
/help              — Full command list
```

---

## Automatic Alerts (sent to your Telegram)

| Alert | Trigger |
|---|---|
| ⚠️ Raised voice | Mic detects shouting or crying |
| ⚠️ Rage-clicking | 10+ rapid clicks in 3 seconds |
| ⚠️ Rage-typing | 20+ rapid keypresses in 3 seconds |
| ⏰ Long session | 2+ hours on same game |
| 🚨 Tamper alert | Someone tried to kill/uninstall the guardian |
| 📊 Daily report | Sent every evening at your set time |

---

## Protection

- Runs as Windows Service (SYSTEM level)
- Starts automatically at boot
- Watchdog restarts it if killed
- Uninstall requires password
- 3 wrong password attempts → alert sent to you
- Registry startup entry protected
- Config stored encrypted on disk

---

## Build EXE

```bash
pip install pyinstaller
python build/build.py
```
Output: `dist/pc-guardian.exe`

---

## Web Dashboard

Open `http://localhost:8080` in browser on the PC.
Password is the same as your uninstall password.

---

## Folder Structure

```
pc-guardian/
├── core/           Windows service, lock engine, keyword listener, watchdog
├── bot/            Telegram bot and all commands
├── av/             Camera, microphone, speaker
├── monitor/        Activity tracking, behavior/panic detection, reports
├── scheduler/      Auto-lock schedules, homework mode, break timer
├── protection/     Tamper detection, uninstall guard
├── config/         Encrypted config storage
├── dashboard/      Local web panel
├── logs/           Event log
├── build/          PyInstaller build script
└── assets/         Alert sounds, icon
```

---

## Requirements

- Windows 10 / 11
- Python 3.11+
- Webcam (for camera features)
- Microphone (for mic features)
- Internet connection (for Telegram)

---

Made with care. For the son who needs his dad present.
