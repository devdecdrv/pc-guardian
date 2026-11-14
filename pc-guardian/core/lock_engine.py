"""
PC Guardian — Lock Engine (FIXED)
- Reliable full-screen overlay using win32 + tkinter
- Password: decdrv unlocks via keyboard or bot
- Blocks Ctrl+Alt+Del via registry during lock
- Input blocking via ctypes low-level hooks
"""

import threading
import time
import ctypes
import logging
import subprocess
import os
from logs.logger import log_event

logger = logging.getLogger("lock_engine")

UNLOCK_PASSWORD = "decdrv"

# Windows constants
WH_KEYBOARD_LL = 13
WH_MOUSE_LL    = 14
user32         = ctypes.windll.user32
kernel32       = ctypes.windll.kernel32

_lock_active   = threading.Event()
_overlay_root  = None
_kb_hook       = None
_ms_hook       = None
_typed_buffer  = []


class LockEngine:
    def __init__(self, cfg):
        self.cfg        = cfg
        self.locked     = False
        self._soft      = False
        self._callbacks = []
        self._overlay_thread = None

    def register_lock_callback(self, fn):
        self._callbacks.append(fn)

    # ── PUBLIC ────────────────────────────────────────────────────────────────

    def lock(self, message: str = None, duration_minutes: int = None):
        if self.locked:
            return
        self.locked = True
        _lock_active.set()
        msg = message or self.cfg.lock_message
        log_event("LOCK", msg)
        logger.info("PC locked.")
        for cb in self._callbacks:
            try: cb("lock")
            except Exception: pass

        self._block_cad()
        self._install_hooks()

        self._overlay_thread = threading.Thread(
            target=self._show_overlay, args=(msg,), daemon=True, name="Overlay"
        )
        self._overlay_thread.start()

        if duration_minutes:
            threading.Thread(
                target=self._auto_unlock, args=(duration_minutes,), daemon=True
            ).start()

    def unlock(self, message: str = None):
        if not self.locked:
            return
        self.locked = False
        _lock_active.clear()
        log_event("UNLOCK", message or "Unlocked.")
        logger.info("PC unlocked.")
        for cb in self._callbacks:
            try: cb("unlock")
            except Exception: pass
        self._unblock_cad()
        self._remove_hooks()
        # overlay checks _lock_active and destroys itself

    def soft_lock(self):
        self._soft = True
        log_event("SOFTLOCK", "Games/YouTube blocked.")

    def soft_unlock(self):
        self._soft = False
        log_event("SOFTUNLOCK", "Soft lock off.")

    @property
    def status(self):
        return "locked" if self.locked else "unlocked"

    # ── INTERNAL ──────────────────────────────────────────────────────────────

    def _auto_unlock(self, minutes: int):
        time.sleep(minutes * 60)
        if self.locked:
            self.unlock(f"Auto-unlock after {minutes} min.")

    def _block_cad(self):
        """Disable Ctrl+Alt+Del via registry."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
                0, winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY
            )
            winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except Exception as e:
            logger.warning(f"CAD block failed: {e}")

    def _unblock_cad(self):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception:
            pass

    def _install_hooks(self):
        global _kb_hook, _ms_hook, _typed_buffer
        _typed_buffer.clear()
        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong)

        def kb_proc(nCode, wParam, lParam):
            if _lock_active.is_set():
                # Capture typed chars for password unlock
                try:
                    vk = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_ulong))[0]
                    if wParam == 0x0100:  # WM_KEYDOWN
                        _typed_buffer.append(vk)
                        # Keep last 20 chars
                        if len(_typed_buffer) > 20:
                            _typed_buffer.pop(0)
                        # Check password
                        typed = "".join(
                            chr(c).lower() for c in _typed_buffer
                            if 65 <= c <= 90 or 97 <= c <= 122
                        )
                        if UNLOCK_PASSWORD in typed:
                            _typed_buffer.clear()
                            threading.Thread(target=self.unlock, daemon=True).start()
                except Exception:
                    pass
                return 1  # block key
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        def ms_proc(nCode, wParam, lParam):
            if _lock_active.is_set():
                return 1  # block mouse
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        _kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, HOOKPROC(kb_proc), None, 0)
        _ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL,    HOOKPROC(ms_proc), None, 0)

        # Message pump to keep hooks alive
        def _pump():
            msg = ctypes.wintypes.MSG()
            while _lock_active.is_set():
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.01)

        threading.Thread(target=_pump, daemon=True).start()

    def _remove_hooks(self):
        global _kb_hook, _ms_hook
        try:
            if _kb_hook: user32.UnhookWindowsHookEx(_kb_hook); _kb_hook = None
            if _ms_hook: user32.UnhookWindowsHookEx(_ms_hook); _ms_hook = None
        except Exception as e:
            logger.warning(f"Hook remove failed: {e}")

    def _show_overlay(self, message: str):
        """Full-screen black overlay — all monitors — stays until unlock."""
        try:
            import tkinter as tk
            from tkinter import font as tkfont

            root = tk.Tk()
            root.withdraw()

            try:
                from screeninfo import get_monitors
                monitors = get_monitors()
            except Exception:
                monitors = None

            wins = []

            def make_win(x, y, w, h):
                win = tk.Toplevel(root)
                win.geometry(f"{w}x{h}+{x}+{y}")
                win.configure(bg="black")
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.lift()
                win.focus_force()

                f_title = tkfont.Font(family="Segoe UI", size=32, weight="bold")
                f_msg   = tkfont.Font(family="Segoe UI", size=18)
                f_sub   = tkfont.Font(family="Segoe UI", size=12)

                tk.Label(win, text="🔒  PC LOCKED",
                         font=f_title, fg="#ff4444", bg="black").pack(pady=(h//5, 20))
                tk.Label(win, text=message,
                         font=f_msg, fg="white", bg="black",
                         wraplength=w - 120).pack(pady=10)
                tk.Label(win, text="Contact your father to unlock.",
                         font=f_sub, fg="#666666", bg="black").pack(pady=8)

                wins.append(win)

            if monitors:
                for m in monitors:
                    make_win(m.x, m.y, m.width, m.height)
            else:
                make_win(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())

            def _check():
                if not _lock_active.is_set():
                    for w in wins:
                        try: w.destroy()
                        except Exception: pass
                    root.quit()
                    return
                # Keep on top
                for w in wins:
                    try: w.lift()
                    except Exception: pass
                root.after(400, _check)

            root.after(400, _check)
            root.mainloop()

        except Exception as e:
            logger.error(f"Overlay error: {e}")
