# PCGuard driver build script v4
$ErrorActionPreference = "Stop"

# Find cl.exe
$vswhere  = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath   = & $vswhere -latest -products * -requires Microsoft.VisualCpp.Tools.HostX64.TargetX64 -property installationPath
$msvcVer  = Get-ChildItem "$vsPath\VC\Tools\MSVC" | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name
$msvcBase = "$vsPath\VC\Tools\MSVC\$msvcVer"
$clPath   = "$msvcBase\bin\HostX64\x64\cl.exe"
$linkPath = "$msvcBase\bin\HostX64\x64\link.exe"

$wdkBase = "C:\Program Files (x86)\Windows Kits\10"
$wdkVer  = "10.0.22621.0"
$wdkInc  = "$wdkBase\Include\$wdkVer"
$wdkLib  = "$wdkBase\Lib\$wdkVer"

# Debug — list everything
Write-Host "=== INCLUDE FOLDERS ==="
Get-ChildItem $wdkInc | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host "ntdef.h in shared: $(Test-Path $wdkInc\shared\ntdef.h)"
Write-Host "ntdef.h in km:     $(Test-Path $wdkInc\km\ntdef.h)"
Write-Host "ntdef.h in um:     $(Test-Path $wdkInc\um\ntdef.h)"
Write-Host "MSVC include: $msvcBase\include"
Write-Host "excpt.h: $(Test-Path $msvcBase\include\excpt.h)"

New-Item -ItemType Directory -Force -Path build_drv | Out-Null
Copy-Item pc-guardian\driver\PCGuard.cpp build_drv\
Copy-Item pc-guardian\driver\PCGuard.h   build_drv\
Push-Location build_drv

# Use short 8.3 paths to avoid space issues entirely
$wdkIncShort  = (New-Object -ComObject Scripting.FileSystemObject).GetFolder($wdkInc).ShortPath
$msvcIncShort = (New-Object -ComObject Scripting.FileSystemObject).GetFolder("$msvcBase\include").ShortPath
$wdkLibShort  = (New-Object -ComObject Scripting.FileSystemObject).GetFolder("$wdkLib\km\x64").ShortPath

Write-Host "WDK Inc short:  $wdkIncShort"
Write-Host "MSVC Inc short: $msvcIncShort"

# Build response file with short paths
@"
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
/I$wdkIncShort\km
/I$wdkIncShort\shared
/I$msvcIncShort
/c
PCGuard.cpp
"@ | Out-File -FilePath cl.rsp -Encoding ascii

Write-Host "=== cl.rsp contents ==="
Get-Content cl.rsp

Write-Host "=== Compiling ==="
& "$clPath" "@cl.rsp"
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "Compile failed"; exit 1 }

Write-Host "=== Linking ==="
& "$linkPath" `
  /DRIVER /SUBSYSTEM:NATIVE /ENTRY:DriverEntry /NODEFAULTLIB `
  /MACHINE:X64 `
  /LIBPATH:$wdkLibShort `
  ntoskrnl.lib hal.lib wdm.lib wdmsec.lib `
  /OUT:PCGuard.sys `
  PCGuard.obj

if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "Link failed"; exit 1 }
Pop-Location

if (Test-Path build_drv\PCGuard.sys) {
  Write-Host "SUCCESS: $($(Get-Item build_drv\PCGuard.sys).Length) bytes"
} else {
  Write-Error "PCGuard.sys missing"; exit 1
}
