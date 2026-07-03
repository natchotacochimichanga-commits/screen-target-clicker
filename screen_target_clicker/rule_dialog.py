"""Dialog for setting subsection match confidence when adding a click rule."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .ui_theme import Colors, apply_theme


class SubsectionThresholdDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        primary_name: str,
        subsection_name: str,
        default: float = 0.85,
        *,
        confirm_text: str = "Add Rule",
        dialog_title: str = "Subsection Confidence",
    ) -> None:
        super().__init__(master)
        self.title(dialog_title)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        apply_theme(self)

        self._result: float | None = None
        self.threshold_var = tk.DoubleVar(value=default)

        body = ttk.Frame(self, style="Panel.TFrame", padding=16)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            body,
            text=f"Primary: {primary_name}\nSubsection: {subsection_name}",
            style="Panel.TLabel",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(
            body,
            text="Subsection match confidence (primary uses global setting):",
            style="Dim.TLabel",
        ).pack(anchor=tk.W)

        row = ttk.Frame(body, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=8)

        scale = ttk.Scale(
            row,
            from_=0.5,
            to=0.99,
            variable=self.threshold_var,
            orient=tk.HORIZONTAL,
            command=lambda _v: self._sync_label(),
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.value_label = ttk.Label(row, width=8, style="Panel.TLabel")
        self.value_label.pack(side=tk.LEFT)
        self._sync_label()

        buttons = ttk.Frame(body, style="Panel.TFrame")
        buttons.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(
            buttons, text=confirm_text, style="Accent.TButton", command=self._confirm
        ).pack(side=tk.RIGHT, padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.wait_window()

    @property
    def result(self) -> float | None:
        return self._result

    def _sync_label(self) -> None:
        self.value_label.config(text=f"{self.threshold_var.get():.2f}")

    def _confirm(self) -> None:
        self._result = self.threshold_var.get()
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()
