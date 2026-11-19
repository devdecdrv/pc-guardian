/*
 * PCGuard.h — PC Guardian Kernel Driver Header
 */

#pragma once

#include <ntddk.h>

// IOCTL codes
#define PCGUARD_DEVICE_TYPE     FILE_DEVICE_UNKNOWN
#define IOCTL_SET_PID   CTL_CODE(PCGUARD_DEVICE_TYPE, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_UNLOAD    CTL_CODE(PCGUARD_DEVICE_TYPE, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

// Device paths
#define DEVICE_NAME_STR     "\\\\.\\PCGuard"
#define DEVICE_NAME         L"\\Device\\PCGuard"
#define SYMBOLIC_LINK       L"\\DosDevices\\PCGuard"

// Password
#define DRIVER_PASSWORD     L"DECDRV"

// VM_COUNTERS (needed for SYSTEM_PROCESS_INFORMATION)
typedef struct _VM_COUNTERS {
    SIZE_T PeakVirtualSize;
    SIZE_T VirtualSize;
    ULONG  PageFaultCount;
    SIZE_T PeakWorkingSetSize;
    SIZE_T WorkingSetSize;
    SIZE_T QuotaPeakPagedPoolUsage;
    SIZE_T QuotaPagedPoolUsage;
    SIZE_T QuotaPeakNonPagedPoolUsage;
    SIZE_T QuotaNonPagedPoolUsage;
    SIZE_T PagefileUsage;
    SIZE_T PeakPagefileUsage;
} VM_COUNTERS, *PVM_COUNTERS;
