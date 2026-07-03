"""One-shot detection preview with confidence scores and visual markers."""



from __future__ import annotations



import tkinter as tk

from tkinter import messagebox, ttk



import cv2

from PIL import Image, ImageTk



from .detection_analysis import analyze_detection

from .matcher import TargetImage

from .rules import ClickRule

from .scan_region import ScanRegion

from .ui_theme import Colors, apply_theme, style_text

from .window_capture import capture_window





class TestDetectionWindow(tk.Toplevel):

    def __init__(

        self,

        master: tk.Misc,

        hwnd: int,

        window_title: str,

        targets: list[TargetImage],

        click_rules: list[ClickRule],

        threshold: float,

        scan_region: ScanRegion | None,

    ) -> None:

        super().__init__(master)

        self.title(f"Test Detection — {window_title}")

        self.geometry("900x640")

        self.minsize(640, 480)

        apply_theme(self)

        self.configure(bg=Colors.BG)



        self._hwnd = hwnd

        self._targets = targets

        self._click_rules = click_rules

        self._threshold = threshold

        self._scan_region = scan_region

        self._photo: ImageTk.PhotoImage | None = None



        self._build_ui()

        self.run_test()



    def _build_ui(self) -> None:

        toolbar = ttk.Frame(self, padding=8)

        toolbar.pack(fill=tk.X)



        ttk.Button(toolbar, text="Run Again", style="Accent.TButton", command=self.run_test).pack(

            side=tk.LEFT

        )

        ttk.Label(

            toolbar,

            text="Green = pass · Orange = below threshold · P/S = primary/subsection",

        ).pack(side=tk.LEFT, padx=(12, 0))



        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)

        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))



        preview_frame = ttk.LabelFrame(

            body, text=" PREVIEW ", style="Card.TLabelframe", padding=4

        )

        body.add(preview_frame, weight=3)



        canvas_wrap = ttk.Frame(preview_frame)

        canvas_wrap.pack(fill=tk.BOTH, expand=True)



        y_scroll = ttk.Scrollbar(canvas_wrap, orient=tk.VERTICAL)

        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        x_scroll = ttk.Scrollbar(canvas_wrap, orient=tk.HORIZONTAL)

        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)



        self.canvas = tk.Canvas(

            canvas_wrap,

            bg=Colors.INPUT,

            xscrollcommand=x_scroll.set,

            yscrollcommand=y_scroll.set,

            highlightthickness=0,

        )

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        x_scroll.config(command=self.canvas.xview)

        y_scroll.config(command=self.canvas.yview)



        results_frame = ttk.LabelFrame(

            body, text=" RESULTS ", style="Card.TLabelframe", padding=8

        )

        body.add(results_frame, weight=1)



        results_scroll = ttk.Scrollbar(results_frame)

        results_scroll.pack(side=tk.RIGHT, fill=tk.Y)



        self.results = tk.Text(

            results_frame,

            width=34,

            wrap=tk.WORD,

            state=tk.DISABLED,

            yscrollcommand=results_scroll.set,

        )

        self.results.pack(fill=tk.BOTH, expand=True)

        style_text(self.results)

        results_scroll.config(command=self.results.yview)



    def run_test(self) -> None:

        try:

            screen, _, _ = capture_window(self._hwnd)

        except Exception as exc:

            messagebox.showerror("Capture failed", str(exc), parent=self)

            return



        analysis = analyze_detection(

            screen,

            self._targets,

            self._click_rules,

            self._threshold,

            self._scan_region,

        )

        self._show_image(analysis.annotated)

        self._set_results(analysis.results_text)



    def _show_image(self, bgr_image) -> None:

        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)

        pil = Image.fromarray(rgb)



        max_w, max_h = 680, 520

        w, h = pil.size

        scale = min(max_w / w, max_h / h, 1.0)

        if scale < 1.0:

            pil = pil.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)



        self._photo = ImageTk.PhotoImage(pil)

        self.canvas.delete("all")

        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._photo)

        self.canvas.config(scrollregion=(0, 0, pil.width, pil.height))



    def _set_results(self, text: str) -> None:

        self.results.config(state=tk.NORMAL)

        self.results.delete("1.0", tk.END)

        self.results.insert(tk.END, text)

        self.results.config(state=tk.DISABLED)


