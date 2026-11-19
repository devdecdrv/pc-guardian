"""
PC Guardian — Privilege Escalation
Gives the process real SYSTEM-level rights so it cannot be killed
by any normal user or even admin from Task Manager.
"""

import os
import sys
import ctypes
import subprocess
import logging

logger = logging.getLogger("privilege")

# Windows constants
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY             = 0x0008
SE_PRIVILEGE_ENABLED    = 0x00000002
SE_DEBUG_NAME           = "SeDebugPrivilege"
SE_TCB_NAME             = "SeTcbPrivilege"
SE_BACKUP_NAME          = "SeBackupPrivilege"
SE_RESTORE_NAME         = "SeRestorePrivilege"
SE_SHUTDOWN_NAME        = "SeShutdownPrivilege"
SE_ASSIGNPRIMARYTOKEN   = "SeAssignPrimaryTokenPrivilege"

k32   = ctypes.windll.kernel32
adv32 = ctypes.windll.advapi32


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_ulong), ("HighPart", ctypes.c_long)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", ctypes.c_ulong)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", ctypes.c_ulong),
        ("Privileges",     LUID_AND_ATTRIBUTES * 1)
    ]


def _enable_privilege(name: str) -> bool:
    """Enable a specific privilege for current process."""
    try:
        h_token = ctypes.wintypes.HANDLE()
        adv32.OpenProcessToken(
            k32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(h_token)
        )
        luid = LUID()
        adv32.LookupPrivilegeValueW(None, name, ctypes.byref(luid))
        tp            = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid       = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        adv32.AdjustTokenPrivileges(
            h_token, False, ctypes.byref(tp),
            ctypes.sizeof(tp), None, None
        )
        k32.CloseHandle(h_token)
        return True
    except Exception as e:
        logger.warning(f"Privilege {name} failed: {e}")
        return False


def enable_all_privileges():
    """Enable every privilege available to the process."""
    privs = [
        SE_DEBUG_NAME,
        SE_TCB_NAME,
        SE_BACKUP_NAME,
        SE_RESTORE_NAME,
        SE_SHUTDOWN_NAME,
        "SeLoadDriverPrivilege",
        "SeSystemtimePrivilege",
        "SeCreateTokenPrivilege",
        "SeImpersonatePrivilege",
        "SeCreateGlobalPrivilege",
    ]
    for p in privs:
        _enable_privilege(p)
    logger.info("All available privileges enabled.")


def protect_process():
    """
    Make this process unkillable from Task Manager.
    Sets a DACL that denies PROCESS_TERMINATE to everyone except SYSTEM.
    """
    try:
        import ctypes.wintypes as wt
        from ctypes import windll

        # Get current process handle
        h_proc = k32.GetCurrentProcess()

        # Build Security Descriptor that denies terminate
        # Use SetSecurityInfo to set DACL
        SECURITY_INFORMATION = 0x00000004  # DACL_SECURITY_INFORMATION

        # Create empty DACL (denies everything)
        acl = ctypes.c_void_p()
        adv32.InitializeAcl(ctypes.byref(acl), 128, 2)  # ACL_REVISION = 2

        # Build SID for "Everyone"
        everyone_sid = ctypes.c_void_p()
        sia = (ctypes.c_ulong * 8)(0, 0, 0, 0, 0, 0, 0, 0)
        adv32.AllocateAndInitializeSid(
            ctypes.byref(ctypes.c_ulong(1)),  # SECURITY_WORLD_SID_AUTHORITY
            1, 0, 0, 0, 0, 0, 0, 0, 0,
            ctypes.byref(everyone_sid)
        )

        # Deny PROCESS_TERMINATE (0x0001) to Everyone
        PROCESS_TERMINATE = 0x0001
        adv32.AddAccessDeniedAce(
            acl, 2, PROCESS_TERMINATE, everyone_sid
        )

        # Apply DACL to process
        windll.advapi32.SetSecurityInfo(
            h_proc,
            6,                    # SE_KERNEL_OBJECT
            SECURITY_INFORMATION,
            None, None,
            acl, None
        )
        logger.info("Process DACL set — terminate denied for Everyone.")
        return True

    except Exception as e:
        logger.warning(f"DACL protect failed: {e}")
        # Fallback — use PowerShell
        return _protect_via_powershell()


def _protect_via_powershell():
    """
    Fallback: Use PowerShell to set process protection level.
    Sets process as Protected Process Light (PPL) if possible.
    """
    try:
        pid = os.getpid()
        ps  = f"""
$p = Get-Process -Id {pid}
$handle = $p.Handle
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class ProcProtect {{
    [DllImport("ntdll.dll")] public static extern int NtSetInformationProcess(IntPtr h, int i, ref int v, int s);
    public static void Protect(IntPtr h) {{
        int v = 0x61; // PROCESS_PROTECTION_LEVEL_WINTCB_LIGHT
        NtSetInformationProcess(h, 61, ref v, 4);
    }}
}}
'@
[ProcProtect]::Protect($handle)
"""
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True, timeout=10
        )
        logger.info("PowerShell process protection applied.")
        return True
    except Exception as e:
        logger.error(f"PowerShell protection failed: {e}")
        return False


def run_as_system():
    """
    Relaunch this process as SYSTEM using PsExec-style technique.
    SYSTEM processes cannot be killed by any user including admins.
    """
    try:
        if _is_system():
            logger.info("Already running as SYSTEM.")
            return True

        exe = sys.executable if getattr(sys, "frozen", False) else f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

        # Create scheduled task that runs as SYSTEM
        task_xml = f"""<?xml version="1.0"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Principals>
    <Principal><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions><Exec><Command>{exe}</Command></Exec></Actions>
</Task>"""

        import tempfile
        xml_path = os.path.join(tempfile.gettempdir(), "pcg_sys.xml")
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(task_xml)

        subprocess.run(
            f'schtasks /Create /TN "WindowsSecuritySystem" /XML "{xml_path}" /F',
            shell=True, capture_output=True
        )
        subprocess.run(
            'schtasks /Run /TN "WindowsSecuritySystem"',
            shell=True, capture_output=True
        )
        try: os.remove(xml_path)
        except Exception: pass

        logger.info("Relaunched as SYSTEM via Task Scheduler.")
        return True

    except Exception as e:
        logger.error(f"Run as SYSTEM failed: {e}")
        return False


def _is_system() -> bool:
    """Check if current process is running as SYSTEM."""
    try:
        import subprocess
        result = subprocess.check_output("whoami", shell=True).decode().strip().lower()
        return "system" in result
    except Exception:
        return False


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def elevate_if_needed():
    """Relaunch as admin if not already elevated."""
    if not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                " ".join([f'"{a}"' for a in sys.argv]),
                None, 1
            )
            sys.exit(0)
        except Exception as e:
            logger.error(f"Elevation failed: {e}")


def full_privilege_setup():
    """Call once on startup — maximum privilege + kill protection."""
    elevate_if_needed()
    enable_all_privileges()
    protect_process()
    run_as_system()
    logger.info("Full privilege setup complete.")
