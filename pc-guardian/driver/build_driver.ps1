# PCGuard driver build script
# Called by GitHub Actions

$ErrorActionPreference = "Stop"

# Find cl.exe
$vswhere  = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath   = & $vswhere -latest -products * -requires Microsoft.VisualCpp.Tools.HostX64.TargetX64 -property installationPath
$msvcVer  = Get-ChildItem "$vsPath\VC\Tools\MSVC" | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name
$msvcBase = "$vsPath\VC\Tools\MSVC\$msvcVer"
$clPath   = "$msvcBase\bin\HostX64\x64\cl.exe"
$linkPath = "$msvcBase\bin\HostX64\x64\link.exe"

$wdkInc  = "C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0"
$wdkLib  = "C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22621.0"

Write-Host "cl.exe:    $clPath"
Write-Host "WDK inc:   $wdkInc"
Write-Host "ntddk.h:   $(Test-Path $wdkInc\km\ntddk.h)"
Write-Host "MSVC inc:  $msvcBase\include"

New-Item -ItemType Directory -Force -Path build_drv | Out-Null
Copy-Item pc-guardian\driver\PCGuard.cpp build_drv\
Copy-Item pc-guardian\driver\PCGuard.h   build_drv\

# Write a response file — avoids all quoting issues with spaces in paths
$rspContent = @"
/nologo
/kernel
/GS-
/W3
/WX-
/Gz
/GF
/EHsc
/Zp8
/GR-
/Zl
/D_AMD64_
/DNTDDI_VERSION=0x0A000007
/D_WIN32_WINNT=0x0A00
/DWIN32=100
/DDBG
/I"$wdkInc\km"
/I"$wdkInc\shared"
/I"$msvcBase\include"
/c
build_drv\PCGuard.cpp
"@

$rspPath = "$env:TEMP\pcguard_cl.rsp"
$rspContent | Out-File -FilePath $rspPath -Encoding ascii
Write-Host "Response file: $rspPath"
Get-Content $rspPath

# Compile using response file
& "$clPath" "@$rspPath"
if ($LASTEXITCODE -ne 0) { Write-Error "Compile failed"; exit 1 }

# Link
$objPath  = "PCGuard.obj"
$libPath  = "$wdkLib\km\x64"
Move-Item build_drv\PCGuard.obj . -Force -ErrorAction SilentlyContinue

& "$linkPath" `
  /DRIVER /SUBSYSTEM:NATIVE /ENTRY:DriverEntry /NODEFAULTLIB `
  /MACHINE:X64 `
  /LIBPATH:"$libPath" `
  ntoskrnl.lib hal.lib wdm.lib wdmsec.lib `
  /OUT:build_drv\PCGuard.sys `
  PCGuard.obj

if ($LASTEXITCODE -ne 0) { Write-Error "Link failed"; exit 1 }

if (Test-Path build_drv\PCGuard.sys) {
    Write-Host "SUCCESS: PCGuard.sys $($(Get-Item build_drv\PCGuard.sys).Length) bytes"
} else {
    Write-Error "PCGuard.sys not found"; exit 1
}# PCGuard driver build script
# Called by GitHub Actions

$ErrorActionPreference = "Stop"

# Find cl.exe
$vswhere  = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath   = & $vswhere -latest -products * -requires Microsoft.VisualCpp.Tools.HostX64.TargetX64 -property installationPath
$msvcVer  = Get-ChildItem "$vsPath\VC\Tools\MSVC" | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name
$msvcBase = "$vsPath\VC\Tools\MSVC\$msvcVer"
$clPath   = "$msvcBase\bin\HostX64\x64\cl.exe"
$linkPath = "$msvcBase\bin\HostX64\x64\link.exe"

$wdkInc  = "C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0"
$wdkLib  = "C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22621.0"

Write-Host "cl.exe:    $clPath"
Write-Host "WDK inc:   $wdkInc"
Write-Host "ntddk.h:   $(Test-Path $wdkInc\km\ntddk.h)"
Write-Host "MSVC inc:  $msvcBase\include"

New-Item -ItemType Directory -Force -Path build_drv | Out-Null
Copy-Item pc-guardian\driver\PCGuard.cpp build_drv\
Copy-Item pc-guardian\driver\PCGuard.h   build_drv\

# Write a response file — avoids all quoting issues with spaces in paths
$rspContent = @"
/nologo
/kernel
/GS-
/W3
/WX-
/Gz
/GF
/EHsc
/Zp8
/GR-
/Zl
/D_AMD64_
/DNTDDI_VERSION=0x0A000007
/D_WIN32_WINNT=0x0A00
/DWIN32=100
/DDBG
/I"$wdkInc\km"
/I"$wdkInc\shared"
/I"$msvcBase\include"
/c
build_drv\PCGuard.cpp
"@

$rspPath = "$env:TEMP\pcguard_cl.rsp"
$rspContent | Out-File -FilePath $rspPath -Encoding ascii
Write-Host "Response file: $rspPath"
Get-Content $rspPath

# Compile using response file
& "$clPath" "@$rspPath"
if ($LASTEXITCODE -ne 0) { Write-Error "Compile failed"; exit 1 }

# Link
$objPath  = "PCGuard.obj"
$libPath  = "$wdkLib\km\x64"
Move-Item build_drv\PCGuard.obj . -Force -ErrorAction SilentlyContinue

& "$linkPath" `
  /DRIVER /SUBSYSTEM:NATIVE /ENTRY:DriverEntry /NODEFAULTLIB `
  /MACHINE:X64 `
  /LIBPATH:"$libPath" `
  ntoskrnl.lib hal.lib wdm.lib wdmsec.lib `
  /OUT:build_drv\PCGuard.sys `
  PCGuard.obj

if ($LASTEXITCODE -ne 0) { Write-Error "Link failed"; exit 1 }

if (Test-Path build_drv\PCGuard.sys) {
    Write-Host "SUCCESS: PCGuard.sys $($(Get-Item build_drv\PCGuard.sys).Length) bytes"
} else {
    Write-Error "PCGuard.sys not found"; exit 1
}
