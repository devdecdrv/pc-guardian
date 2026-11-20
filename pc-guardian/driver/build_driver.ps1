$ErrorActionPreference = "Stop"

# Find cl.exe
$vswhere  = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath   = & $vswhere -latest -products * -requires Microsoft.VisualCpp.Tools.HostX64.TargetX64 -property installationPath
$msvcVer  = Get-ChildItem "$vsPath\VC\Tools\MSVC" | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name
$msvcBase = "$vsPath\VC\Tools\MSVC\$msvcVer"
$clPath   = "$msvcBase\bin\HostX64\x64\cl.exe"
$linkPath = "$msvcBase\bin\HostX64\x64\link.exe"

# Exhaustive ntdef.h search
Write-Host "=== Searching for ntdef.h ==="
Get-ChildItem "C:\Program Files (x86)\Windows Kits" -Recurse -Filter "ntdef.h" -ErrorAction SilentlyContinue |
  Select-Object -First 10 | ForEach-Object { Write-Host "FOUND: $($_.FullName)" }

Write-Host "=== Searching for ntddk.h ==="
Get-ChildItem "C:\Program Files (x86)\Windows Kits" -Recurse -Filter "ntddk.h" -ErrorAction SilentlyContinue |
  Select-Object -First 10 | ForEach-Object { Write-Host "FOUND: $($_.FullName)" }

Write-Host "=== WDK Include folders ==="
Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\Include" -ErrorAction SilentlyContinue |
  ForEach-Object {
    Write-Host "  $($_.Name)"
    Get-ChildItem $_.FullName -ErrorAction SilentlyContinue | ForEach-Object {
      Write-Host "    $($_.Name)"
    }
  }

Write-Host "=== MSVC include ==="
Write-Host "excpt.h: $(Test-Path $msvcBase\include\excpt.h)"
Write-Host "ntdef.h in MSVC: $(Test-Path $msvcBase\include\ntdef.h)"
