"""Window enumeration and screenshot capture on Windows."""

from __future__ import annotations

import time

import win32api
import win32con
import win32gui
import win32process
import mss
import numpy as np
import cv2


def list_visible_windows() -> list[tuple[int, str]]:
    """Return (hwnd, title) pairs for visible windows with non-empty titles."""
    windows: list[tuple[int, str]] = []

    def callback(hwnd: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.IsIconic(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if title.strip():
            windows.append((hwnd, title))
        return True

    win32gui.EnumWindows(callback, None)
    windows.sort(key=lambda item: item[1].lower())
    return windows


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) for a window."""
    return win32gui.GetWindowRect(hwnd)


def get_foreground_hwnd() -> int:
    return win32gui.GetForegroundWindow()


def is_window_alive(hwnd: int) -> bool:
    return bool(hwnd) and win32gui.IsWindow(hwnd)


def bring_window_to_front(hwnd: int) -> None:
    """Try to restore and focus a window."""
    focus_target_window(hwnd)


def focus_target_window(hwnd: int, *, settle_sec: float = 0.12) -> bool:
    """
    Bring the target window to the foreground.

    Returns True when that window is the active foreground window.
    """
    if not is_window_alive(hwnd):
        return False

    if win32gui.GetForegroundWindow() == hwnd:
        return True

    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    try:
        win32gui.SetForegroundWindow(hwnd)
    except win32gui.error:
        _force_foreground(hwnd)

    if settle_sec > 0:
        time.sleep(settle_sec)

    return win32gui.GetForegroundWindow() == hwnd


def _force_foreground(hwnd: int) -> None:
    """Fallback when SetForegroundWindow is blocked by the OS."""
    foreground = win32gui.GetForegroundWindow()
    if foreground == hwnd:
        return

    current_thread = win32api.GetCurrentThreadId()
    fg_thread, _ = win32process.GetWindowThreadProcessId(foreground)
    target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)

    attached_fg = False
    attached_target = False
    try:
        if fg_thread and fg_thread != current_thread:
            win32process.AttachThreadInput(current_thread, fg_thread, True)
            attached_fg = True
        if target_thread and target_thread != current_thread:
            win32process.AttachThreadInput(current_thread, target_thread, True)
            attached_target = True
        win32gui.SetForegroundWindow(hwnd)
    except win32gui.error:
        pass
    finally:
        if attached_fg:
            win32process.AttachThreadInput(current_thread, fg_thread, False)
        if attached_target:
            win32process.AttachThreadInput(current_thread, target_thread, False)


def capture_window(hwnd: int) -> tuple[np.ndarray, int, int]:
    """
    Capture the client area of a window as a BGR numpy array.

    Returns (image, screen_left, screen_top) where coordinates are absolute
    screen positions for converting match centers to click targets.
    """
    left, top, right, bottom = get_window_rect(hwnd)
    width = max(1, right - left)
    height = max(1, bottom - top)

    with mss.mss() as sct:
        monitor = {"left": left, "top": top, "width": width, "height": height}
        shot = sct.grab(monitor)
        img = np.array(shot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    return img, left, top
