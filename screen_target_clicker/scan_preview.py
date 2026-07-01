"""Live scan preview with detection markers and cooldown timer."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from .detection_analysis import DetectionAnalysis
from .scanner import ScannerTimerState
from .ui_theme import Colors, apply_theme, style_text, ui_font
from .window_capture import get_window_rect

PREVIEW_WIDTH = 340
PREVIEW_HEIGHT = 300
PREVIEW_INSET = 6
PREVIEW_IMAGE_MAX_W = 300
PREVIEW_IMAGE_MAX_H = 140


class ScanPreviewWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc, hwnd: int, window_title: str) -> None:
        super().__init__(master)
        self._target_hwnd = hwnd
        self.title(f"Scan — {window_title}")
        self.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}")
        self.minsize(280, 240)
        self.resizable(False, False)
        apply_theme(self)
        self.configure(bg=Colors.BG)
        self.attributes("-topmost", True)

        self._photo: ImageTk.PhotoImage | None = None
        self._build_ui()
        self.pin_to_target()

    def _build_ui(self) -> None:
        timer_bar = tk.Frame(self, bg=Colors.CARD, padx=8, pady=6)
        timer_bar.pack(fill=tk.X)

        self._timer_label = tk.Label(
            timer_bar,
            text="Starting scan…",
            bg=Colors.CARD,
            fg=Colors.TEXT,
            font=ui_font(9, bold=True),
            anchor=tk.W,
        )
        self._timer_label.pack(fill=tk.X)

        self._burst_label = tk.Label(
            timer_bar,
            text="",
            bg=Colors.CARD,
            fg=Colors.TEXT_DIM,
            font=ui_font(8),
            anchor=tk.W,
        )
        self._burst_label.pack(fill=tk.X, pady=(2, 0))

        preview_wrap = ttk.Frame(self, padding=(6, 4))
        preview_wrap.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            preview_wrap,
            width=PREVIEW_IMAGE_MAX_W,
            height=PREVIEW_IMAGE_MAX_H,
            bg=Colors.INPUT,
            highlightthickness=1,
            highlightbackground=Colors.BORDER,
        )
        self.canvas.pack()

        results_wrap = ttk.Frame(self, padding=(6, 0, 6, 6))
        results_wrap.pack(fill=tk.BOTH, expand=True)

        self.results = tk.Text(
            results_wrap,
            height=5,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.results.pack(fill=tk.BOTH, expand=True)
        style_text(self.results)

    def pin_to_target(self) -> None:
        if not self.winfo_exists():
            return
        try:
            left, top, _right, _bottom = get_window_rect(self._target_hwnd)
        except Exception:
            return

        x = left + PREVIEW_INSET
        y = top + PREVIEW_INSET
        self.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}+{x}+{y}")

    def update_timer(self, state: ScannerTimerState) -> None:
        if state.limit_pause_remaining > 0:
            self._timer_label.config(
                text=f"Pause {state.limit_pause_remaining:.1f}s",
                fg=Colors.WARNING,
            )
        elif state.click_cooldown_remaining > 0:
            self._timer_label.config(
                text=f"Cooldown {state.click_cooldown_remaining:.1f}s",
                fg=Colors.ACCENT,
            )
        else:
            self._timer_label.config(
                text="Ready",
                fg=Colors.SUCCESS,
            )

        self._burst_label.config(
            text=(
                f"Burst {state.burst_clicks}/{state.click_limit} · "
                f"Loop {state.scan_loops:,} · Clicks {state.total_clicks:,} · "
                f"Waits {state.waits_triggered:,}"
            )
        )

    def update_scan(
        self,
        analysis: DetectionAnalysis,
        *,
        click_blocked: bool = False,
        clicked: bool = False,
    ) -> None:
        text = _compact_results(analysis.results_text)
        if clicked:
            text += "\n>> Clicked"
        elif click_blocked:
            text += "\n>> Waiting for cooldown"

        self._show_image(analysis.annotated)
        self._set_results(text)

    def _show_image(self, bgr_image) -> None:
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)

        w, h = pil.size
        scale = min(
            PREVIEW_IMAGE_MAX_W / w,
            PREVIEW_IMAGE_MAX_H / h,
            1.0,
        )
        if scale < 1.0:
            pil = pil.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        self._photo = ImageTk.PhotoImage(pil)
        self.canvas.delete("all")
        self.canvas.create_image(
            PREVIEW_IMAGE_MAX_W // 2,
            PREVIEW_IMAGE_MAX_H // 2,
            anchor=tk.CENTER,
            image=self._photo,
        )

    def _set_results(self, text: str) -> None:
        self.results.config(state=tk.NORMAL)
        self.results.delete("1.0", tk.END)
        self.results.insert(tk.END, text)
        self.results.config(state=tk.DISABLED)


def _compact_results(full_text: str) -> str:
    """Keep the most useful lines for the small results panel."""
    lines: list[str] = []
    for raw in full_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("==="):
            continue
        if line.startswith("Primary threshold") or line.startswith("Scan zone"):
            lines.append(line)
            continue
        if line.startswith("Best:") or line.startswith("Status:"):
            lines.append(f"  {line}")
            continue
        if "→" in line or line.endswith(".png") or line.endswith(".jpg"):
            lines.append(line)
            continue
        if line.startswith(">>>") or "Best click candidate" in line:
            lines.append(line)

    if not lines:
        return full_text[:400]
    return "\n".join(lines[:12])
