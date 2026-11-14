"""
PC Guardian — Lock Engine
Full-screen overlay, blocks all input, intercepts system keys
"""

import threading
import time
import ctypes
import logging
from logs.logger import log_event

logger = logging.getLogger("lock_engine")

# Windows API constants
SPI_SETSCREENSAVERRUNNING = 0x0061
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
VK_LWIN = 0x5B
VK_RWIN = 0x5C

_lock_active = threading.Event()
_overlay_thread = None
_keyboard_hook = None
_mouse_hook = None


class LockEngine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.locked = False
        self.lock_message = cfg.lock_message
        self.child_name = cfg.child_name
        self._overlay_thread = None
        self._countdown = None
        self._lock_callbacks = []

    def register_lock_callback(self, fn):
        self._lock_callbacks.append(fn)

    def lock(self, message: str = None, duration_minutes: int = None):
        if self.locked:
            return
        self.locked = True
        _lock_active.set()
        display_msg = message or self.lock_message
        log_event("LOCK", f"PC locked — {display_msg}")
        logger.info("PC locked.")

        for cb in self._lock_callbacks:
            try:
                cb("lock")
            except Exception:
                pass

        self._install_hooks()

        self._overlay_thread = threading.Thread(
            target=self._show_overlay,
            args=(display_msg,),
            daemon=True,
            name="LockOverlay"
        )
        self._overlay_thread.start()

        if duration_minutes:
            self._countdown = threading.Thread(
                target=self._auto_unlock,
                args=(duration_minutes,),
                daemon=True
            )
            self._countdown.start()

    def unlock(self):
        if not self.locked:
            return
        self.locked = False
        _lock_active.clear()
        log_event("UNLOCK", "PC unlocked.")
        logger.info("PC unlocked.")

        for cb in self._lock_callbacks:
            try:
                cb("unlock")
            except Exception:
                pass

        self._remove_hooks()
        self._destroy_overlay()

    def soft_lock(self):
        """Block games/YouTube but leave desktop accessible."""
        log_event("SOFTLOCK", "Soft lock enabled.")
        self._soft_locked = True

    def soft_unlock(self):
        self._soft_locked = False
        log_event("SOFTUNLOCK", "Soft lock disabled.")

    def _auto_unlock(self, minutes: int):
        time.sleep(minutes * 60)
        if self.locked:
            self.unlock()

    def _install_hooks(self):
        """Low-level keyboard/mouse hooks to block input."""
        try:
            import pywin32
        except ImportError:
            pass

        try:
            user32 = ctypes.windll.user32

            HOOKPROC = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong
            )

            def keyboard_proc(nCode, wParam, lParam):
                if _lock_active.is_set():
                    return 1  # Block all keys
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            def mouse_proc(nCode, wParam, lParam):
                if _lock_active.is_set():
                    return 1  # Block all mouse input
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            global _keyboard_hook, _mouse_hook
            _keyboard_hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, HOOKPROC(keyboard_proc), None, 0
            )
            _mouse_hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL, HOOKPROC(mouse_proc), None, 0
            )
        except Exception as e:
            logger.warning(f"Hook install failed: {e}")

    def _remove_hooks(self):
        try:
            user32 = ctypes.windll.user32
            global _keyboard_hook, _mouse_hook
            if _keyboard_hook:
                user32.UnhookWindowsHookEx(_keyboard_hook)
                _keyboard_hook = None
            if _mouse_hook:
                user32.UnhookWindowsHookEx(_mouse_hook)
                _mouse_hook = None
        except Exception as e:
            logger.warning(f"Hook remove failed: {e}")

    def _show_overlay(self, message: str):
        """Full-screen tkinter overlay covering all monitors."""
        try:
            import tkinter as tk
            from tkinter import font as tkfont

            root = tk.Tk()
            root.withdraw()

            # Detect all monitors
            try:
                from screeninfo import get_monitors
                monitors = get_monitors()
            except Exception:
                monitors = None

            windows = []

            def make_overlay(x, y, w, h):
                win = tk.Toplevel(root)
                win.geometry(f"{w}x{h}+{x}+{y}")
                win.configure(bg="black")
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.attributes("-fullscreen", True)
                win.grab_set()

                # Main message
                f1 = tkfont.Font(family="Segoe UI", size=28, weight="bold")
                f2 = tkfont.Font(family="Segoe UI", size=16)
                f3 = tkfont.Font(family="Segoe UI", size=13)

                tk.Label(
                    win, text="🔒 PC LOCKED", font=f1,
                    fg="#ff4444", bg="black"
                ).pack(pady=(h//4, 10))

                tk.Label(
                    win, text=message, font=f2,
                    fg="white", bg="black", wraplength=w - 100
                ).pack(pady=10)

                tk.Label(
                    win,
                    text=f"Contact your father to unlock this PC.",
                    font=f3, fg="#888888", bg="black"
                ).pack(pady=5)

                windows.append(win)
                return win

            if monitors:
                for m in monitors:
                    make_overlay(m.x, m.y, m.width, m.height)
            else:
                sw = root.winfo_screenwidth()
                sh = root.winfo_screenheight()
                make_overlay(0, 0, sw, sh)

            def check_unlock():
                if not _lock_active.is_set():
                    for w in windows:
                        try:
                            w.destroy()
                        except Exception:
                            pass
                    root.quit()
                    return
                root.after(500, check_unlock)

            root.after(500, check_unlock)
            root.mainloop()

        except Exception as e:
            logger.error(f"Overlay failed: {e}")

    def _destroy_overlay(self):
        # Signal via _lock_active being cleared — overlay checks this
        pass

    @property
    def status(self):
        return "locked" if self.locked else "unlocked"
