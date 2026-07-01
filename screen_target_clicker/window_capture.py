"""Window enumeration and screenshot capture on Windows."""

from __future__ import annotations

import win32gui
import win32con
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


def bring_window_to_front(hwnd: int) -> None:
    """Try to restore and focus a window before capture."""
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except win32gui.error:
        pass


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
