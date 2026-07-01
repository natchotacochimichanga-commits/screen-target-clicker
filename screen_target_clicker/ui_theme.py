"""Axon-style dark theme for tkinter / ttk widgets."""

from __future__ import annotations

from dataclasses import dataclass

import tkinter as tk
from tkinter import ttk

DEFAULT_ACCENT = "#7c6cf0"
DEFAULT_UI_FONT = "Segoe UI"
DEFAULT_MONO_FONT = "Consolas"

# Curated fonts commonly available on Windows; filtered at runtime.
FONT_CHOICES_UI = [
    "Segoe UI",
    "Arial",
    "Calibri",
    "Tahoma",
    "Verdana",
    "Bahnschrift",
    "Franklin Gothic Medium",
    "Georgia",
    "Century Gothic",
    "Trebuchet MS",
]

FONT_CHOICES_MONO = [
    "Consolas",
    "Courier New",
    "Cascadia Mono",
    "Cascadia Code",
    "Lucida Console",
    "Courier",
    "Fixedsys",
]

DEFAULT_BACKGROUNDS = {
    "BG": "#0b0b0f",
    "SIDEBAR": "#0e0e14",
    "PANEL": "#12121a",
    "CARD": "#181824",
    "INPUT": "#14141e",
}

DEFAULT_CARD_HOVER = "#1e1e2c"
DEFAULT_BORDER = "#2a2a3c"

# Display label -> Colors attribute (None = accent)
COLOR_TARGETS: list[tuple[str, str | None]] = [
    ("Accent", None),
    ("Window", "BG"),
    ("Sidebar", "SIDEBAR"),
    ("Panel", "PANEL"),
    ("Cards", "CARD"),
    ("Inputs", "INPUT"),
]


@dataclass(frozen=True)
class ThemePreset:
    name: str
    accent: str
    bg: str
    sidebar: str
    panel: str
    card: str
    input: str
    card_hover: str
    border: str


THEME_PRESETS: list[ThemePreset] = [
    ThemePreset(
        name="Axon",
        accent="#7c6cf0",
        bg="#0b0b0f",
        sidebar="#0e0e14",
        panel="#12121a",
        card="#181824",
        input="#14141e",
        card_hover="#1e1e2c",
        border="#2a2a3c",
    ),
    ThemePreset(
        name="Neon",
        accent="#22d3ee",
        bg="#06080f",
        sidebar="#080b14",
        panel="#0c101c",
        card="#111827",
        input="#0f1520",
        card_hover="#182032",
        border="#243044",
    ),
    ThemePreset(
        name="Ember",
        accent="#f97316",
        bg="#0f0a08",
        sidebar="#140c0a",
        panel="#1a100d",
        card="#241612",
        input="#1a100d",
        card_hover="#2e1c16",
        border="#3d2a22",
    ),
    ThemePreset(
        name="Forest",
        accent="#34d399",
        bg="#080c0a",
        sidebar="#0a100d",
        panel="#0e1612",
        card="#142019",
        input="#101a15",
        card_hover="#1a2a22",
        border="#264035",
    ),
    ThemePreset(
        name="Rose",
        accent="#f472b6",
        bg="#0f0a0d",
        sidebar="#140a10",
        panel="#1a0f15",
        card="#24121c",
        input="#1a1018",
        card_hover="#2e1826",
        border="#3d2640",
    ),
    ThemePreset(
        name="Slate",
        accent="#94a3b8",
        bg="#0a0b0d",
        sidebar="#0e0f12",
        panel="#12141a",
        card="#181b22",
        input="#14171e",
        card_hover="#22262f",
        border="#2f3540",
    ),
]


class Colors:
    BG = "#0b0b0f"
    SIDEBAR = "#0e0e14"
    PANEL = "#12121a"
    CARD = "#181824"
    CARD_HOVER = "#1e1e2c"
    INPUT = "#14141e"
    BORDER = "#2a2a3c"
    ACCENT = DEFAULT_ACCENT
    ACCENT_DIM = "#5a4db8"
    ACCENT_GLOW = "#9588f5"
    SUCCESS = "#34d399"
    DANGER = "#f87171"
    WARNING = "#fbbf24"
    TEXT = "#ececf4"
    TEXT_DIM = "#7a7a94"
    TEXT_MUTED = "#55556a"


class Fonts:
    UI = DEFAULT_UI_FONT
    MONO = DEFAULT_MONO_FONT


def ui_font(size: int, *, bold: bool = False) -> tuple:
    if bold:
        return (Fonts.UI, size, "bold")
    return (Fonts.UI, size)


