"""
PC Guardian — First Run Setup
GUI window for credential input (works with --noconsole exe)
"""

import os
import sys
import ctypes
import subprocess
import time
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.enc")
SETUP_FLAG     = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".setup_done")
DELETE_PASSWORD = "DECDRV"


def needs_setup() -> bool:
    return not os.path.exists(CONFIG_PATH) or not os.path.exists(SETUP_FLAG)


def run_first_setup():
    """Dark GUI setup window — appears once on first run."""

    result = {}

    root = tk.Tk()
    root.title("PC Guardian — First Time Setup")
    root.configure(bg="#0d0d0d")
    root.resizable(False, False)

    # Center window
    w, h = 520, 620
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    root.attributes("-topmost", True)

    # Fonts
    import tkinter.font as tkf
    f_title = tkf.Font(family="Segoe UI", size=16, weight="bold")
    f_label = tkf.Font(family="Segoe UI", size=10)
    f_small = tkf.Font(family="Segoe UI", size=9)

    # ── Header ────────────────────────────────────────────────────────────────
    tk.Label(root, text="🛡  PC GUARDIAN SETUP",
             font=f_title, fg="#58a6ff", bg="#0d0d0d").pack(pady=(24, 4))
    tk.Label(root, text="Fill in your details to activate. This screen appears only once.",
             font=f_small, fg="#666666", bg="#0d0d0d").pack(pady=(0, 20))

    # ── Fields ────────────────────────────────────────────────────────────────
    fields = {}

    def add_field(label, hint="", secret=False, default=""):
        frame = tk.Frame(root, bg="#0d0d0d")
        frame.pack(fill="x", padx=40, pady=6)
        tk.Label(frame, text=label, font=f_label,
                 fg="#e6edf3", bg="#0d0d0d", anchor="w").pack(fill="x")
        if hint:
            tk.Label(frame, text=hint, font=f_small,
                     fg="#555555", bg="#0d0d0d", anchor="w").pack(fill="x")
        entry = tk.Entry(frame, bg="#161b22", fg="#e6edf3",
                         insertbackground="white", relief="flat",
                         font=f_label, bd=0, highlightthickness=1,
                         highlightcolor="#30363d", highlightbackground="#30363d",
                         show="●" if secret else "")
        entry.pack(fill="x", ipady=8, pady=(4, 0))
        entry.insert(0, default)
        return entry

    fields["token"]    = add_field("Telegram Bot Token",
                                    "→ @BotFather on Telegram → /newbot → copy token")
    fields["uid"]      = add_field("Your Telegram User ID",
                                    "→ @userinfobot on Telegram → copy the number")
    fields["child"]    = add_field("Child's Name", default="Son")
    fields["keyword"]  = add_field("Lock Keyword (type this anywhere to lock)",
                                    default="lockson")
    fields["password"] = add_field("Uninstall Password", secret=True)
    fields["confirm"]  = add_field("Confirm Password", secret=True)

    # ── Error label ───────────────────────────────────────────────────────────
    err_var = tk.StringVar()
    tk.Label(root, textvariable=err_var, font=f_small,
             fg="#ff6b6b", bg="#0d0d0d").pack(pady=(4, 0))

    # ── Save button ───────────────────────────────────────────────────────────
    def on_save():
        token   = fields["token"].get().strip()
        uid     = fields["uid"].get().strip()
        child   = fields["child"].get().strip() or "Son"
        keyword = fields["keyword"].get().strip() or "lockson"
        pw1     = fields["password"].get().strip()
        pw2     = fields["confirm"].get().strip()

        if len(token) < 20 or ":" not in token:
            err_var.set("⚠ Invalid bot token.")
            return
        if not uid.isdigit():
            err_var.set("⚠ User ID must be numbers only.")
            return
        if len(pw1) < 4:
            err_var.set("⚠ Password must be at least 4 characters.")
            return
        if pw1 != pw2:
            err_var.set("⚠ Passwords do not match.")
            return

        err_var.set("")
        result["ok"]      = True
        result["token"]   = token
        result["uid"]     = int(uid)
        result["child"]   = child
        result["keyword"] = keyword
        result["pw"]      = pw1
        root.quit()

    btn = tk.Button(root, text="Activate PC Guardian →",
                    font=f_label, bg="#238636", fg="white",
                    activebackground="#2ea043", activeforeground="white",
                    relief="flat", cursor="hand2", bd=0,
                    command=on_save)
    btn.pack(fill="x", padx=40, pady=(16, 8), ipady=10)

    root.mainloop()
    root.destroy()

    if not result.get("ok"):
        sys.exit(0)

    # ── Save encrypted config ─────────────────────────────────────────────────
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config"), exist_ok=True)

    from config.crypto import encrypt_config
    encrypt_config({
        "bot_token":          result["token"],
        "allowed_user_id":    result["uid"],
        "uninstall_password": result["pw"],
        "lock_keyword":       result["keyword"],
        "child_name":         result["child"],
        "lock_message":       f"Take a breath {result['child']}. Dad is watching.",
        "daily_report_time":  "21:00",
        "school_schedule":    {"enabled": False, "lock_time": "08:00", "unlock_time": "15:00"},
        "bedtime_schedule":   {"enabled": False, "lock_time": "21:00", "unlock_time": "16:00"},
        "panic_detection":    {"voice_enabled": True, "behavior_enabled": True, "volume_threshold": 0.7},
        "web_dashboard":      {"enabled": True, "port": 8080, "password": result["pw"]},
        "camera_enabled":     True,
        "mic_enabled":        True,
        "speaker_enabled":    True,
        "anthropic_api_key":  "",
    })

    with open(SETUP_FLAG, "w") as f:
        f.write("1")

    protect_from_deletion()


