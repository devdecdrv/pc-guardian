"""
PC Guardian — Build Script
Compiles to single .exe via PyInstaller
Run: python build/build.py
"""

import os
import sys
import subprocess
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build_output")
SPEC = os.path.join(ROOT, "build", "pcguardian.spec")
ICON = os.path.join(ROOT, "assets", "icon.ico")
MAIN = os.path.join(ROOT, "main.py")


def build():
    print("Building PC Guardian...")

    # Clean previous build
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    if os.path.exists(BUILD):
        shutil.rmtree(BUILD)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "pc-guardian",
        "--distpath", DIST,
        "--workpath", BUILD,
        "--add-data", f"{os.path.join(ROOT, 'assets')};assets",
        "--add-data", f"{os.path.join(ROOT, 'dashboard', 'templates')};dashboard/templates",
        "--add-data", f"{os.path.join(ROOT, 'dashboard', 'static')};dashboard/static",
        "--hidden-import", "pynput.keyboard._win32",
        "--hidden-import", "pynput.mouse._win32",
        "--hidden-import", "win32api",
        "--hidden-import", "win32con",
        "--hidden-import", "win32gui",
    ]

    if os.path.exists(ICON):
        cmd += ["--icon", ICON]

    cmd.append(MAIN)

    result = subprocess.run(cmd, cwd=ROOT)

    if result.returncode == 0:
        exe = os.path.join(DIST, "pc-guardian.exe")
        print(f"\n✓ Build successful: {exe}")
        print(f"  Size: {os.path.getsize(exe) / 1024 / 1024:.1f} MB")
    else:
        print("\n✗ Build failed.")
        sys.exit(1)


if __name__ == "__main__":
    build()
