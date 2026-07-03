"""Background scanner that watches a window and clicks on target matches."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import pyautogui

from .detection_analysis import DetectionAnalysis, analyze_detection
from .matcher import Match, TargetImage
from .rules import ClickRule
from .scan_region import ScanRegion
from .window_capture import capture_window, focus_target_window, get_foreground_hwnd, is_window_alive

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


@dataclass(frozen=True)
class ScannerTimerState:
    click_cooldown_remaining: float
    limit_pause_remaining: float
    burst_clicks: int
    click_limit: int
    scan_loops: int
    total_clicks: int
    burst_cycles: int
    waits_triggered: int


@dataclass(frozen=True)
class ScanFrameUpdate:
    analysis: DetectionAnalysis
    click_blocked: bool
    clicked: bool
    block_reason: str | None = None


class WindowScanner:
    def __init__(
        self,
        hwnd: int,
        targets: list[TargetImage],
        click_rules: list[ClickRule],
        threshold: float,
        scan_region: ScanRegion | None,
        interval_sec: float,
        cooldown_sec: float,
        click_limit: int,
        limit_pause_sec: float,
        on_status: Callable[[str], None],
        on_match: Callable[[Match, int, int], None] | None = None,
        on_scan_frame: Callable[[ScanFrameUpdate], None] | None = None,
        on_window_lost: Callable[[], None] | None = None,
        target_title: str = "",
    ) -> None:
        self.hwnd = hwnd
        self.target_title = target_title.strip()
        self.targets = targets
        self.click_rules = click_rules
        self.threshold = threshold
        self.scan_region = scan_region
        self.interval_sec = interval_sec
        self.cooldown_sec = max(0.0, cooldown_sec)
        self.click_limit = max(1, click_limit)
        self.limit_pause_sec = limit_pause_sec
        self.on_status = on_status
        self.on_match = on_match
        self.on_scan_frame = on_scan_frame
        self.on_window_lost = on_window_lost

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_click_time = 0.0
        self._burst_clicks = 0
        self._pause_until = 0.0
        self._scan_loops = 0
        self._total_clicks = 0
        self._burst_cycles = 0
        self._waits_triggered = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_timer_state(self) -> ScannerTimerState:
        now = time.monotonic()
        cooldown = 0.0
        if self._last_click_time > 0:
            cooldown = max(0.0, self.cooldown_sec - (now - self._last_click_time))
        pause = 0.0
        if self._in_limit_pause():
            pause = max(0.0, self._pause_until - now)
        return ScannerTimerState(
            click_cooldown_remaining=cooldown,
            limit_pause_remaining=pause,
            burst_clicks=self._burst_clicks,
            click_limit=self.click_limit,
            scan_loops=self._scan_loops,
            total_clicks=self._total_clicks,
            burst_cycles=self._burst_cycles,
            waits_triggered=self._waits_triggered,
        )

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._last_click_time = 0.0
        self._burst_clicks = 0
        self._pause_until = 0.0
        self._scan_loops = 0
        self._total_clicks = 0
        self._burst_cycles = 0
        self._waits_triggered = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _in_click_cooldown(self) -> bool:
        if self._last_click_time <= 0 or self.cooldown_sec <= 0:
            return False
        return (time.monotonic() - self._last_click_time) < self.cooldown_sec

    def _mark_click(self) -> None:
        self._last_click_time = time.monotonic()

    def _in_limit_pause(self) -> bool:
        return time.monotonic() < self._pause_until

    def _wait_interruptible(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self._stop_event.is_set():
            time.sleep(min(0.25, max(0.0, end - time.monotonic())))

    def _record_click(self) -> None:
        self._burst_clicks += 1
        if self._burst_clicks < self.click_limit:
            return

        self._burst_clicks = 0
        self._pause_until = time.monotonic() + self.limit_pause_sec
        self._burst_cycles += 1
        self._waits_triggered += 1
        self.on_status(
            f"Click limit reached ({self.click_limit}). "
            f"Pausing for {self.limit_pause_sec:.0f}s before trying again."
        )

    def _emit_scan_frame(
        self,
        analysis: DetectionAnalysis,
        *,
        click_blocked: bool,
        clicked: bool,
        block_reason: str | None = None,
    ) -> None:
        if self.on_scan_frame is None:
            return
        self.on_scan_frame(
            ScanFrameUpdate(
                analysis=analysis,
                click_blocked=click_blocked,
                clicked=clicked,
                block_reason=block_reason,
            )
        )

    def _ensure_target_focus(self) -> bool:
        if not is_window_alive(self.hwnd):
            return False
        if get_foreground_hwnd() == self.hwnd:
            return True
        label = self.target_title or f"window {self.hwnd}"
        self.on_status(f"Refocusing {label} before click.")
        return focus_target_window(self.hwnd)

    def _run(self) -> None:
        self.on_status("Scanner started.")
        try:
            while not self._stop_event.is_set():
                if self._in_limit_pause():
                    remaining = self._pause_until - time.monotonic()
                    if remaining > 0:
                        self._wait_interruptible(remaining)
                    if not self._stop_event.is_set() and not self._in_limit_pause():
                        self.on_status("Pause ended. Resuming clicks.")
                    continue

                try:
                    if not is_window_alive(self.hwnd):
                        self.on_status("Target window closed or unavailable.")
                        if self.on_window_lost is not None:
                            self.on_window_lost()
                        break

                    screen, win_left, win_top = capture_window(self.hwnd)
                except Exception as exc:
                    self.on_status(f"Capture failed: {exc}")
                    time.sleep(self.interval_sec)
                    continue

                analysis = analyze_detection(
                    screen,
                    self.targets,
                    self.click_rules,
                    self.threshold,
                    self.scan_region,
                )

                best_match = analysis.best_match
                click_blocked = False
                clicked = False
                block_reason: str | None = None

                if best_match is not None:
                    if self._in_click_cooldown():
                        click_blocked = True
                        block_reason = "cooldown"
                        self._waits_triggered += 1
                    elif not self._ensure_target_focus():
                        click_blocked = True
                        block_reason = "refocus"
                        self._waits_triggered += 1
                    else:
                        click_x = win_left + best_match.center_x
                        click_y = win_top + best_match.center_y
                        pyautogui.click(click_x, click_y)
                        self._mark_click()
                        self._record_click()
                        self._total_clicks += 1
                        clicked = True
                        msg = (
                            f"Clicked '{best_match.target_name}' at "
                            f"({click_x}, {click_y}) "
                            f"[{best_match.confidence:.0%}]"
                        )
                        self.on_status(msg)
                        if self.on_match:
                            self.on_match(best_match, click_x, click_y)

                self._emit_scan_frame(
                    analysis,
                    click_blocked=click_blocked,
                    clicked=clicked,
                    block_reason=block_reason,
                )
                self._scan_loops += 1

                time.sleep(self.interval_sec)
        finally:
            self.on_status("Scanner stopped.")
