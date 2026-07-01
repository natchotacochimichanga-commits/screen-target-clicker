"""Desktop GUI for screen-target-clicker."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .color_wheel import ColorWheelWidget
from .hotkey_manager import HotkeyManager, format_hotkey
from .matcher import TargetImage, load_target
from .region_picker import RegionPickerDialog
from .rule_dialog import SubsectionThresholdDialog
from .rules import ClickRule
from .scan_region import ScanRegion
from .scan_preview import ScanPreviewWindow
from .scanner import ScanFrameUpdate, WindowScanner
from .test_detection import TestDetectionWindow
from .ui_theme import (
    COLOR_TARGETS,
    FONT_CHOICES_MONO,
    FONT_CHOICES_UI,
    Colors,
    Fonts,
    THEME_PRESETS,
    ThemePreset,
    apply_theme,
    apply_theme_preset,
    available_fonts,
    get_color_for_target,
    make_nav_button,
    mono_font,
    refresh_widget_styles,
    reset_theme_colors,
    set_accent_color,
    set_background_color,
    set_mono_font,
    set_nav_active,
    set_ui_font,
    style_listbox,
    style_text,
    target_key_for_label,
    ui_font,
)
from .window_capture import list_visible_windows

DISCORD_INVITE_URL = "https://discord.gg/mRfnuHC8f"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Screen Target Clicker")
        self.geometry("920x640")
        self.minsize(820, 560)
        self.configure(bg=Colors.BG)

        apply_theme(self)

        self._targets: list[TargetImage] = []
        self._click_rules: list[ClickRule] = []
        self._scan_region: ScanRegion | None = None
        self._windows: list[tuple[int, str]] = []
        self._scanner: WindowScanner | None = None
        self._test_window: TestDetectionWindow | None = None
        self._scan_preview: ScanPreviewWindow | None = None
        self._scan_ui_tick_id: str | None = None
        self._nav_buttons: dict[str, tk.Button] = {}
        self._panels: dict[str, ttk.Frame] = {}
        self._active_panel = "window"
        self._hotkey_combo = "f6"
        self._hotkey_manager = HotkeyManager(lambda: self.after(0, self.toggle_scan))
        self._capturing_hotkey = False

        self.threshold_var = tk.DoubleVar(value=0.85)
        self.interval_var = tk.DoubleVar(value=0.5)
        self.cooldown_var = tk.DoubleVar(value=2.0)
        self.click_limit_var = tk.IntVar(value=2)
        self.limit_pause_var = tk.DoubleVar(value=60.0)
        self.window_var = tk.StringVar()
        self._status_var = tk.StringVar(value="Idle")
        self._hotkey_display = tk.StringVar(
            value=f"Hotkey: {format_hotkey(self._hotkey_combo)}"
        )
        self._loop_tracker_var = tk.StringVar(value="Loops: 0 · Clicks: 0 · Waits: 0")
        self._last_scan_loops = 0
        self._last_total_clicks = 0
        self._last_burst_cycles = 0
        self._last_waits_triggered = 0

        self._build_ui()
        self.refresh_windows()
        self._show_panel("window")
        self._register_hotkey(self._hotkey_combo)

    def _build_ui(self) -> None:
        shell = ttk.Frame(self)
        shell.pack(fill=tk.BOTH, expand=True)

        sidebar = ttk.Frame(shell, style="Sidebar.TFrame", width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(16, 20, 16, 8))
        brand.pack(fill=tk.X)
        ttk.Label(brand, text="TARGET", style="Brand.TLabel").pack(anchor=tk.W)
        ttk.Label(brand, text="CLICKER", style="Brand.TLabel").pack(anchor=tk.W)
        ttk.Label(brand, text="v1.0 · Axon style", style="SubBrand.TLabel").pack(
            anchor=tk.W, pady=(4, 0)
        )

        nav = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(8, 12))
        nav.pack(fill=tk.X)

        for key, label in (
            ("window", "  Window"),
            ("targets", "  Targets"),
            ("rules", "  Rules"),
            ("settings", "  Settings"),
            ("discord", "  Discord"),
        ):
            btn = make_nav_button(nav, label, lambda k=key: self._show_panel(k))
            btn.pack(fill=tk.X, pady=2)
            self._nav_buttons[key] = btn

        ttk.Frame(sidebar, style="Sidebar.TFrame").pack(fill=tk.BOTH, expand=True)

        actions = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=12)
        actions.pack(fill=tk.X, side=tk.BOTTOM)

        self.hotkey_hint = ttk.Label(
            actions,
            textvariable=self._hotkey_display,
            style="SubBrand.TLabel",
        )
        self.hotkey_hint.pack(anchor=tk.W, pady=(0, 6))

        self.loop_tracker = ttk.Label(
            actions,
            textvariable=self._loop_tracker_var,
            style="SubBrand.TLabel",
            wraplength=160,
        )
        self.loop_tracker.pack(anchor=tk.W, pady=(0, 6))

        self.start_btn = ttk.Button(
            actions, text="START", style="Accent.TButton", command=self.toggle_scan
        )
        self.start_btn.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(
            actions, text="Test Detection", command=self.open_test_detection
        ).pack(fill=tk.X)

        ttk.Label(
            actions,
            text="Failsafe: move mouse to top-left corner",
            style="SubBrand.TLabel",
            wraplength=160,
        ).pack(anchor=tk.W, pady=(10, 0))

        main = ttk.Frame(shell, style="Panel.TFrame")
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        header = ttk.Frame(main, style="Panel.TFrame", padding=(20, 16, 20, 8))
        header.pack(fill=tk.X)

        self.page_title = ttk.Label(header, text="Window", style="Title.TLabel")
        self.page_title.pack(side=tk.LEFT)

        self.status_pill = tk.Label(
            header,
            textvariable=self._status_var,
            bg=Colors.INPUT,
            fg=Colors.TEXT_DIM,
            font=ui_font(8, bold=True),
            padx=10,
            pady=4,
        )
        self.status_pill.pack(side=tk.RIGHT)

        content_wrap = ttk.Frame(main, style="Panel.TFrame", padding=(20, 0, 20, 12))
        content_wrap.pack(fill=tk.BOTH, expand=True)

        self.content_host = ttk.Frame(content_wrap, style="Panel.TFrame")
        self.content_host.pack(fill=tk.BOTH, expand=True)

        self._build_window_panel()
        self._build_targets_panel()
        self._build_rules_panel()
        self._build_settings_panel()
        self._build_discord_panel()

        log_card = ttk.Frame(main, style="Panel.TFrame", padding=(20, 0, 20, 16))
        log_card.pack(fill=tk.X)

        log_inner = ttk.LabelFrame(log_card, text=" ACTIVITY LOG ", style="Card.TLabelframe")
        log_inner.pack(fill=tk.X)

        log_wrap = ttk.Frame(log_inner, style="Card.TFrame", padding=8)
        log_wrap.pack(fill=tk.X)

        log_scroll = ttk.Scrollbar(log_wrap)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log = tk.Text(log_wrap, height=6, state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(side=tk.LEFT, fill=tk.X, expand=True)
        style_text(self.log)
        log_scroll.config(command=self.log.yview)
        self.log.config(yscrollcommand=log_scroll.set)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _card(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        frame = ttk.LabelFrame(parent, text=f" {title} ", style="Card.TLabelframe")
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        inner = ttk.Frame(frame, style="Card.TFrame", padding=12)
        inner.pack(fill=tk.BOTH, expand=True)
        return inner

    def _build_window_panel(self) -> None:
        panel = ttk.Frame(self.content_host, style="Panel.TFrame")
        self._panels["window"] = panel

        target_card = self._card(panel, "TARGET WINDOW")
        row = ttk.Frame(target_card, style="Card.TFrame")
        row.pack(fill=tk.X)

        self.window_combo = ttk.Combobox(
            row, textvariable=self.window_var, state="readonly"
        )
        self.window_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(row, text="Refresh", command=self.refresh_windows).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        zone_card = self._card(panel, "SCAN ZONE")
        zone_btns = ttk.Frame(zone_card, style="Card.TFrame")
        zone_btns.pack(fill=tk.X)

        ttk.Button(zone_btns, text="Set Zone", command=self.set_scan_zone).pack(
            side=tk.LEFT
        )
        ttk.Button(zone_btns, text="Clear Zone", command=self.clear_scan_zone).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        self.scan_zone_label = ttk.Label(
            zone_card, text="Full window", style="DimCard.TLabel"
        )
        self.scan_zone_label.pack(anchor=tk.W, pady=(10, 0))

        ttk.Label(
            zone_card,
            text="Drag a rectangle to limit where images are searched.",
            style="DimCard.TLabel",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(6, 0))

    def _build_targets_panel(self) -> None:
        panel = ttk.Frame(self.content_host, style="Panel.TFrame")
        self._panels["targets"] = panel

        card = self._card(panel, "TARGET IMAGES")
        btns = ttk.Frame(card, style="Card.TFrame")
        btns.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(btns, text="Add Images", command=self.add_targets).pack(side=tk.LEFT)
        ttk.Button(btns, text="Remove Selected", command=self.remove_selected).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        list_wrap = ttk.Frame(card, style="Card.TFrame")
        list_wrap.pack(fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(list_wrap)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.target_list = tk.Listbox(list_wrap, height=12)
        self.target_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        style_listbox(self.target_list)
        scroll.config(command=self.target_list.yview)
        self.target_list.config(yscrollcommand=scroll.set)

        ttk.Label(
            card,
            text="Clicks immediately when a match is found.",
            style="DimCard.TLabel",
        ).pack(anchor=tk.W, pady=(8, 0))

    def _build_rules_panel(self) -> None:
        panel = ttk.Frame(self.content_host, style="Panel.TFrame")
        self._panels["rules"] = panel

        card = self._card(panel, "CONDITIONAL RULES")
        btns = ttk.Frame(card, style="Card.TFrame")
        btns.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(btns, text="Add Rule", command=self.add_click_rule).pack(side=tk.LEFT)
        ttk.Button(btns, text="Set Rule Zone", command=self.set_rule_scan_zone).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(btns, text="Clear Rule Zone", command=self.clear_rule_scan_zone).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(btns, text="Remove Selected", command=self.remove_click_rule).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        list_wrap = ttk.Frame(card, style="Card.TFrame")
        list_wrap.pack(fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(list_wrap)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.rules_list = tk.Listbox(list_wrap, height=12)
        self.rules_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        style_listbox(self.rules_list)
        scroll.config(command=self.rules_list.yview)
        self.rules_list.config(yscrollcommand=scroll.set)

        ttk.Label(
            card,
            text=(
                "Primary clicks only when subsection also matches. "
                "Each rule can have its own scan zone (purple) separate from the "
                "target scan zone on the Window tab."
            ),
            style="DimCard.TLabel",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(8, 0))

    def _build_settings_panel(self) -> None:
        panel = ttk.Frame(self.content_host, style="Panel.TFrame")
        self._panels["settings"] = panel

        card = self._card(panel, "DETECTION")
        self._add_slider(card, "Primary confidence", self.threshold_var, 0.5, 0.99, 0.01)
        self._add_slider(card, "Scan interval (sec)", self.interval_var, 0.1, 2.0, 0.1)

        timing = self._card(panel, "TIMING & LIMITS")
        self._add_slider(timing, "Click cooldown (sec)", self.cooldown_var, 0.5, 10.0, 0.5)

        limit_row = ttk.Frame(timing, style="Card.TFrame")
        limit_row.pack(fill=tk.X, pady=6)
        ttk.Label(limit_row, text="Click limit", style="Card.TLabel", width=20).pack(
            side=tk.LEFT
        )
        ttk.Spinbox(
            limit_row,
            from_=1,
            to=50,
            width=6,
            textvariable=self.click_limit_var,
        ).pack(side=tk.LEFT, padx=(4, 8))
        ttk.Label(
            limit_row, text="clicks before long pause", style="DimCard.TLabel"
        ).pack(side=tk.LEFT)

        self._add_slider(
            timing, "Pause after limit (sec)", self.limit_pause_var, 10.0, 300.0, 5.0
        )

        hotkey_card = self._card(panel, "HOTKEY")
        hk_row = ttk.Frame(hotkey_card, style="Card.TFrame")
        hk_row.pack(fill=tk.X)

        self.hotkey_label = ttk.Label(
            hotkey_card,
            text=f"Start / Stop: {format_hotkey(self._hotkey_combo)}",
            style="Card.TLabel",
        )
        self.hotkey_label.pack(anchor=tk.W, pady=(0, 8))

        ttk.Button(hk_row, text="Set Hotkey", command=self.begin_hotkey_capture).pack(
            side=tk.LEFT
        )
        self.hotkey_status = ttk.Label(
            hotkey_card, text="Works globally while app is open.", style="DimCard.TLabel"
        )
        self.hotkey_status.pack(anchor=tk.W, pady=(8, 0))

        appearance = self._card(panel, "APPEARANCE")

        presets_row = ttk.Frame(appearance, style="Card.TFrame")
        presets_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(presets_row, text="Presets", style="Card.TLabel", width=10).pack(
            side=tk.LEFT
        )
        for preset in THEME_PRESETS:
            ttk.Button(
                presets_row,
                text=preset.name,
                command=lambda p=preset: self._apply_theme_preset(p),
            ).pack(side=tk.LEFT, padx=(4, 0))

        fonts_row = ttk.Frame(appearance, style="Card.TFrame")
        fonts_row.pack(fill=tk.X, pady=(0, 10))

        ui_font_col = ttk.Frame(fonts_row, style="Card.TFrame")
        ui_font_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Label(ui_font_col, text="UI font", style="Card.TLabel").pack(anchor=tk.W)
        self._ui_font_choices = available_fonts(self, FONT_CHOICES_UI)
        self._ui_font_var = tk.StringVar(value=Fonts.UI)
        self.ui_font_combo = ttk.Combobox(
            ui_font_col,
            textvariable=self._ui_font_var,
            values=self._ui_font_choices,
            state="readonly",
            width=22,
        )
        self.ui_font_combo.pack(fill=tk.X, pady=(4, 0))
        self.ui_font_combo.bind("<<ComboboxSelected>>", self._on_ui_font_changed)

        mono_font_col = ttk.Frame(fonts_row, style="Card.TFrame")
        mono_font_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(mono_font_col, text="Lists / log font", style="Card.TLabel").pack(
            anchor=tk.W
        )
        self._mono_font_choices = available_fonts(self, FONT_CHOICES_MONO)
        self._mono_font_var = tk.StringVar(value=Fonts.MONO)
        self.mono_font_combo = ttk.Combobox(
            mono_font_col,
            textvariable=self._mono_font_var,
            values=self._mono_font_choices,
            state="readonly",
            width=22,
        )
        self.mono_font_combo.pack(fill=tk.X, pady=(4, 0))
        self.mono_font_combo.bind("<<ComboboxSelected>>", self._on_mono_font_changed)

        target_row = ttk.Frame(appearance, style="Card.TFrame")
        target_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(target_row, text="Editing", style="Card.TLabel", width=10).pack(
            side=tk.LEFT
        )
        self._color_target_var = tk.StringVar(value="Accent")
        target_names = [name for name, _ in COLOR_TARGETS]
        self.color_target_combo = ttk.Combobox(
            target_row,
            textvariable=self._color_target_var,
            values=target_names,
            state="readonly",
            width=14,
        )
        self.color_target_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.color_target_combo.bind("<<ComboboxSelected>>", self._on_color_target_changed)

        swatch_row = ttk.Frame(appearance, style="Card.TFrame")
        swatch_row.pack(fill=tk.X, pady=(0, 10))
        self._color_swatches: dict[str, tk.Canvas] = {}
        self._swatch_cells: list[tuple[tk.Frame, tk.Label]] = []
        for name, _key in COLOR_TARGETS:
            cell = tk.Frame(swatch_row, bg=Colors.CARD)
            cell.pack(side=tk.LEFT, padx=(0, 8))
            cv = tk.Canvas(
                cell,
                width=30,
                height=30,
                bg=Colors.CARD,
                highlightthickness=1,
                highlightbackground=Colors.BORDER,
                cursor="hand2",
            )
            cv.pack()
            cv.bind(
                "<Button-1>",
                lambda _e, n=name: self._select_color_target(n),
            )
            label = tk.Label(
                cell,
                text=name,
                bg=Colors.CARD,
                fg=Colors.TEXT_DIM,
                font=ui_font(7),
            )
            label.pack(pady=(2, 0))
            self._color_swatches[name] = cv
            self._swatch_cells.append((cell, label))

        wheel_row = ttk.Frame(appearance, style="Card.TFrame")
        wheel_row.pack(fill=tk.X)

        self.color_wheel = ColorWheelWidget(
            wheel_row, on_color=self._on_color_picked, bg=Colors.CARD
        )
        self.color_wheel.pack(side=tk.LEFT)

        wheel_side = ttk.Frame(wheel_row, style="Card.TFrame", padding=(12, 0, 0, 0))
        wheel_side.pack(side=tk.LEFT, fill=tk.Y)

        self.color_target_title = ttk.Label(
            wheel_side,
            text="Accent color",
            style="Card.TLabel",
        )
        self.color_target_title.pack(anchor=tk.W)
        ttk.Label(
            wheel_side,
            text="Use the wheel for hue, the bar for brightness,\nand + / − to lighten or darken.",
            style="DimCard.TLabel",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 10))

        ttk.Button(wheel_side, text="Reset to Axon", command=self._reset_theme).pack(
            anchor=tk.W
        )

        self.color_hex_label = ttk.Label(
            wheel_side, text=Colors.ACCENT.upper(), style="DimCard.TLabel"
        )
        self.color_hex_label.pack(anchor=tk.W, pady=(8, 0))
        self._refresh_color_swatches()

    def _build_discord_panel(self) -> None:
        panel = ttk.Frame(self.content_host, style="Panel.TFrame")
        self._panels["discord"] = panel

        card = self._card(panel, "COMMUNITY")
        ttk.Label(
            card,
            text="Join the Discord server for help, updates, and discussion.",
            style="Card.TLabel",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(0, 12))

        ttk.Button(
            card,
            text="Join Discord Server",
            style="Accent.TButton",
            command=self.open_discord,
        ).pack(anchor=tk.W)

        ttk.Label(
            card,
            text=DISCORD_INVITE_URL,
            style="DimCard.TLabel",
        ).pack(anchor=tk.W, pady=(10, 0))

    def open_discord(self) -> None:
        webbrowser.open(DISCORD_INVITE_URL)
        self.log_message("Opened Discord invite in browser.")

    def _on_ui_font_changed(self, _event: object = None) -> None:
        set_ui_font(self._ui_font_var.get())
        refresh_widget_styles(self)
        self.log_message(f"UI font: {Fonts.UI}")

    def _on_mono_font_changed(self, _event: object = None) -> None:
        set_mono_font(self._mono_font_var.get())
        refresh_widget_styles(self)
        self.log_message(f"Log font: {Fonts.MONO}")

    def _refresh_font_widgets(self) -> None:
        self.status_pill.configure(font=ui_font(8, bold=True))
        for _cell, label in self._swatch_cells:
            label.configure(font=ui_font(7))

    def _apply_theme_preset(self, preset: ThemePreset) -> None:
        apply_theme_preset(preset)
        self._sync_color_editor_to_target()
        refresh_widget_styles(self)
        self.color_wheel.set_frame_bg(Colors.CARD, border=Colors.BORDER)
        self.log_message(f"Applied theme preset: {preset.name}")

    def _select_color_target(self, name: str) -> None:
        self._color_target_var.set(name)
        self._sync_color_editor_to_target()

    def _on_color_target_changed(self, _event: object = None) -> None:
        self._sync_color_editor_to_target()

    def _sync_color_editor_to_target(self) -> None:
        target = self._color_target_var.get()
        hex_color = get_color_for_target(target)
        self.color_target_title.config(text=f"{target} color")
        self.color_hex_label.config(text=hex_color.upper())
        self.color_wheel.set_color(hex_color)
        self._refresh_color_swatches()

    def _refresh_color_swatches(self) -> None:
        for cell, label in self._swatch_cells:
            cell.configure(bg=Colors.CARD)
            label.configure(bg=Colors.CARD)
        for name, canvas in self._color_swatches.items():
            hex_color = get_color_for_target(name)
            canvas.configure(bg=Colors.CARD)
            canvas.delete("all")
            canvas.create_rectangle(
                2, 2, 28, 28, fill=hex_color, outline=Colors.BORDER, width=1
            )
            selected = self._color_target_var.get() == name
            canvas.configure(
                highlightbackground=Colors.ACCENT if selected else Colors.BORDER,
                highlightthickness=2 if selected else 1,
            )

    def _on_color_picked(self, hex_color: str) -> None:
        target = self._color_target_var.get()
        key = target_key_for_label(target)
        if key is None:
            set_accent_color(hex_color)
        else:
            set_background_color(key, hex_color)
        self.color_hex_label.config(text=hex_color.upper())
        refresh_widget_styles(self)
        self.color_wheel.set_frame_bg(Colors.CARD, border=Colors.BORDER)
        self._refresh_color_swatches()

    def _reset_theme(self) -> None:
        reset_theme_colors()
        self._ui_font_var.set(Fonts.UI)
        self._mono_font_var.set(Fonts.MONO)
        self._sync_color_editor_to_target()
        refresh_widget_styles(self)
        self.color_wheel.set_frame_bg(Colors.CARD, border=Colors.BORDER)
        self.log_message("Theme reset to Axon preset.")

    def begin_hotkey_capture(self) -> None:
        if self._capturing_hotkey:
            return
        self._capturing_hotkey = True
        self.hotkey_status.config(text="Press a key combination now…")
        self._hotkey_manager.unregister()
        HotkeyManager.capture_async(self._on_hotkey_captured)

    def _on_hotkey_captured(self, combo: str | None, error: str | None) -> None:
        def finish() -> None:
            self._capturing_hotkey = False
            if error or not combo:
                self.hotkey_status.config(text=error or "Hotkey capture cancelled.")
                self._register_hotkey(self._hotkey_combo)
                return
            self._hotkey_combo = combo
            ok, msg = self._register_hotkey(combo)
            display = format_hotkey(combo)
            self.hotkey_label.config(text=f"Start / Stop: {display}")
            self._hotkey_display.set(f"Hotkey: {display}")
            self.hotkey_status.config(text=msg if ok else msg)
            if ok:
                self.log_message(f"Hotkey set to {display}.")

        self.after(0, finish)

    def _register_hotkey(self, combo: str) -> tuple[bool, str]:
        return self._hotkey_manager.register(combo)

    def _show_panel(self, key: str) -> None:
        titles = {
            "window": "Window",
            "targets": "Targets",
            "rules": "Rules",
            "settings": "Settings",
            "discord": "Discord",
        }
        self.page_title.config(text=titles.get(key, key.title()))

        for name, btn in self._nav_buttons.items():
            set_nav_active(btn, name == key)

        self._active_panel = key
        panel = self._panels[key]
        panel.place(relx=0, rely=0, relwidth=1, relheight=1)
        panel.lift()

    def _add_slider(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.DoubleVar,
        from_: float,
        to: float,
        step: float,
    ) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill=tk.X, pady=6)

        ttk.Label(row, text=label, style="Card.TLabel", width=20).pack(side=tk.LEFT)
        scale = ttk.Scale(
            row,
            from_=from_,
            to=to,
            variable=variable,
            orient=tk.HORIZONTAL,
            command=lambda _v: self._sync_slider_label(value_label, variable, step),
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))

        value_label = ttk.Label(row, text="", style="Card.TLabel", width=8)
        value_label.pack(side=tk.LEFT)
        self._sync_slider_label(value_label, variable, step)

    def _sync_slider_label(
        self, label: ttk.Label, variable: tk.DoubleVar, step: float
    ) -> None:
        value = variable.get()
        if step < 0.05:
            label.config(text=f"{value:.2f}")
        else:
            label.config(text=f"{value:.1f}")

    def _set_status(self, text: str, *, running: bool = False) -> None:
        self._status_var.set(text.upper())
        if running:
            self.status_pill.configure(bg="#1a2e1a", fg=Colors.SUCCESS)
        else:
            self.status_pill.configure(bg=Colors.INPUT, fg=Colors.TEXT_DIM)

    def _on_scan_frame(self, update: ScanFrameUpdate) -> None:
        def apply() -> None:
            if self._scan_preview is None or not self._scan_preview.winfo_exists():
                return
            self._scan_preview.update_scan(
                update.analysis,
                click_blocked=update.click_blocked,
                clicked=update.clicked,
            )

        self.after(0, apply)

    def _tick_scan_ui(self) -> None:
        self._scan_ui_tick_id = None
        if self._scanner is None or not self._scanner.running:
            return

        state = self._scanner.get_timer_state()
        if self._scan_preview is not None and self._scan_preview.winfo_exists():
            self._scan_preview.pin_to_target()
            self._scan_preview.update_timer(state)
        self._update_loop_tracker(state)
        self._update_scan_status_timer(state)
        self._scan_ui_tick_id = self.after(100, self._tick_scan_ui)

    def _update_loop_tracker(self, state) -> None:
        self._last_scan_loops = state.scan_loops
        self._last_total_clicks = state.total_clicks
        self._last_burst_cycles = state.burst_cycles
        self._last_waits_triggered = state.waits_triggered
        self._loop_tracker_var.set(
            f"Loops: {state.scan_loops:,} · Clicks: {state.total_clicks:,} · "
            f"Waits: {state.waits_triggered:,}"
        )

    def _update_scan_status_timer(self, state) -> None:
        if state.limit_pause_remaining > 0:
            text = f"Scanning · Loop {state.scan_loops:,} · Pause {state.limit_pause_remaining:.1f}s"
        elif state.click_cooldown_remaining > 0:
            text = f"Scanning · Loop {state.scan_loops:,} · CD {state.click_cooldown_remaining:.1f}s"
        else:
            text = f"Scanning · Loop {state.scan_loops:,}"
        self._set_status(text, running=True)

    def _open_scan_preview(self, hwnd: int, window_title: str) -> None:
        if self._scan_preview is not None and self._scan_preview.winfo_exists():
            self._scan_preview.destroy()
        self._scan_preview = ScanPreviewWindow(self, hwnd, window_title)

    def _close_scan_preview(self) -> None:
        if self._scan_ui_tick_id is not None:
            self.after_cancel(self._scan_ui_tick_id)
            self._scan_ui_tick_id = None
        if self._scan_preview is not None and self._scan_preview.winfo_exists():
            self._scan_preview.destroy()
        self._scan_preview = None

    def log_message(self, message: str) -> None:
        def append() -> None:
            self.log.config(state=tk.NORMAL)
            self.log.insert(tk.END, message + "\n")
            self.log.see(tk.END)
            self.log.config(state=tk.DISABLED)

        self.after(0, append)

    def refresh_windows(self) -> None:
        self._windows = list_visible_windows()
        titles = [title for _, title in self._windows]
        self.window_combo["values"] = titles
        if titles and not self.window_var.get():
            self.window_combo.current(0)
        self.log_message(f"Found {len(titles)} windows.")

    def add_targets(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select target images",
            filetypes=[
                ("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                ("All files", "*.*"),
            ],
        )
        added = 0
        for raw in paths:
            path = Path(raw)
            if any(t.path == path for t in self._targets):
                continue
            try:
                target = load_target(path)
            except ValueError as exc:
                messagebox.showerror("Invalid image", str(exc))
                continue
            self._targets.append(target)
            self.target_list.insert(tk.END, target.name)
            added += 1
        if added:
            self.log_message(f"Added {added} target image(s).")

    def remove_selected(self) -> None:
        selection = list(self.target_list.curselection())
        if not selection:
            return
        for index in reversed(selection):
            self.target_list.delete(index)
            del self._targets[index]
        self.log_message("Removed selected target(s).")

    def add_click_rule(self) -> None:
        primary_path = filedialog.askopenfilename(
            title="Select primary image (click target)",
            filetypes=[
                ("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                ("All files", "*.*"),
            ],
        )
        if not primary_path:
            return

        subsection_path = filedialog.askopenfilename(
            title="Select subsection image (must also match)",
            filetypes=[
                ("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                ("All files", "*.*"),
            ],
        )
        if not subsection_path:
            return

        try:
            primary = load_target(Path(primary_path))
            subsection = load_target(Path(subsection_path))
        except ValueError as exc:
            messagebox.showerror("Invalid image", str(exc))
            return

        dialog = SubsectionThresholdDialog(
            self,
            primary_name=primary.name,
            subsection_name=subsection.name,
            default=self.threshold_var.get(),
        )
        if dialog.result is None:
            return

        rule = ClickRule(
            primary=primary,
            subsection=subsection,
            subsection_threshold=dialog.result,
        )
        self._click_rules.append(rule)
        self.rules_list.insert(tk.END, rule.label)
        self.log_message(f"Added rule: {rule.label}")

    def _selected_rule_index(self) -> int | None:
        selection = self.rules_list.curselection()
        if not selection:
            return None
        return int(selection[0])

    def _refresh_rules_list(self, *, select_index: int | None = None) -> None:
        self.rules_list.delete(0, tk.END)
        for rule in self._click_rules:
            self.rules_list.insert(tk.END, rule.label)
        if select_index is not None and 0 <= select_index < len(self._click_rules):
            self.rules_list.selection_set(select_index)
            self.rules_list.activate(select_index)

    def set_rule_scan_zone(self) -> None:
        index = self._selected_rule_index()
        if index is None:
            messagebox.showwarning("No rule", "Select a rule first.")
            return

        hwnd = self._selected_hwnd()
        if hwnd is None:
            messagebox.showwarning("No window", "Select a target window first.")
            return

        rule = self._click_rules[index]
        picker = RegionPickerDialog(
            self,
            hwnd=hwnd,
            window_title=self.window_var.get(),
            existing=rule.scan_region,
            dialog_title=f"Set rule scan zone — {rule.primary.name}",
        )
        self.wait_window(picker)
        if picker.result is None and not picker.use_full_window:
            return

        new_region = None if picker.use_full_window else picker.result
        self._click_rules[index] = replace(rule, scan_region=new_region)
        self._refresh_rules_list(select_index=index)
        if new_region is None:
            self.log_message(f"Rule zone cleared for {rule.primary.name}.")
        else:
            self.log_message(
                f"Rule zone set for {rule.primary.name}: {new_region.label}"
            )

    def clear_rule_scan_zone(self) -> None:
        index = self._selected_rule_index()
        if index is None:
            messagebox.showwarning("No rule", "Select a rule first.")
            return

        rule = self._click_rules[index]
        if rule.scan_region is None:
            return

        self._click_rules[index] = replace(rule, scan_region=None)
        self._refresh_rules_list(select_index=index)
        self.log_message(f"Rule zone cleared for {rule.primary.name}.")

    def set_scan_zone(self) -> None:
        hwnd = self._selected_hwnd()
        if hwnd is None:
            messagebox.showwarning("No window", "Select a target window first.")
            return

        picker = RegionPickerDialog(
            self,
            hwnd=hwnd,
            window_title=self.window_var.get(),
            existing=self._scan_region,
        )
        self.wait_window(picker)
        if picker.result is None and not picker.use_full_window:
            return

        if picker.use_full_window:
            self._scan_region = None
            self.scan_zone_label.config(text="Full window")
            self.log_message("Scan zone: full window.")
            return

        self._scan_region = picker.result
        self.scan_zone_label.config(text=picker.result.label)
        self.log_message(f"Scan zone set: {picker.result.label}")

    def clear_scan_zone(self) -> None:
        self._scan_region = None
        self.scan_zone_label.config(text="Full window")
        self.log_message("Scan zone cleared (full window).")

    def remove_click_rule(self) -> None:
        selection = list(self.rules_list.curselection())
        if not selection:
            return
        for index in reversed(selection):
            self.rules_list.delete(index)
            del self._click_rules[index]
        self.log_message("Removed selected click rule(s).")

    def _selected_hwnd(self) -> int | None:
        title = self.window_var.get()
        for hwnd, win_title in self._windows:
            if win_title == title:
                return hwnd
        return None

    def toggle_scan(self) -> None:
        if self._scanner and self._scanner.running:
            self.stop_scan()
            return
        self.start_scan()

    def start_scan(self) -> None:
        hwnd = self._selected_hwnd()
        if hwnd is None:
            messagebox.showwarning("No window", "Select a target window first.")
            return
        if not self._targets and not self._click_rules:
            messagebox.showwarning(
                "Nothing to scan",
                "Add target images and/or a conditional click rule.",
            )
            return

        self._scanner = WindowScanner(
            hwnd=hwnd,
            targets=list(self._targets),
            click_rules=list(self._click_rules),
            threshold=self.threshold_var.get(),
            scan_region=self._scan_region,
            interval_sec=self.interval_var.get(),
            cooldown_sec=self.cooldown_var.get(),
            click_limit=max(1, int(self.click_limit_var.get())),
            limit_pause_sec=self.limit_pause_var.get(),
            on_status=self.log_message,
            on_scan_frame=self._on_scan_frame,
        )
        self._open_scan_preview(hwnd, self.window_var.get())
        self._loop_tracker_var.set("Loops: 0 · Clicks: 0 · Waits: 0")
        self._last_scan_loops = 0
        self._last_total_clicks = 0
        self._last_burst_cycles = 0
        self._last_waits_triggered = 0
        self._scanner.start()
        self.start_btn.config(text="STOP", style="Danger.TButton")
        self._set_status("Scanning", running=True)
        self._tick_scan_ui()
        zone = self._scan_region.label if self._scan_region else "full window"
        self.log_message(f"Watching window: {self.window_var.get()} (zone: {zone})")

    def stop_scan(self) -> None:
        if self._scanner:
            state = self._scanner.get_timer_state()
            self._update_loop_tracker(state)
            self._scanner.stop()
            self._scanner = None
            self.log_message(
                f"Session summary — loops: {self._last_scan_loops:,}, "
                f"clicks: {self._last_total_clicks:,}, "
                f"waits: {self._last_waits_triggered:,} "
                f"({self._last_burst_cycles:,} long pauses)"
            )
        self._close_scan_preview()
        self.start_btn.config(text="START", style="Accent.TButton")
        self._set_status("Idle", running=False)

    def open_test_detection(self) -> None:
        hwnd = self._selected_hwnd()
        if hwnd is None:
            messagebox.showwarning("No window", "Select a target window first.")
            return
        if not self._targets and not self._click_rules:
            messagebox.showwarning(
                "Nothing to test",
                "Add target images and/or a conditional click rule.",
            )
            return

        if self._test_window is not None and self._test_window.winfo_exists():
            self._test_window.destroy()

        self._test_window = TestDetectionWindow(
            master=self,
            hwnd=hwnd,
            window_title=self.window_var.get(),
            targets=list(self._targets),
            click_rules=list(self._click_rules),
            threshold=self.threshold_var.get(),
            scan_region=self._scan_region,
        )
        self.log_message("Ran test detection preview.")

    def on_close(self) -> None:
        self.stop_scan()
        self._hotkey_manager.unregister()
        self.destroy()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
