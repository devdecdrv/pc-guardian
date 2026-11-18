# 🛡 PC Guardian

Advanced parental control system for Windows — controlled entirely via Telegram.

---

## Quick Start

1. Download `pc-guardian.exe` from [Releases](https://github.com/devdecdrv/pc-guardian/releases)
2. Double click — starts silently in background
3. Open Telegram → send commands to your bot

---

## Telegram Commands

### 🔒 Lock
| Command | What it does |
|---|---|
| `/lock` | Lock PC immediately |
| `/lock 30` | Lock for 30 minutes, auto-unlock after |
| `/unlock` | Unlock PC |
| `/softlock` | Block games/YouTube only, desktop still works |
| `/status` | Show lock status, session time, active apps |

> **Keyboard unlock:** Type `lockson` anywhere on keyboard while PC is locked

---

### 🔊 Speaker — Talk to your son
| Command | What it does |
|---|---|
| `/speak Hello son` | Say any message through PC speakers |
| `/msg calm` | "Calm down son, take a breath. Dad is here." |
| `/msg break` | "Time for a break. Come eat something." |
| `/msg bed` | "Bedtime. Shut down the PC now." |
| `/msg good` | "Good job today. I am proud of you." |
| `/msg study` | "Time to study now. Games later." |
| `/msg eat` | "Come have your food. PC will wait." |
| `/alert` | Loud attention chime |
| `/alert soft` | Gentle chime |
| `/volume 80` | Set volume to 80% |
| `/volume mute` | Mute PC |
| `/volume unmute` | Unmute PC |
| `/music stop` | Stop any media playing |
| `/music pause` | Pause media |

> **Voice message:** Send a voice note in Telegram → plays your actual voice on PC speakers

---

### 📷 Camera
| Command | What it does |
|---|---|
| `/cam` | Take one photo from webcam |
| `/cam burst` | Take 5 photos, 2 seconds apart |
| `/cam live` | Live stream — photo every 3 seconds in this chat |
| `/cam stop` | Stop live stream |

---

### 🎤 Microphone
| Command | What it does |
|---|---|
| `/listen 30` | Record 30 seconds from mic, sends audio to you |
| `/listen 10` | Record 10 seconds |
| `/listen live` | Live mic stream |
| `/listen stop` | Stop mic stream |

---

### 🖥 Monitor
| Command | What it does |
|---|---|
| `/screen` | Screenshot of current PC screen |
| `/apps` | All running apps right now |
| `/top` | Top apps by usage time today |
| `/history` | Today's full event log |
| `/week` | Weekly usage summary |

---

### ⏰ Schedule
| Command | What it does |
|---|---|
| `/schedule` | View current schedule |
| `/homework on` | Homework mode — block games and YouTube |
| `/homework off` | Turn off homework mode |
| `/break_time 30` | Give 30 min free time, auto-locks after |
| `/reward 60` | Give 60 min reward + voice message plays on PC |

---

### 📁 Files
| Command | What it does |
|---|---|
| `/ls` | List C:\Users directory |
| `/ls C:\Users\YourName\Desktop` | List any folder |
| `/readfile C:\path\to\file.txt` | Download any file to Telegram |
| `/writefile C:\path\to\file.txt` | Reply to a file → writes it to PC |
| `/deletefile C:\path\to\file.txt` | Delete a file on PC |
| `/findfile *.txt` | Search for files matching pattern |
| `/findfile *.mp4 C:\Users` | Search in specific folder |

---

### 💻 System
| Command | What it does |
|---|---|
| `/shutdown` | Shut down PC in 10 seconds |
| `/restart` | Restart PC in 10 seconds |
| `/kill roblox` | Force close any app by name |
| `/kill chrome` | Force close Chrome |

---

### ⚙️ Settings
| Command | What it does |
|---|---|
| `/settings` | View all current settings |
| `/lockword newword` | Change the keyboard unlock word |
| `/password change newpass` | Change uninstall password |
| `/help` | Full command list in Telegram |

---

### 🤖 AI
| Command | What it does |
|---|---|
| `/ai why is gaming addictive` | Ask Claude anything from Telegram |

---

## Automatic Alerts

These are sent to your Telegram automatically — no command needed:

| Alert | Trigger |
|---|---|
| ⚠️ Raised voice | Mic detects shouting |
| ⚠️ Rage-clicking | 10+ rapid clicks in 3 seconds |
| ⚠️ Rage-typing | 20+ rapid keypresses in 3 seconds |
| 🚨 Tamper alert | Someone tried to kill or uninstall Guardian |
| 📊 Daily report | Sent every evening at 9 PM |

---

## Changing Credentials

Open `pc-guardian/first_run.py` on GitHub, edit these lines at the top, push — new `.exe` builds automatically:

```python
BOT_TOKEN          = "your_new_bot_token"
TELEGRAM_USER_ID   = 123456789
CHILD_NAME         = "Son"
LOCK_KEYWORD       = "lockson"
UNINSTALL_PASSWORD = "decdrv"
```

---

## MCP Custom Connector (AI Integration)

Run alongside the exe to expose all controls as an API:

```bash
python mcp_server.py
```

Tunnel publicly:
```bash
ngrok http 7860
```

Add `https://xxxx.ngrok.io` as custom MCP connector in Claude.ai settings.

Available MCP tools: `lock_pc`, `unlock_pc`, `get_status`, `speak`, `play_preset`, `take_snapshot`, `get_screenshot`, `get_running_apps`, `record_mic`, `set_volume`, `list_directory`, `read_file`, `kill_app`, `get_activity_report`

---

## Protection

- Runs hidden in background — no window, no tray icon
- Starts automatically at every Windows boot
- Watchdog restarts it if killed
- Uninstall requires password
- 3 wrong password attempts → alert sent to Telegram
- Config stored encrypted on disk

---

## Files Reference

```
pc-guardian/
├── main.py                  — entry point
├── first_run.py             — credentials config (edit this)
├── mcp_server.py            — MCP/HTTP API server
├── requirements.txt         — Python dependencies
├── core/
│   ├── lock_engine.py       — lock/unlock + overlay
│   ├── keyword_listener.py  — keyboard trigger
│   ├── startup.py           — boot persistence
│   ├── watchdog.py          — self-healing
│   └── service.py           — Windows service
├── bot/
│   ├── bot.py               — Telegram bot runner
│   ├── commands.py          — all commands
│   ├── auth.py              — user verification
│   └── alerts.py            — auto-alert sender
├── av/
│   ├── camera.py            — webcam
│   ├── microphone.py        — mic + panic detection
│   └── speaker.py           — TTS + audio
├── monitor/
│   ├── activity.py          — app usage tracking
│   ├── behavior.py          — panic/frustration detection
│   └── reporter.py          — daily/weekly reports
├── scheduler/
│   └── schedule_engine.py   — auto-lock schedules
├── protection/
│   ├── tamper_detect.py     — tamper alerts
│   └── uninstall_guard.py   — delete protection
├── config/
│   ├── config.py            — settings manager
│   └── crypto.py            — encryption
├── dashboard/
│   └── app.py               — web panel localhost:8080
└── logs/
    └── logger.py            — event logging
```

---

## Web Dashboard

Open in browser on the PC:
```
http://localhost:8080
```
Password: same as your uninstall password.

Shows live status, app usage, event log, quick lock/unlock controls.

---

Built with care. For the son who needs his dad present.
