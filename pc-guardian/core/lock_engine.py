"""
PC Guardian — Lock Engine (FIXED)
Uses win32 API directly — most reliable method on Windows.
No tkinter threading issues.
Password: decdrv typed anywhere unlocks.
"""

import threading
import time
import ctypes
import ctypes.wintypes
import logging
import subprocess
import os
from logs.logger import log_event

logger = logging.getLogger("lock_engine")

UNLOCK_PASSWORD = "decdrv"

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WH_MOUSE_LL    = 14
WM_KEYDOWN     = 0x0100

_lock_active  = threading.Event()
_kb_hook      = None
_ms_hook      = None
_typed        = []
_hook_proc_kb = None  # keep reference alive
_hook_proc_ms = None


class LockEngine:
    def __init__(self, cfg):
        self.cfg     = cfg
        self.locked  = False
        self._soft   = False
        self._cbs    = []
        self._overlay_proc = None

    def register_lock_callback(self, fn):
        self._cbs.append(fn)

    # ── PUBLIC ────────────────────────────────────────────────────────────────

    def lock(self, message: str = None, duration_minutes: int = None):
        if self.locked:
            return
        self.locked = True
        _lock_active.set()
        msg = message or self.cfg.lock_message
        log_event("LOCK", msg)
        logger.info("Locking PC.")

        for cb in self._cbs:
            try: cb("lock")
            except Exception: pass

        self._disable_taskmgr()
        self._install_hooks()

        # Launch overlay as separate process — most reliable
        threading.Thread(
            target=self._launch_overlay, args=(msg,),
            daemon=True, name="Overlay"
        ).start()

        if duration_minutes:
            threading.Thread(
                target=self._auto_unlock, args=(duration_minutes,),
                daemon=True
            ).start()

    def unlock(self, message: str = None):
        if not self.locked:
            return
        self.locked = False
        _lock_active.clear()
        log_event("UNLOCK", message or "Unlocked.")
        logger.info("Unlocking PC.")

        for cb in self._cbs:
            try: cb("unlock")
            except Exception: pass

        self._enable_taskmgr()
        self._remove_hooks()
        self._kill_overlay()

    def soft_lock(self):
        self._soft = True
        log_event("SOFTLOCK", "Games blocked.")

    def soft_unlock(self):
        self._soft = False
        log_event("SOFTUNLOCK", "Soft lock off.")

    @property
    def status(self):
        return "locked" if self.locked else "unlocked"

    # ── OVERLAY ───────────────────────────────────────────────────────────────

    def _launch_overlay(self, message: str):
        """
        Write a small overlay script and run it as a subprocess.
        Subprocess approach avoids all tkinter + threading issues.
        """
        script = f'''
import tkinter as tk
import sys

msg = {repr(message)}

root = tk.Tk()
root.withdraw()

try:
    from screeninfo import get_monitors
    monitors = get_monitors()
except Exception:
    monitors = None

wins = []

def make(x, y, w, h):
    win = tk.Toplevel(root)
    win.geometry(f"{{w}}x{{h}}+{{x}}+{{y}}")
    win.configure(bg="black")
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.lift()
    win.focus_force()

    import tkinter.font as f
    tk.Label(win, text="\\U0001f512  PC LOCKED",
             font=f.Font(family="Segoe UI", size=34, weight="bold"),
             fg="#ff3333", bg="black").pack(pady=(h//5, 20))
    tk.Label(win, text=msg,
             font=f.Font(family="Segoe UI", size=18),
             fg="white", bg="black", wraplength=w-100).pack(pady=10)
    tk.Label(win, text="Contact your father to unlock.",
             font=f.Font(family="Segoe UI", size=12),
             fg="#555555", bg="black").pack(pady=6)
    wins.append(win)

if monitors:
    for m in monitors:
        make(m.x, m.y, m.width, m.height)
else:
    make(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())

def _keep_top():
    for w in wins:
        try:
            w.lift()
            w.attributes("-topmost", True)
        except Exception:
            pass
    root.after(500, _keep_top)

root.after(500, _keep_top)
root.mainloop()
'''
        import tempfile, sys
        path = os.path.join(tempfile.gettempdir(), "pcg_overlay.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)

        self._overlay_proc = subprocess.Popen(
            [sys.executable, path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

    def _kill_overlay(self):
        if self._overlay_proc:
            try:
                self._overlay_proc.terminate()
                self._overlay_proc = None
            except Exception:
                pass
        # Also kill any stray overlay processes
        try:
            import psutil
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    cmd = " ".join(proc.info.get("cmdline") or [])
                    if "pcg_overlay" in cmd:
                        proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

    # ── HOOKS ─────────────────────────────────────────────────────────────────

    def _install_hooks(self):
        global _kb_hook, _ms_hook, _hook_proc_kb, _hook_proc_ms, _typed
        _typed.clear()

        HOOKPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong
        )

        def kb_proc(nCode, wParam, lParam):
            if _lock_active.is_set():
                if wParam == WM_KEYDOWN:
                    try:
                        vk = ctypes.cast(
                            lParam, ctypes.POINTER(ctypes.c_ulong)
                        )[0] & 0xFF
                        # Only a-z keys (65-90)
                        if 65 <= vk <= 90:
                            _typed.append(chr(vk).lower())
                            if len(_typed) > 20:
                                _typed.pop(0)
                            if "".join(_typed[-len(UNLOCK_PASSWORD):]) == UNLOCK_PASSWORD:
                                _typed.clear()
                                threading.Thread(
                                    target=self.unlock, daemon=True
                                ).start()
                    except Exception:
                        pass
                return 1  # block all keys
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        def ms_proc(nCode, wParam, lParam):
            if _lock_active.is_set():
                return 1  # block mouse
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        _hook_proc_kb = HOOKPROC(kb_proc)
        _hook_proc_ms = HOOKPROC(ms_proc)

        _kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _hook_proc_kb, None, 0)
        _ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL,    _hook_proc_ms, None, 0)

        # Message pump — keeps hooks alive
        def pump():
            msg = ctypes.wintypes.MSG()
            while _lock_active.is_set():
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.005)

        threading.Thread(target=pump, daemon=True, name="HookPump").start()
        logger.info("Input hooks installed.")

    def _remove_hooks(self):
        global _kb_hook, _ms_hook
        try:
            if _kb_hook:
                user32.UnhookWindowsHookEx(_kb_hook)
                _kb_hook = None
            if _ms_hook:
                user32.UnhookWindowsHookEx(_ms_hook)
                _ms_hook = None
        except Exception as e:
            logger.warning(f"Hook remove: {e}")

    # ── SYSTEM ────────────────────────────────────────────────────────────────

    def _disable_taskmgr(self):
        try:
            import winreg
            k = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
                0, winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY
            )
            winreg.SetValueEx(k, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(k)
        except Exception as e:
            logger.warning(f"DisableTaskMgr: {e}")

    def _enable_taskmgr(self):
        try:
            import winreg
            k = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(k, "DisableTaskMgr", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(k)
        except Exception:
            pass

    def _auto_unlock(self, minutes: int):
        time.sleep(minutes * 60)
        if self.locked:
            self.unlock(f"Auto-unlock after {minutes} min.")
