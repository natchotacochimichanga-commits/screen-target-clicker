"""Desktop GUI for screen-target-clicker."""

from __future__ import annotations

import json
import os
import subprocess
import tkinter as tk
import webbrowser
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .color_wheel import ColorWheelWidget
from .config_store import (
    CONFIG_VERSION,
    auto_config_path,
    config_directory,
    load_config_file,
    rule_from_dict,
    save_config_file,
    scan_region_from_dict,
    scan_region_to_dict,
)
from .hotkey_manager import HotkeyManager, format_hotkey
from .instance import (
    default_hotkey_for_instance,
    instance_number,
    launch_another_instance,
    window_title_for_instance,
)
from .matcher import TargetImage, load_target
from .region_picker import RegionPickerDialog
from .rule_dialog import SubsectionThresholdDialog
from .rules import ClickRule
from .scan_region import ScanRegion
from .scan_preview import ScanPreviewWindow
from .scanner import ScanFrameUpdate, WindowScanner
from .test_detection import TestDetectionWindow
from .tooltip import add_tooltip
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
from .window_claims import claim_window, get_blocked_hwnds, release_claim

DISCORD_INVITE_URL = "https://discord.gg/mRfnuHC8f"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self._instance_number = instance_number()
        self.title(window_title_for_instance(self._instance_number))
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
        self._hotkey_combo = default_hotkey_for_instance(self._instance_number)
        self._hotkey_manager = HotkeyManager(lambda: self.after(0, self.toggle_scan))
        self._capturing_hotkey = False
        self._autosave_after_id: str | None = None
        self._window_search_var = tk.StringVar()
        self._slider_rows: list[tuple[ttk.Scale, tk.DoubleVar, float]] = []
        self._loading_config = False

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
        self._bind_shortcuts()
        self._bind_autosave_traces()
        self.refresh_windows()
        self._load_auto_config()
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
        ttk.Label(brand, text="v1.2 · Atlas", style="SubBrand.TLabel").pack(
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
        ).pack(fill=tk.X, pady=(0, 6))

        ttk.Button(
            actions, text="New Instance", command=self.open_new_instance
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

        log_header = ttk.Frame(log_inner, style="Card.TFrame", padding=(8, 8, 8, 0))
        log_header.pack(fill=tk.X)
        ttk.Button(log_header, text="Clear Log", command=self.clear_log).pack(side=tk.RIGHT)

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

        search_row = ttk.Frame(target_card, style="Card.TFrame")
        search_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(search_row, text="Search", style="Card.TLabel", width=8).pack(
            side=tk.LEFT
        )
        search_entry = ttk.Entry(search_row, textvariable=self._window_search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._window_search_var.trace_add("write", lambda *_: self._filter_window_list())

        row = ttk.Frame(target_card, style="Card.TFrame")
        row.pack(fill=tk.X)

        self.window_combo = ttk.Combobox(
            row, textvariable=self.window_var, state="readonly"
        )
        self.window_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.window_combo.bind("<<ComboboxSelected>>", self._on_window_selected)

        ttk.Button(row, text="Refresh", command=self.refresh_windows).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Label(
            target_card,
            text="Each window can only be selected in one app instance at a time.",
            style="DimCard.TLabel",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(10, 0))

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
        ttk.Button(btns, text="Show in Explorer", command=self.reveal_selected_target).pack(
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
        self.target_list.bind("<<ListboxSelect>>", self._on_target_selected)

        self.target_path_label = ttk.Label(
            card, text="", style="DimCard.TLabel", wraplength=520
        )
        self.target_path_label.pack(anchor=tk.W, pady=(8, 0))

        ttk.Label(
            card,
            text="Clicks immediately when a match is found.",
            style="DimCard.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))

    def _build_rules_panel(self) -> None:
        panel = ttk.Frame(self.content_host, style="Panel.TFrame")
        self._panels["rules"] = panel

        card = self._card(panel, "CONDITIONAL RULES")
        btns = ttk.Frame(card, style="Card.TFrame")
        btns.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(btns, text="Add Rule", command=self.add_click_rule).pack(side=tk.LEFT)
        ttk.Button(btns, text="Edit Rule", command=self.edit_click_rule).pack(
            side=tk.LEFT, padx=(8, 0)
        )
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
        self._add_slider(
            card,
            "Primary confidence",
            self.threshold_var,
            0.5,
            0.99,
            0.01,
            tooltip="Higher = fewer false clicks. Lower = more sensitive matching.",
        )
        self._add_slider(
            card,
            "Scan interval (sec)",
            self.interval_var,
            0.1,
            2.0,
            0.1,
            tooltip="How often the target window is scanned.",
        )

        timing = self._card(panel, "TIMING & LIMITS")
        self._add_slider(
            timing,
            "Click cooldown (sec)",
            self.cooldown_var,
            0.5,
            10.0,
            0.5,
            tooltip="Minimum wait after any click before the next click.",
        )

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
            timing,
            "Pause after limit (sec)",
            self.limit_pause_var,
            10.0,
            300.0,
            5.0,
            tooltip="How long scanning waits after hitting the click limit.",
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
        if self._instance_number > 1:
            ttk.Label(
                hotkey_card,
                text=f"This instance defaults to {format_hotkey(default_hotkey_for_instance(self._instance_number))}.",
                style="DimCard.TLabel",
                wraplength=520,
            ).pack(anchor=tk.W, pady=(6, 0))

        config_card = self._card(panel, "CONFIG FILES")
        config_btns = ttk.Frame(config_card, style="Card.TFrame")
        config_btns.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(config_btns, text="Save Config...", command=self.save_config_as).pack(
            side=tk.LEFT
        )
        ttk.Button(config_btns, text="Load Config...", command=self.load_config_from).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(config_btns, text="Open Config Folder", command=self.open_config_folder).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        self.config_path_label = ttk.Label(
            config_card,
            text=f"Auto-save: {auto_config_path(self._instance_number)}",
            style="DimCard.TLabel",
            wraplength=520,
        )
        self.config_path_label.pack(anchor=tk.W)
        ttk.Label(
            config_card,
            text="Your setup saves automatically while you work and on exit.",
            style="DimCard.TLabel",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(6, 0))
        ttk.Label(
            config_card,
            text="Shortcuts: Ctrl+S save now · Ctrl+L load · Delete removes selected target/rule",
            style="DimCard.TLabel",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(4, 0))

        appearance = self._card(panel, "APPEARANCE")

        presets_header = ttk.Frame(appearance, style="Card.TFrame")
        presets_header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(presets_header, text="Presets", style="Card.TLabel", width=10).pack(
            side=tk.LEFT
        )
        presets_wrap = ttk.Frame(appearance, style="Card.TFrame")
        presets_wrap.pack(fill=tk.X, pady=(0, 10))
        for index, preset in enumerate(THEME_PRESETS):
            row = index // 4
            if row == 0:
                parent = presets_wrap
                if index == 0:
                    presets_row1 = ttk.Frame(presets_wrap, style="Card.TFrame")
                    presets_row1.pack(fill=tk.X, pady=(0, 4))
                parent = presets_row1
            else:
                if index == 4:
                    presets_row2 = ttk.Frame(presets_wrap, style="Card.TFrame")
                    presets_row2.pack(fill=tk.X)
                parent = presets_row2
            ttk.Button(
                parent,
                text=preset.name,
                command=lambda p=preset: self._apply_theme_preset(p),
            ).pack(side=tk.LEFT, padx=(0 if index % 4 == 0 else 4, 0))

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

        ttk.Button(wheel_side, text="Reset to Atlas", command=self._reset_theme).pack(
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

    def open_new_instance(self) -> None:
        launch_another_instance()
        self.log_message(f"Opened new app instance (#{self._instance_number + 1}).")

    def export_config(self) -> dict:
        theme_colors = {
            label: get_color_for_target(label).lower() for label, _key in COLOR_TARGETS
        }
        return {
            "version": CONFIG_VERSION,
            "window_title": self.window_var.get(),
            "targets": [str(target.path) for target in self._targets],
            "scan_region": scan_region_to_dict(self._scan_region),
            "click_rules": [
                {
                    "primary": str(rule.primary.path),
                    "subsection": str(rule.subsection.path),
                    "subsection_threshold": rule.subsection_threshold,
                    "scan_region": scan_region_to_dict(rule.scan_region),
                }
                for rule in self._click_rules
            ],
            "settings": {
                "threshold": self.threshold_var.get(),
                "interval": self.interval_var.get(),
                "cooldown": self.cooldown_var.get(),
                "click_limit": int(self.click_limit_var.get()),
                "limit_pause": self.limit_pause_var.get(),
                "hotkey": self._hotkey_combo,
            },
            "theme": {
                "colors": theme_colors,
                "ui_font": Fonts.UI,
                "mono_font": Fonts.MONO,
            },
        }

    def apply_config(self, data: dict, *, source: str) -> None:
        if self._scanner and self._scanner.running:
            self.stop_scan()

        self._loading_config = True
        try:
            settings = data.get("settings", {})
            if isinstance(settings, dict):
                if "threshold" in settings:
                    self.threshold_var.set(float(settings["threshold"]))
                if "interval" in settings:
                    self.interval_var.set(float(settings["interval"]))
                if "cooldown" in settings:
                    self.cooldown_var.set(float(settings["cooldown"]))
                if "click_limit" in settings:
                    self.click_limit_var.set(int(settings["click_limit"]))
                if "limit_pause" in settings:
                    self.limit_pause_var.set(float(settings["limit_pause"]))
                if settings.get("hotkey"):
                    self._hotkey_combo = str(settings["hotkey"]).strip().lower()

            theme = data.get("theme", {})
            if isinstance(theme, dict):
                colors = theme.get("colors", {})
                if isinstance(colors, dict):
                    for label, _key in COLOR_TARGETS:
                        hex_color = colors.get(label)
                        if not isinstance(hex_color, str):
                            continue
                        key = target_key_for_label(label)
                        if key is None:
                            set_accent_color(hex_color)
                        else:
                            set_background_color(key, hex_color)
                if theme.get("ui_font"):
                    set_ui_font(str(theme["ui_font"]))
                    self._ui_font_var.set(Fonts.UI)
                if theme.get("mono_font"):
                    set_mono_font(str(theme["mono_font"]))
                    self._mono_font_var.set(Fonts.MONO)

            self._targets.clear()
            self.target_list.delete(0, tk.END)
            for raw_path in data.get("targets", []):
                path = Path(str(raw_path))
                if not path.is_file():
                    self.log_message(f"Config: missing target image {path.name}")
                    continue
                try:
                    target = load_target(path)
                except ValueError as exc:
                    self.log_message(f"Config: skipped target {path.name} ({exc})")
                    continue
                self._targets.append(target)
                self.target_list.insert(tk.END, target.name)

            self._click_rules.clear()
            self.rules_list.delete(0, tk.END)
            for entry in data.get("click_rules", []):
                if not isinstance(entry, dict):
                    continue
                parsed = rule_from_dict(entry)
                if parsed is None:
                    self.log_message("Config: skipped invalid click rule entry.")
                    continue
                primary_path = Path(parsed.primary_path)
                subsection_path = Path(parsed.subsection_path)
                if not primary_path.is_file() or not subsection_path.is_file():
                    self.log_message("Config: skipped rule with missing image(s).")
                    continue
                try:
                    primary = load_target(primary_path)
                    subsection = load_target(subsection_path)
                except ValueError as exc:
                    self.log_message(f"Config: skipped rule ({exc})")
                    continue
                rule = ClickRule(
                    primary=primary,
                    subsection=subsection,
                    subsection_threshold=parsed.subsection_threshold,
                    scan_region=parsed.scan_region,
                )
                self._click_rules.append(rule)
                self.rules_list.insert(tk.END, rule.label)

            self._scan_region = scan_region_from_dict(data.get("scan_region"))
            if self._scan_region is None:
                self.scan_zone_label.config(text="Full window")
            else:
                self.scan_zone_label.config(text=self._scan_region.label)

            window_title = str(data.get("window_title", "")).strip()
            if window_title:
                titles = [title for _, title in self._windows]
                if window_title in titles:
                    self.window_var.set(window_title)
                    self._claim_selected_window(silent=True)
                else:
                    self.window_var.set("")
                    release_claim()
                    self.log_message(
                        f"Config: window '{window_title}' is not available right now."
                    )

            refresh_widget_styles(self)
            if hasattr(self, "color_wheel"):
                self.color_wheel.set_frame_bg(Colors.CARD, border=Colors.BORDER)
                if hasattr(self.color_wheel, "refresh_fonts"):
                    self.color_wheel.refresh_fonts()
            self._sync_color_editor_to_target()
            self._refresh_color_swatches()
            self._refresh_font_widgets()

            display = format_hotkey(self._hotkey_combo)
            self.hotkey_label.config(text=f"Start / Stop: {display}")
            self._hotkey_display.set(f"Hotkey: {display}")
            ok, msg = self._register_hotkey(self._hotkey_combo)
            self.hotkey_status.config(text=msg)
        finally:
            self._loading_config = False

        self.log_message(f"Loaded config from {source}.")

    def save_config_to(self, path: Path) -> None:
        save_config_file(path, self.export_config())

    def save_auto_config(self) -> None:
        try:
            self.save_config_to(auto_config_path(self._instance_number))
        except OSError as exc:
            self.log_message(f"Auto-save failed: {exc}")

    def _load_auto_config(self) -> None:
        path = auto_config_path(self._instance_number)
        if not path.is_file():
            return
        try:
            data = load_config_file(path)
            self.apply_config(data, source=str(path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.log_message(f"Auto-load failed: {exc}")

    def save_config_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save config",
            defaultextension=".json",
            filetypes=[("Config files", "*.json"), ("All files", "*.*")],
            initialfile=f"screen-target-clicker-config-{self._instance_number}.json",
        )
        if not path:
            return
        try:
            self.save_config_to(Path(path))
            self.log_message(f"Saved config to {path}")
            messagebox.showinfo("Config saved", f"Saved to:\n{path}", parent=self)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)

    def load_config_from(self) -> None:
        path = filedialog.askopenfilename(
            title="Load config",
            filetypes=[("Config files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Load config",
            "Loading replaces your current targets, rules, zones, and settings.\n\nContinue?",
            parent=self,
        ):
            return
        try:
            data = load_config_file(Path(path))
            self.apply_config(data, source=path)
            self._mark_dirty()
            messagebox.showinfo("Config loaded", f"Loaded from:\n{path}", parent=self)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("Load failed", str(exc), parent=self)

    def open_config_folder(self) -> None:
        folder = config_directory()
        os.startfile(folder)
        self.log_message(f"Opened config folder: {folder}")

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
        self._mark_dirty()

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
        self.log_message("Theme reset to Atlas preset.")
        self._mark_dirty()

    def begin_hotkey_capture(self) -> None:
        if self._capturing_hotkey:
            return
        self._capturing_hotkey = True
        self.hotkey_status.config(text="Press a key combination now (Esc to cancel)…")
        self._hotkey_manager.unregister()
        HotkeyManager.capture_async(self._on_hotkey_captured)

    def _on_escape(self, _event: object = None) -> str | None:
        if self._capturing_hotkey:
            self._on_hotkey_captured(None, "Hotkey capture cancelled.")
            return "break"
        return None

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-s>", self._shortcut_save)
        self.bind("<Control-l>", self._shortcut_load)
        self.bind("<Delete>", self._shortcut_delete)
        self.bind("<Escape>", self._on_escape)

    def _shortcut_save(self, _event: object = None) -> str:
        self.save_auto_config()
        self.log_message("Config saved.")
        return "break"

    def _shortcut_load(self, _event: object = None) -> str:
        self.load_config_from()
        return "break"

    def _shortcut_delete(self, _event: object = None) -> str | None:
        if self._active_panel == "targets":
            self.remove_selected()
            return "break"
        if self._active_panel == "rules":
            self.remove_click_rule()
            return "break"
        return None

    def _bind_autosave_traces(self) -> None:
        for var in (
            self.threshold_var,
            self.interval_var,
            self.cooldown_var,
            self.limit_pause_var,
        ):
            var.trace_add("write", lambda *_: self._mark_dirty())
        self.click_limit_var.trace_add("write", lambda *_: self._mark_dirty())

    def _mark_dirty(self) -> None:
        if self._loading_config:
            return
        if self._autosave_after_id is not None:
            self.after_cancel(self._autosave_after_id)
        self._autosave_after_id = self.after(1500, self._run_autosave)

    def _run_autosave(self) -> None:
        self._autosave_after_id = None
        self.save_auto_config()

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
                self._mark_dirty()

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
        *,
        tooltip: str | None = None,
    ) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill=tk.X, pady=6)

        name_label = ttk.Label(row, text=label, style="Card.TLabel", width=20)
        name_label.pack(side=tk.LEFT)
        if tooltip:
            add_tooltip(name_label, tooltip)

        scale = ttk.Scale(
            row,
            from_=from_,
            to=to,
            variable=variable,
            orient=tk.HORIZONTAL,
            command=lambda _v: self._sync_slider_label(value_label, variable, step),
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))
        scale.bind("<ButtonRelease-1>", lambda _e: self._mark_dirty())

        value_label = ttk.Label(row, text="", style="Card.TLabel", width=8)
        value_label.pack(side=tk.LEFT)
        self._sync_slider_label(value_label, variable, step)
        self._slider_rows.append((scale, variable, step))

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
                block_reason=update.block_reason,
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
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"

        def append() -> None:
            self.log.config(state=tk.NORMAL)
            self.log.insert(tk.END, line + "\n")
            line_count = int(float(self.log.index("end-1c").split(".")[0]))
            if line_count > 500:
                self.log.delete("1.0", f"{line_count - 500}.0")
            self.log.see(tk.END)
            self.log.config(state=tk.DISABLED)

        self.after(0, append)

    def clear_log(self) -> None:
        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.config(state=tk.DISABLED)

    def _filter_window_list(self) -> None:
        query = self._window_search_var.get().strip().lower()
        if query:
            filtered = [
                (hwnd, title)
                for hwnd, title in self._windows
                if query in title.lower()
            ]
        else:
            filtered = self._windows

        titles = [title for _, title in filtered]
        current = self.window_var.get()
        if current and current not in titles:
            if any(title == current for _, title in self._windows):
                titles = [current, *titles]

        self.window_combo["values"] = titles
        if current in titles:
            self.window_var.set(current)
        elif titles:
            self.window_combo.current(0)
            self._claim_selected_window(silent=True)
        else:
            self.window_var.set("")
            release_claim()

    def refresh_windows(self) -> None:
        all_windows = list_visible_windows()
        blocked = get_blocked_hwnds(exclude_pid=os.getpid())
        self._windows = [(hwnd, title) for hwnd, title in all_windows if hwnd not in blocked]
        all_titles = [title for _, title in self._windows]

        previous = self.window_var.get()

        if previous and previous not in all_titles:
            taken = previous in [t for _, t in all_windows]
            self.window_var.set("")
            release_claim()
            if taken:
                self.log_message(
                    f"'{previous}' is already selected in another app instance."
                )
            else:
                self.log_message(f"Previous window '{previous}' is no longer available.")

        if all_titles and not self.window_var.get():
            self.window_var.set(all_titles[0])
            self._claim_selected_window(silent=True)
        elif self.window_var.get():
            self._claim_selected_window(silent=True)

        blocked_count = len(all_windows) - len(self._windows)
        message = f"Found {len(all_titles)} available window(s)."
        if blocked_count:
            message += f" {blocked_count} hidden (in use by other instance(s))."
        self.log_message(message)
        self._filter_window_list()

    def _on_window_selected(self, _event: object = None) -> None:
        self._claim_selected_window()

    def _claim_selected_window(self, *, silent: bool = False) -> bool:
        hwnd = self._selected_hwnd()
        if hwnd is None:
            release_claim()
            return False

        ok, blocker = claim_window(
            os.getpid(),
            hwnd,
            self.window_var.get(),
            self._instance_number,
        )
        if ok:
            if not silent:
                self.log_message(f"Selected window: {self.window_var.get()}")
            self._mark_dirty()
            return True

        release_claim()
        self.window_var.set("")
        if blocker:
            messagebox.showwarning(
                "Window unavailable",
                f"That window is already selected in {blocker}.",
                parent=self,
            )
            if not silent:
                self.log_message(f"Could not select window — already used by {blocker}.")
        self.refresh_windows()
        return False

    def add_targets(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select target images",
            filetypes=[
                ("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                ("All files", "*.*"),
            ],
        )
        added = 0
        skipped = 0
        for raw in paths:
            path = Path(raw)
            if any(t.path == path for t in self._targets):
                skipped += 1
                self.log_message(f"Already added: {path.name}")
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
            self._mark_dirty()
        elif paths and not added and not skipped:
            self.log_message("No target images were added.")

    def _on_target_selected(self, _event: object = None) -> None:
        selection = self.target_list.curselection()
        if not selection:
            self.target_path_label.config(text="")
            return
        target = self._targets[int(selection[0])]
        self.target_path_label.config(text=str(target.path))

    def reveal_selected_target(self) -> None:
        selection = self.target_list.curselection()
        if not selection:
            self.log_message("Select a target image first.")
            return
        path = self._targets[int(selection[0])].path
        if not path.is_file():
            self.log_message(f"File not found: {path.name}")
            return
        subprocess.run(["explorer", "/select,", str(path)], check=False)
        self.log_message(f"Revealed in Explorer: {path.name}")

    def remove_selected(self) -> None:
        selection = list(self.target_list.curselection())
        if not selection:
            self.log_message("Nothing selected to remove.")
            return
        for index in reversed(selection):
            self.target_list.delete(index)
            del self._targets[index]
        self.target_path_label.config(text="")
        self.log_message("Removed selected target(s).")
        self._mark_dirty()

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
        self._mark_dirty()

    def edit_click_rule(self) -> None:
        index = self._selected_rule_index()
        if index is None:
            self.log_message("Select a rule to edit.")
            return

        rule = self._click_rules[index]
        dialog = SubsectionThresholdDialog(
            self,
            primary_name=rule.primary.name,
            subsection_name=rule.subsection.name,
            default=rule.subsection_threshold,
            confirm_text="Save",
            dialog_title="Edit Rule Confidence",
        )
        if dialog.result is None:
            return

        self._click_rules[index] = replace(
            rule, subsection_threshold=dialog.result
        )
        self._refresh_rules_list(select_index=index)
        self.log_message(f"Updated rule: {self._click_rules[index].label}")
        self._mark_dirty()

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
        self._mark_dirty()

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
        self._mark_dirty()

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
            self._mark_dirty()
            return

        self._scan_region = picker.result
        self.scan_zone_label.config(text=picker.result.label)
        self.log_message(f"Scan zone set: {picker.result.label}")
        self._mark_dirty()

    def clear_scan_zone(self) -> None:
        self._scan_region = None
        self.scan_zone_label.config(text="Full window")
        self.log_message("Scan zone cleared (full window).")
        self._mark_dirty()

    def remove_click_rule(self) -> None:
        selection = list(self.rules_list.curselection())
        if not selection:
            self.log_message("Nothing selected to remove.")
            return
        for index in reversed(selection):
            self.rules_list.delete(index)
            del self._click_rules[index]
        self.log_message("Removed selected click rule(s).")
        self._mark_dirty()

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
        if not self._claim_selected_window():
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
            on_window_lost=lambda: self.after(0, self._on_scan_window_lost),
            target_title=self.window_var.get(),
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

    def _on_scan_window_lost(self) -> None:
        if self._scanner is None or not self._scanner.running:
            return
        title = self.window_var.get() or "Target window"
        self.stop_scan()
        self._set_status("Window closed", running=False)
        messagebox.showwarning(
            "Window closed",
            f"{title} is no longer available.\n\nScanning has been stopped.",
            parent=self,
        )

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
        self.save_auto_config()
        self._hotkey_manager.unregister()
        release_claim()
        self.destroy()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
