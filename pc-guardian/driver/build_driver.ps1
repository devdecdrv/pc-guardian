# PCGuard driver build script v6
# ntdef.h explicitly included in PCGuard.cpp now
$ErrorActionPreference = "Stop"

$vswhere  = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath   = & $vswhere -latest -products * -requires Microsoft.VisualCpp.Tools.HostX64.TargetX64 -property installationPath
$msvcVer  = Get-ChildItem "$vsPath\VC\Tools\MSVC" | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name
$msvcBase = "$vsPath\VC\Tools\MSVC\$msvcVer"
$clPath   = "$msvcBase\bin\HostX64\x64\cl.exe"
$linkPath = "$msvcBase\bin\HostX64\x64\link.exe"

$wdkBase = "C:\Program Files (x86)\Windows Kits\10"
$wdkVer  = "10.0.22621.0"
$wdkInc  = "$wdkBase\Include\$wdkVer"
$wdkLib  = "$wdkBase\Lib\$wdkVer\km\x64"

# Short path helper — avoids spaces
function Short([string]$p) {
    $fso = New-Object -ComObject Scripting.FileSystemObject
    if (Test-Path $p -PathType Container) { return $fso.GetFolder($p).ShortPath }
    return $fso.GetFile($p).ShortPath
}

$kmShort     = Short "$wdkInc\km"
$sharedShort = Short "$wdkInc\shared"
$msvcShort   = Short "$msvcBase\include"
$clShort     = Short $clPath
$linkShort   = Short $linkPath
$libShort    = Short $wdkLib

Write-Host "km:     $kmShort"
Write-Host "shared: $sharedShort"
Write-Host "msvc:   $msvcShort"
Write-Host "ntdef.h: $(Test-Path $wdkInc\shared\ntdef.h)"

New-Item -ItemType Directory -Force -Path build_drv | Out-Null
Copy-Item pc-guardian\driver\PCGuard.cpp build_drv\PCGuard.cpp -Force
Copy-Item pc-guardian\driver\PCGuard.h   build_drv\PCGuard.h   -Force
Push-Location build_drv

# Response file — no quotes, short paths, one arg per line
$rsp = @"
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
/I$kmShort
/I$sharedShort
/I$msvcShort
/c
PCGuard.cpp
"@

$rsp | Set-Content cl.rsp -Encoding ASCII
Write-Host "--- cl.rsp ---"
Get-Content cl.rsp

Write-Host "--- Compile ---"
& $clShort "@cl.rsp"
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "Compile failed"; exit 1 }

Write-Host "--- Link ---"
& $linkShort /DRIVER /SUBSYSTEM:NATIVE /ENTRY:DriverEntry /NODEFAULTLIB `
  /MACHINE:X64 /LIBPATH:$libShort `
  ntoskrnl.lib hal.lib wdm.lib wdmsec.lib `
  /OUT:PCGuard.sys PCGuard.obj
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "Link failed"; exit 1 }

Pop-Location

if (Test-Path build_drv\PCGuard.sys) {
    Write-Host "SUCCESS: $($(Get-Item build_drv\PCGuard.sys).Length) bytes"
} else {
    Write-Error "PCGuard.sys missing"; exit 1
}
