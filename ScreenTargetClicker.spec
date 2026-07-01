# -*- mode: python ; coding: utf-8 -*-
import os
import sys

import cv2

cv2_dir = os.path.dirname(cv2.__file__)

# OpenCV loads these from disk at runtime; they must exist next to cv2/__init__.py.
opencv_config_datas = []
for fname in [
    "config.py",
    "config-3.py",
    f"config-{sys.version_info[0]}.{sys.version_info[1]}.py",
    "load_config_py3.py",
]:
    fpath = os.path.join(cv2_dir, fname)
    if os.path.isfile(fpath):
        opencv_config_datas.append((fpath, "cv2"))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=opencv_config_datas,
    hiddenimports=[
        "win32gui",
        "win32con",
        "pywintypes",
        "PIL._tkinter_finder",
        "keyboard",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ScreenTargetClicker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ScreenTargetClicker",
)
