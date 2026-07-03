# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

import cv2

cv2_dir = os.path.dirname(cv2.__file__)

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

build_src = os.environ.get("STC_BUILD_SRC", "").strip()
if build_src:
    entry = str(Path(build_src) / "main.py")
    search_paths = [build_src]
else:
    entry = "main.py"
    search_paths = []

EXCLUDES = [
    "matplotlib",
    "scipy",
    "pandas",
    "pytest",
    "unittest",
    "test",
    "tests",
    "tkinter.test",
    "idlelib",
    "lib2to3",
    "pydoc",
    "pydoc_data",
    "xmlrpc",
    "curses",
    "setuptools",
    "distutils",
    "pip",
    "wheel",
]

HIDDEN_IMPORTS = [
    "win32gui",
    "win32con",
    "win32api",
    "win32process",
    "pywintypes",
    "PIL._tkinter_finder",
    "keyboard",
    "pyarmor_runtime_000000",
    "screen_target_clicker.app",
]

a = Analysis(
    [entry],
    pathex=search_paths,
    binaries=[],
    datas=opencv_config_datas,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure, cipher=None)

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
    disable_windowed_traceback=True,
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
