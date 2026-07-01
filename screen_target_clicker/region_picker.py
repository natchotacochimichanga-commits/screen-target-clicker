"""Dialog to drag-select a scan region on a window screenshot."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk

from .scan_region import ScanRegion
from .ui_theme import Colors, apply_theme, style_text
from .window_capture import capture_window


class RegionPickerDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        hwnd: int,
        window_title: str,
        existing: ScanRegion | None = None,
        *,
        dialog_title: str | None = None,
    ) -> None:
        super().__init__(master)
        self.title(dialog_title or f"Set scan zone — {window_title}")
        self.geometry("820x620")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        apply_theme(self)
        self.configure(bg=Colors.BG)

        self._result: ScanRegion | None = None
        self._use_full = False
        self._photo: ImageTk.PhotoImage | None = None
        self._scale = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._image_w = 0
        self._image_h = 0
        self._drag_start: tuple[int, int] | None = None
        self._rect_id: int | None = None
        self._existing = existing

        try:
            screen, _, _ = capture_window(hwnd)
        except Exception as exc:
            messagebox.showerror("Capture failed", str(exc), parent=master)
            self.destroy()
            return

        self._screen = screen
        self._build_ui()
        self._show_image()
        if existing is not None:
            self._draw_existing(existing)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    @property
    def result(self) -> ScanRegion | None:
        return self._result

    @property
    def use_full_window(self) -> bool:
        return self._use_full

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill=tk.X)

        ttk.Label(
            toolbar,
            text="Click and drag to draw the scan zone. Only this area will be searched.",
        ).pack(side=tk.LEFT)

        canvas_wrap = ttk.Frame(self, padding=8)
        canvas_wrap.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_wrap, bg=Colors.INPUT, cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        buttons = ttk.Frame(self, padding=8)
        buttons.pack(fill=tk.X)

        ttk.Button(buttons, text="Use full window", command=self._use_full_window).pack(
            side=tk.LEFT
        )
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="OK", style="Accent.TButton", command=self._confirm).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        self.status = ttk.Label(self, text="", padding=(8, 0, 8, 8))
        self.status.pack(fill=tk.X)

    def _show_image(self) -> None:
        rgb = cv2.cvtColor(self._screen, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        self._image_w, self._image_h = pil.size

        max_w = max(400, self.winfo_width() - 40)
        max_h = max(300, self.winfo_height() - 120)
        self._scale = min(max_w / self._image_w, max_h / self._image_h, 1.0)

        disp_w = int(self._image_w * self._scale)
        disp_h = int(self._image_h * self._scale)
        if self._scale < 1.0:
            pil = pil.resize((disp_w, disp_h), Image.Resampling.LANCZOS)

        self._photo = ImageTk.PhotoImage(pil)
        self.canvas.delete("all")
        self.canvas.config(width=disp_w, height=disp_h, scrollregion=(0, 0, disp_w, disp_h))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._photo)

    def _canvas_to_image(self, cx: int, cy: int) -> tuple[int, int]:
        ix = int(round(cx / self._scale))
        iy = int(round(cy / self._scale))
        ix = max(0, min(ix, self._image_w - 1))
        iy = max(0, min(iy, self._image_h - 1))
        return ix, iy

    def _image_rect_to_canvas(
        self, x: int, y: int, w: int, h: int
    ) -> tuple[int, int, int, int]:
        return (
            int(x * self._scale),
            int(y * self._scale),
            int((x + w) * self._scale),
            int((y + h) * self._scale),
        )

    def _draw_existing(self, region: ScanRegion) -> None:
        x1, y1, x2, y2 = self._image_rect_to_canvas(
            region.x, region.y, region.width, region.height
        )
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
        self._rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2, outline="#ff7828", width=2
        )
        self._offset_x = region.x
        self._offset_y = region.y
        self.status.config(text=f"Current zone: {region.label}")

    def _on_press(self, event: tk.Event) -> None:
        self._drag_start = (event.x, event.y)
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
        x1, y1 = self._drag_start
        self._rect_id = self.canvas.create_rectangle(
            x1, y1, event.x, event.y, outline="#ff7828", width=2
        )

    def _on_release(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return

        x1, y1 = self._drag_start
        x2, y2 = event.x, event.y
        self._drag_start = None

        left, top = self._canvas_to_image(min(x1, x2), min(y1, y2))
        right, bottom = self._canvas_to_image(max(x1, x2), max(y1, y2))
        width = max(1, right - left)
        height = max(1, bottom - top)

        self._offset_x = left
        self._offset_y = top
        region = ScanRegion(x=left, y=top, width=width, height=height)
        self.status.config(text=f"Selected: {region.label}")

    def _use_full_window(self) -> None:
        self._use_full = True
        self._result = None
        self.destroy()

    def _confirm(self) -> None:
        if self._rect_id is None and self._existing is None:
            messagebox.showwarning(
                "No zone selected",
                "Drag a rectangle on the preview, or click Use full window.",
                parent=self,
            )
            return

        if self._rect_id is not None:
            coords = self.canvas.coords(self._rect_id)
            if len(coords) != 4:
                return
            left, top = self._canvas_to_image(int(coords[0]), int(coords[1]))
            right, bottom = self._canvas_to_image(int(coords[2]), int(coords[3]))
            width = max(1, right - left)
            height = max(1, bottom - top)
            self._result = ScanRegion(x=left, y=top, width=width, height=height)
        else:
            self._result = self._existing

        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()