def mono_font(size: int = 9) -> tuple:
    return (Fonts.MONO, size)


def set_ui_font(name: str) -> None:
    Fonts.UI = name


def set_mono_font(name: str) -> None:
    Fonts.MONO = name


def reset_fonts() -> None:
    Fonts.UI = DEFAULT_UI_FONT
    Fonts.MONO = DEFAULT_MONO_FONT


def available_fonts(root: tk.Misc, choices: list[str]) -> list[str]:
    import tkinter.font as tkfont

    installed = {family.lower(): family for family in tkfont.families(root)}
    found: list[str] = []
    for choice in choices:
        match = installed.get(choice.lower())
        if match:
            found.append(match)
    return found or [DEFAULT_UI_FONT]


def set_accent_color(hex_color: str) -> None:
    from .color_wheel import derive_accent_variants

    accent, glow, dim = derive_accent_variants(hex_color)
    Colors.ACCENT = accent
    Colors.ACCENT_GLOW = glow
    Colors.ACCENT_DIM = dim


def reset_accent_color() -> None:
    set_accent_color(DEFAULT_ACCENT)


def set_background_color(key: str, hex_color: str) -> None:
    from .color_wheel import adjust_hex

    if key not in DEFAULT_BACKGROUNDS:
        return
    setattr(Colors, key, hex_color)
    if key == "CARD":
        Colors.CARD_HOVER = adjust_hex(hex_color, 14)
    if key == "INPUT":
        Colors.BORDER = adjust_hex(hex_color, 38)


def get_color_for_target(label: str) -> str:
    for name, key in COLOR_TARGETS:
        if name == label:
            if key is None:
                return Colors.ACCENT
            return getattr(Colors, key)
    return Colors.ACCENT


def target_key_for_label(label: str) -> str | None:
    for name, key in COLOR_TARGETS:
        if name == label:
            return key
    return None


def reset_theme_colors() -> None:
    apply_theme_preset(THEME_PRESETS[0])
    reset_fonts()


def apply_theme_preset(preset: ThemePreset) -> None:
    set_accent_color(preset.accent)
    Colors.BG = preset.bg
    Colors.SIDEBAR = preset.sidebar
    Colors.PANEL = preset.panel
    Colors.CARD = preset.card
    Colors.INPUT = preset.input
    Colors.CARD_HOVER = preset.card_hover
    Colors.BORDER = preset.border


def get_preset_by_name(name: str) -> ThemePreset | None:
    for preset in THEME_PRESETS:
        if preset.name == name:
            return preset
    return None


def apply_theme(root: tk.Misc) -> ttk.Style:
    root.configure(bg=Colors.BG)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=Colors.BG, foreground=Colors.TEXT, borderwidth=0)
    style.configure("TFrame", background=Colors.BG)
    style.configure("Sidebar.TFrame", background=Colors.SIDEBAR)
    style.configure("Panel.TFrame", background=Colors.PANEL)
    style.configure("Card.TFrame", background=Colors.CARD)

    style.configure(
        "Card.TLabelframe",
        background=Colors.CARD,
        foreground=Colors.TEXT_DIM,
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=Colors.CARD,
        foreground=Colors.ACCENT_GLOW,
        font=ui_font(9, bold=True),
    )

    style.configure(
        "TLabel",
        background=Colors.BG,
        foreground=Colors.TEXT,
        font=ui_font(9),
    )
    style.configure("Dim.TLabel", background=Colors.BG, foreground=Colors.TEXT_DIM)
    style.configure("Panel.TLabel", background=Colors.PANEL, foreground=Colors.TEXT)
    style.configure("Card.TLabel", background=Colors.CARD, foreground=Colors.TEXT)
    style.configure("DimCard.TLabel", background=Colors.CARD, foreground=Colors.TEXT_DIM)
    style.configure(
        "Title.TLabel",
        background=Colors.PANEL,
        foreground=Colors.TEXT,
        font=ui_font(14, bold=True),
    )
    style.configure(
        "Brand.TLabel",
        background=Colors.SIDEBAR,
        foreground=Colors.ACCENT_GLOW,
        font=ui_font(13, bold=True),
    )
    style.configure(
        "SubBrand.TLabel",
        background=Colors.SIDEBAR,
        foreground=Colors.TEXT_DIM,
        font=ui_font(8),
    )

    style.configure(
        "TButton",
        background=Colors.CARD,
        foreground=Colors.TEXT,
        borderwidth=0,
        focusthickness=0,
        padding=(12, 7),
        font=ui_font(9),
    )
    style.map(
        "TButton",
        background=[("active", Colors.CARD_HOVER), ("pressed", Colors.INPUT)],
        foreground=[("disabled", Colors.TEXT_MUTED)],
    )

    style.configure(
        "Accent.TButton",
        background=Colors.ACCENT,
        foreground="#ffffff",
        font=ui_font(9, bold=True),
        padding=(14, 8),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("active", Colors.ACCENT_GLOW),
            ("pressed", Colors.ACCENT_DIM),
        ],
    )

    style.configure(
        "Danger.TButton",
        background="#3d1f1f",
        foreground=Colors.DANGER,
        font=ui_font(9, bold=True),
        padding=(14, 8),
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#4d2828"), ("pressed", "#2d1515")],
    )

    style.configure(
        "TCombobox",
        fieldbackground=Colors.INPUT,
        background=Colors.CARD,
        foreground=Colors.TEXT,
        arrowcolor=Colors.TEXT_DIM,
        borderwidth=0,
        padding=6,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", Colors.INPUT)],
        foreground=[("readonly", Colors.TEXT)],
    )

    style.configure(
        "TScale",
        background=Colors.CARD,
        troughcolor=Colors.INPUT,
        borderwidth=0,
    )

    style.configure(
        "TSpinbox",
        fieldbackground=Colors.INPUT,
        background=Colors.CARD,
        foreground=Colors.TEXT,
        arrowcolor=Colors.TEXT_DIM,
        borderwidth=0,
    )

    style.configure("TScrollbar", background=Colors.CARD, troughcolor=Colors.INPUT)

    return style


