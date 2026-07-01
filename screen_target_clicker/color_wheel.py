"""HSV color wheel widget with brightness bar and lighten/darken controls."""

from __future__ import annotations

import colorsys
import math
import tkinter as tk
from collections.abc import Callable

from PIL import Image, ImageDraw, ImageTk

from .ui_theme import ui_font


def _clamp_byte(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def hex_to_hsv(hex_color: str) -> tuple[float, float, float]:
    raw = hex_color.lstrip("#")
    r = int(raw[0:2], 16) / 255
    g = int(raw[2:4], 16) / 255
    b = int(raw[4:6], 16) / 255
    return colorsys.rgb_to_hsv(r, g, b)


def hsv_to_hex(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{_clamp_byte(r * 255):02x}{_clamp_byte(g * 255):02x}{_clamp_byte(b * 255):02x}"


def derive_accent_variants(hex_color: str) -> tuple[str, str, str]:
    """Return (accent, glow, dim) hex colors from a base accent."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    glow = f"#{_clamp_byte(r + 38):02x}{_clamp_byte(g + 38):02x}{_clamp_byte(b + 38):02x}"
    dim = f"#{_clamp_byte(r * 0.62):02x}{_clamp_byte(g * 0.62):02x}{_clamp_byte(b * 0.62):02x}"
    return f"#{hex_color}", glow, dim


def adjust_hex(hex_color: str, delta: int) -> str:
    """Lighten (+) or darken (-) a hex color."""
    raw = hex_color.lstrip("#")
    r = _clamp_byte(int(raw[0:2], 16) + delta)
    g = _clamp_byte(int(raw[2:4], 16) + delta)
    b = _clamp_byte(int(raw[4:6], 16) + delta)
    return f"#{r:02x}{g:02x}{b:02x}"


def create_wheel_image(size: int) -> Image.Image:
    """Build a circular HSV color wheel as a PIL image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = img.load()
    center = (size - 1) / 2
    radius = center - 2

    for y in range(size):
        for x in range(size):
            dx = x - center
            dy = y - center
            dist = math.hypot(dx, dy)
            if dist > radius:
                continue
            angle = (math.degrees(math.atan2(dy, dx)) + 360) % 360
            saturation = dist / radius
            r, g, b = colorsys.hsv_to_rgb(angle / 360, saturation, 1.0)
            pixels[x, y] = (_clamp_byte(r * 255), _clamp_byte(g * 255), _clamp_byte(b * 255), 255)

    draw = ImageDraw.Draw(img)
    draw.ellipse((1, 1, size - 2, size - 2), outline=(60, 60, 80, 255), width=2)
    return img


def create_brightness_bar(h: float, s: float, width: int, height: int) -> Image.Image:
    """Vertical gradient from full brightness to black at fixed hue/saturation."""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for y in range(height):
        value = 1.0 - (y / max(1, height - 1))
        r, g, b = colorsys.hsv_to_rgb(h, s, value)
        row = (_clamp_byte(r * 255), _clamp_byte(g * 255), _clamp_byte(b * 255))
        for x in range(width):
            pixels[x, y] = row
    return img


class ColorWheelWidget(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        on_color: Callable[[str], None],
        *,
        size: int = 150,
        bar_width: int = 22,
        bg: str = "#12121a",
    ) -> None:
        super().__init__(master, bg=bg)
        self._on_color = on_color
        self._size = size
        self._bar_width = bar_width
        self._wheel_photo: ImageTk.PhotoImage | None = None
        self._bar_photo: ImageTk.PhotoImage | None = None
        self._wheel_marker_id: int | None = None
        self._bar_marker_id: int | None = None
        self._border = "#2a2a3c"
        self._h, self._s, self._v = hex_to_hsv("#7c6cf0")

        controls = tk.Frame(self, bg=bg)
        controls.pack(side=tk.LEFT)

        self.wheel_canvas = tk.Canvas(
            controls,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self.wheel_canvas.pack(side=tk.LEFT)

        wheel = create_wheel_image(size)
        self._wheel_photo = ImageTk.PhotoImage(wheel)
        self.wheel_canvas.create_image(size // 2, size // 2, image=self._wheel_photo)
        self.wheel_canvas.bind("<Button-1>", self._pick_wheel)
        self.wheel_canvas.bind("<B1-Motion>", self._pick_wheel)

        bar_col = tk.Frame(controls, bg=bg)
        bar_col.pack(side=tk.LEFT, padx=(8, 0))

        self.bar_canvas = tk.Canvas(
            bar_col,
            width=bar_width,
            height=size,
            bg=bg,
            highlightthickness=1,
            highlightbackground=self._border,
            bd=0,
        )
        self.bar_canvas.pack()
        self.bar_canvas.bind("<Button-1>", self._pick_bar)
        self.bar_canvas.bind("<B1-Motion>", self._pick_bar)

        btn_row = tk.Frame(bar_col, bg=bg)
        btn_row.pack(fill=tk.X, pady=(6, 0))

        self._lighten_btn = tk.Button(
            btn_row,
            text="+",
            width=2,
            bd=0,
            relief="flat",
            bg="#1e1e2c",
            fg="#ececf4",
            activebackground="#2a2a3c",
            activeforeground="#ffffff",
            font=ui_font(9, bold=True),
            cursor="hand2",
            command=self._lighten,
        )
        self._lighten_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        self._darken_btn = tk.Button(
            btn_row,
            text="−",
            width=2,
            bd=0,
            relief="flat",
            bg="#1e1e2c",
            fg="#ececf4",
            activebackground="#2a2a3c",
            activeforeground="#ffffff",
            font=ui_font(9, bold=True),
            cursor="hand2",
            command=self._darken,
        )
        self._darken_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        self.preview = tk.Canvas(self, width=36, height=36, bg=bg, highlightthickness=0)
        self.preview.pack(side=tk.LEFT, padx=(12, 0))

        self._refresh_brightness_bar()
        self._apply_hsv(emit=False)

    @property
    def current_color(self) -> str:
        return hsv_to_hex(self._h, self._s, self._v)

    def set_color(self, hex_color: str) -> None:
        self._h, self._s, self._v = hex_to_hsv(hex_color)
        self._refresh_brightness_bar()
        self._apply_hsv(emit=False)

    def set_frame_bg(self, hex_color: str, *, border: str | None = None) -> None:
        if border is not None:
            self._border = border
            self.bar_canvas.configure(highlightbackground=border)
        self.configure(bg=hex_color)
        self.wheel_canvas.configure(bg=hex_color)
        self.bar_canvas.configure(bg=hex_color)
        self.preview.configure(bg=hex_color)
        btn_bg = hex_color
        for btn in (self._lighten_btn, self._darken_btn):
            btn.configure(bg=btn_bg, activebackground=border or self._border)
        self._draw_preview(self.current_color)

    def refresh_fonts(self) -> None:
        font = ui_font(9, bold=True)
        self._lighten_btn.configure(font=font)
        self._darken_btn.configure(font=font)

    def _lighten(self) -> None:
        self._v = _clamp01(self._v + 0.06)
        self._apply_hsv(emit=True)

    def _darken(self) -> None:
        self._v = _clamp01(self._v - 0.06)
        self._apply_hsv(emit=True)

    def _apply_hsv(self, *, emit: bool) -> None:
        hex_color = self.current_color
        self._draw_preview(hex_color)
        self._draw_wheel_marker()
        self._draw_bar_marker()
        if emit:
            self._on_color(hex_color)

    def _refresh_brightness_bar(self) -> None:
        bar = create_brightness_bar(self._h, self._s, self._bar_width, self._size)
        self._bar_photo = ImageTk.PhotoImage(bar)
        self.bar_canvas.delete("bar")
        self.bar_canvas.create_image(
            self._bar_width // 2,
            self._size // 2,
            image=self._bar_photo,
            tags="bar",
        )

    def _draw_preview(self, hex_color: str) -> None:
        self.preview.delete("all")
        self.preview.create_oval(
            2, 2, 34, 34, fill=hex_color, outline=self._border, width=2
        )

    def _draw_wheel_marker(self) -> None:
        if self._wheel_marker_id is not None:
            self.wheel_canvas.delete(self._wheel_marker_id)

        center = self._size / 2
        radius = center - 2
        angle = self._h * 2 * math.pi
        dist = self._s * radius
        x = center + dist * math.cos(angle)
        y = center + dist * math.sin(angle)
        r = 5
        self._wheel_marker_id = self.wheel_canvas.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            outline="#ffffff",
            width=2,
        )

    def _draw_bar_marker(self) -> None:
        if self._bar_marker_id is not None:
            self.bar_canvas.delete(self._bar_marker_id)

        y = (1.0 - self._v) * (self._size - 1)
        self._bar_marker_id = self.bar_canvas.create_line(
            0,
            y,
            self._bar_width,
            y,
            fill="#ffffff",
            width=2,
        )

    def _pick_wheel(self, event: tk.Event) -> None:
        center = self._size / 2
        dx = event.x - center
        dy = event.y - center
        dist = math.hypot(dx, dy)
        radius = center - 2
        if dist > radius:
            return

        angle = (math.degrees(math.atan2(dy, dx)) + 360) % 360
        self._h = angle / 360
        self._s = dist / radius
        self._v = 1.0
        self._refresh_brightness_bar()
        self._apply_hsv(emit=True)

    def _pick_bar(self, event: tk.Event) -> None:
        y = max(0, min(self._size - 1, event.y))
        self._v = _clamp01(1.0 - (y / max(1, self._size - 1)))
        self._apply_hsv(emit=True)