def change_credentials():
    """Change any credential — password protected GUI."""

    root = tk.Tk()
    root.title("PC Guardian — Change Credentials")
    root.configure(bg="#0d0d0d")
    root.resizable(False, False)

    w, h = 480, 400
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    root.attributes("-topmost", True)

    import tkinter.font as tkf
    f_title = tkf.Font(family="Segoe UI", size=14, weight="bold")
    f_label = tkf.Font(family="Segoe UI", size=10)
    f_small = tkf.Font(family="Segoe UI", size=9)

    tk.Label(root, text="🔑  CHANGE CREDENTIALS",
             font=f_title, fg="#58a6ff", bg="#0d0d0d").pack(pady=(24, 16))

    # ── Password verify first ─────────────────────────────────────────────────
    frame1 = tk.Frame(root, bg="#0d0d0d")
    frame1.pack(fill="x", padx=40, pady=6)
    tk.Label(frame1, text="Current Password", font=f_label,
             fg="#e6edf3", bg="#0d0d0d", anchor="w").pack(fill="x")
    pw_entry = tk.Entry(frame1, bg="#161b22", fg="#e6edf3",
                        insertbackground="white", relief="flat",
                        font=f_label, bd=0, highlightthickness=1,
                        highlightcolor="#30363d", highlightbackground="#30363d",
                        show="●")
    pw_entry.pack(fill="x", ipady=8, pady=(4, 0))

    err_var = tk.StringVar()
    tk.Label(root, textvariable=err_var, font=f_small,
             fg="#ff6b6b", bg="#0d0d0d").pack(pady=4)

    fields_frame = tk.Frame(root, bg="#0d0d0d")

    new_fields = {}

    def on_verify():
        try:
            from config.crypto import decrypt_config
            cfg = decrypt_config()
        except Exception:
            err_var.set("⚠ No config found.")
            return

        if pw_entry.get().strip() != cfg.get("uninstall_password", ""):
            err_var.set("⚠ Wrong password.")
            return

        err_var.set("")
        frame1.pack_forget()

        # Show change fields
        fields_frame.pack(fill="x", padx=40)

        def add_f(label, default="", secret=False):
            f = tk.Frame(fields_frame, bg="#0d0d0d")
            f.pack(fill="x", pady=4)
            tk.Label(f, text=label, font=f_label,
                     fg="#e6edf3", bg="#0d0d0d", anchor="w").pack(fill="x")
            e = tk.Entry(f, bg="#161b22", fg="#e6edf3",
                         insertbackground="white", relief="flat",
                         font=f_label, bd=0, highlightthickness=1,
                         highlightcolor="#30363d", highlightbackground="#30363d",
                         show="●" if secret else "")
            e.pack(fill="x", ipady=7, pady=(3, 0))
            e.insert(0, default)
            return e

        new_fields["token"]    = add_f("Bot Token (leave blank to keep)", default="")
        new_fields["uid"]      = add_f("User ID (leave blank to keep)", default="")
        new_fields["child"]    = add_f("Child Name", default=cfg.get("child_name", "Son"))
        new_fields["keyword"]  = add_f("Lock Keyword", default=cfg.get("lock_keyword", "lockson"))
        new_fields["new_pw"]   = add_f("New Password (leave blank to keep)", secret=True)

        def on_save():
            from config.crypto import decrypt_config, encrypt_config
            cfg2 = decrypt_config()

            t  = new_fields["token"].get().strip()
            u  = new_fields["uid"].get().strip()
            ch = new_fields["child"].get().strip()
            kw = new_fields["keyword"].get().strip()
            np = new_fields["new_pw"].get().strip()

            if t:  cfg2["bot_token"]       = t
            if u and u.isdigit(): cfg2["allowed_user_id"] = int(u)
            if ch: cfg2["child_name"]      = ch
            if kw: cfg2["lock_keyword"]    = kw
            if np and len(np) >= 4:
                cfg2["uninstall_password"] = np
                cfg2["web_dashboard"]["password"] = np

            encrypt_config(cfg2)
            messagebox.showinfo("Done", "Credentials updated.\nRestart PC Guardian to apply.")
            root.quit()
            root.destroy()

        tk.Button(fields_frame, text="Save Changes",
                  font=f_label, bg="#238636", fg="white",
                  activebackground="#2ea043", relief="flat",
                  cursor="hand2", bd=0, command=on_save
                  ).pack(fill="x", pady=(12, 0), ipady=9)

    tk.Button(root, text="Verify Password →",
              font=f_label, bg="#1f6feb", fg="white",
              activebackground="#388bfd", relief="flat",
              cursor="hand2", bd=0, command=on_verify
              ).pack(fill="x", padx=40, pady=(0, 8), ipady=9)

    root.mainloop()
    try: root.destroy()
    except Exception: pass


def protect_from_deletion():
    """Block delete permission on exe and config folder."""
    try:
        exe        = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
        subprocess.run(f'icacls "{exe}" /deny Everyone:(D)', shell=True, capture_output=True)
        subprocess.run(f'icacls "{config_dir}" /deny Everyone:(D,DC)', shell=True, capture_output=True)
    except Exception:
        pass


if __name__ == "__main__":
    if "--change" in sys.argv:
        change_credentials()
    else:
        if needs_setup():
            run_first_setup()