def style_listbox(listbox: tk.Listbox) -> None:
    listbox.configure(
        bg=Colors.INPUT,
        fg=Colors.TEXT,
        selectbackground=Colors.ACCENT_DIM,
        selectforeground="#ffffff",
        highlightthickness=1,
        highlightbackground=Colors.BORDER,
        highlightcolor=Colors.ACCENT,
        borderwidth=0,
        activestyle="none",
        font=mono_font(9),
        relief="flat",
    )


def style_text(text: tk.Text, *, height: int | None = None) -> None:
    kwargs = dict(
        bg=Colors.INPUT,
        fg=Colors.TEXT_DIM,
        insertbackground=Colors.TEXT,
        selectbackground=Colors.ACCENT_DIM,
        highlightthickness=1,
        highlightbackground=Colors.BORDER,
        borderwidth=0,
        font=mono_font(9),
        relief="flat",
    )
    if height is not None:
        kwargs["height"] = height
    text.configure(**kwargs)


def make_nav_button(
    parent: tk.Misc,
    text: str,
    command,
) -> tk.Button:
    btn = tk.Button(
        parent,
        text=text,
        anchor="w",
        padx=16,
        pady=10,
        bd=0,
        relief="flat",
        cursor="hand2",
        bg=Colors.SIDEBAR,
        fg=Colors.TEXT_DIM,
        activebackground=Colors.CARD,
        activeforeground=Colors.TEXT,
        font=ui_font(10),
        command=command,
    )
    return btn


def set_nav_active(btn: tk.Button, active: bool) -> None:
    if active:
        btn.configure(
            bg=Colors.CARD,
            fg=Colors.ACCENT_GLOW,
            font=ui_font(10, bold=True),
        )
    else:
        btn.configure(
            bg=Colors.SIDEBAR,
            fg=Colors.TEXT_DIM,
            font=ui_font(10),
        )


def refresh_widget_styles(app: tk.Misc) -> None:
    """Re-apply styles after theme color changes."""
    apply_theme(app)
    app.configure(bg=Colors.BG)
    if hasattr(app, "color_wheel"):
        app.color_wheel.set_frame_bg(Colors.CARD, border=Colors.BORDER)
        if hasattr(app.color_wheel, "refresh_fonts"):
            app.color_wheel.refresh_fonts()
    if hasattr(app, "_refresh_color_swatches"):
        app._refresh_color_swatches()
    if hasattr(app, "_refresh_font_widgets"):
        app._refresh_font_widgets()
    if hasattr(app, "target_list"):
        style_listbox(app.target_list)
    if hasattr(app, "rules_list"):
        style_listbox(app.rules_list)
    if hasattr(app, "log"):
        style_text(app.log)
    if hasattr(app, "_active_panel") and hasattr(app, "_nav_buttons"):
        for name, btn in app._nav_buttons.items():
            set_nav_active(btn, name == app._active_panel)
    if hasattr(app, "_set_status") and hasattr(app, "_scanner"):
        running = app._scanner is not None and app._scanner.running
        app._set_status("Scanning" if running else "Idle", running=running)
