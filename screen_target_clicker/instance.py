"""Helpers for running multiple app instances side by side."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import win32gui

TITLE_PREFIX = "Screen Target Clicker"
DEFAULT_HOTKEYS = ("f6", "f7", "f8", "f9", "f10", "f11", "f12")


def count_running_instances() -> int:
    """Count visible windows that belong to this app."""
    total = 0

    def callback(hwnd: int, _: object) -> bool:
        nonlocal total
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if title == TITLE_PREFIX or title.startswith(f"{TITLE_PREFIX} ("):
            total += 1
        return True

    win32gui.EnumWindows(callback, None)
    return total


def instance_number() -> int:
    """1-based instance id for a newly opening window."""
    return count_running_instances() + 1


def window_title_for_instance(number: int) -> str:
    if number <= 1:
        return TITLE_PREFIX
    return f"{TITLE_PREFIX} ({number})"


def default_hotkey_for_instance(number: int) -> str:
    index = max(0, number - 1)
    if index < len(DEFAULT_HOTKEYS):
        return DEFAULT_HOTKEYS[index]
    return DEFAULT_HOTKEYS[-1]


def launch_another_instance() -> None:
    """Start a separate process running the same app."""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
        cwd = Path(sys.executable).resolve().parent
    else:
        project_root = Path(__file__).resolve().parents[1]
        cmd = [sys.executable, str(project_root / "main.py")]
        cwd = project_root

    subprocess.Popen(
        cmd,
        cwd=cwd,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
