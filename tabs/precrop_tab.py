from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from HomeCinemaCrop_core import *

def _build_precrop_tab(self):
    f = self.tab_precrop
    f.columnconfigure(0, weight=1)

    left = ttk.LabelFrame(f, text="Vorschnitt einstellen", padding=12)
    left.grid(row=0, column=0, sticky="nw", padx=(0, 10))
    left.columnconfigure(0, weight=1)
    self.precrop_card = left

    top_line = ttk.Frame(left)
    top_line.grid(row=0, column=0, sticky="ew")
    self.crop_needed_check = ttk.Checkbutton(
        top_line,
        text="Vorschnitt nötig",
        variable=self.crop_needed_var,
        command=self.on_crop_needed_changed,
    )
    self.crop_needed_check.pack(side="left")

    size_box = ttk.LabelFrame(left, text="Größeninformationen", padding=10)
    size_box.grid(row=1, column=0, sticky="ew", pady=(12, 10))
    self.original_size_var = tk.StringVar(value="Originalgröße: -")
    self.current_size_var = tk.StringVar(value="Aktuelle Größe: -")
    ttk.Label(size_box, textvariable=self.original_size_var).pack(anchor="w", pady=(0, 4))
    ttk.Label(size_box, textvariable=self.current_size_var).pack(anchor="w")

    mode_box = ttk.LabelFrame(left, text="Beschnitt", padding=10)
    mode_box.grid(row=2, column=0, sticky="ew", pady=(0, 10))
    mode_box.columnconfigure(1, weight=1)
    self.precrop_mode_box = mode_box
    ttk.Label(mode_box, text="Modus").grid(row=0, column=0, sticky="w", padx=(0, 8))
    self.precrop_mode_combo = ttk.Combobox(
        mode_box,
        textvariable=self.precrop_mode_var,
        values=["Automatisch", "Manuell", "Keine (0)"],
        state="readonly",
        width=18,
    )
    self.precrop_mode_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
    self.precrop_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_precrop_mode_changed())
    self.auto_detect_button = ttk.Button(mode_box, text="Automatisch erkennen", command=self.suggest_4x3_precrop)
    self.auto_detect_button.grid(row=0, column=2, sticky="ew")
    ttk.Label(
        mode_box,
        text="Automatisch schlägt links/rechts einen 4:3-Bereich vor. Manuell erlaubt eigene Pixelwerte.",
        style="Subtitle.TLabel",
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

    crop_box = ttk.LabelFrame(left, text="Vorschnitt (Pixel)", padding=10)
    crop_box.grid(row=3, column=0, sticky="ew", pady=(0, 10))
    self.crop_pixel_box = crop_box
    for c in range(3):
        crop_box.columnconfigure(c, weight=1)

    ttk.Label(crop_box, text="Oben").grid(row=0, column=1, pady=(0, 2))
    self.spin_top = ttk.Spinbox(crop_box, from_=0, to=9999, increment=1, textvariable=self.crop_top_var, width=9, command=self.update_precrop_preview)
    self.spin_top.grid(row=1, column=1, pady=(0, 8))

    ttk.Label(crop_box, text="Links").grid(row=2, column=0, sticky="s", pady=(0, 2))
    ttk.Label(crop_box, text="Ergebnisbereich", foreground="blue").grid(row=2, column=1, sticky="s", pady=(0, 2))
    ttk.Label(crop_box, text="Rechts").grid(row=2, column=2, sticky="s", pady=(0, 2))
    self.spin_left = ttk.Spinbox(crop_box, from_=0, to=9999, increment=1, textvariable=self.crop_left_var, width=9, command=self.update_precrop_preview)
    self.spin_left.grid(row=3, column=0, padx=(0, 14))
    center_placeholder = tk.Canvas(crop_box, width=220, height=100, bg="#f5f5f5", highlightthickness=1, highlightbackground="#aaaaaa")
    center_placeholder.grid(row=3, column=1, padx=4, pady=2)
    center_placeholder.create_rectangle(8, 8, 212, 92, outline="#bbbbbb", dash=(4, 3))
    center_placeholder.create_text(110, 50, text="zugeschnittenes\nBasisbild", fill="blue", justify="center")
    self.spin_right = ttk.Spinbox(crop_box, from_=0, to=9999, increment=1, textvariable=self.crop_right_var, width=9, command=self.update_precrop_preview)
    self.spin_right.grid(row=3, column=2, padx=(14, 0))

    ttk.Label(crop_box, text="Unten").grid(row=4, column=1, pady=(10, 2))
    self.spin_bottom = ttk.Spinbox(crop_box, from_=0, to=9999, increment=1, textvariable=self.crop_bottom_var, width=9, command=self.update_precrop_preview)
    self.spin_bottom.grid(row=5, column=1)

    hint = (
        "Hier stellst du nur den festen Vorschnitt ein, z.B. schwarze Seitenränder aus MakeMKV entfernen.\n"
        "Ist deine Quelle schon echtes 4:3/IMAX, kannst du \"Vorschnitt nötig\" abwählen."
    )
    ttk.Label(left, text=hint, style="Subtitle.TLabel", justify="left").grid(row=4, column=0, sticky="w", pady=(4, 0))

    for var in (self.crop_left_var, self.crop_right_var, self.crop_top_var, self.crop_bottom_var):
        var.trace_add("write", lambda *_: self._update_precrop_info())
    self.on_crop_needed_changed(update_preview=False)

def _set_children_state(self, widget, state: str, exclude=()):
    for child in widget.winfo_children():
        if child in exclude:
            continue
        try:
            child.configure(state=state)
        except tk.TclError:
            pass
        self._set_children_state(child, state, exclude=exclude)

def on_crop_needed_changed(self, update_preview: bool = True):
    enabled = bool(self.crop_needed_var.get())
    state = "normal" if enabled else "disabled"
    for widget_name in ("precrop_mode_box", "crop_pixel_box"):
        widget = getattr(self, widget_name, None)
        if widget is not None:
            self._set_children_state(widget, state)
    if enabled:
        try:
            self.precrop_mode_combo.configure(state="readonly")
        except Exception:
            pass
        self.on_precrop_mode_changed(update_preview=False)
    else:
        # Quelle ist schon echtes 4:3/IMAX oder der Benutzer möchte keinen festen Vorschnitt.
        self.crop_left_var.set("0")
        self.crop_right_var.set("0")
        self.crop_top_var.set("0")
        self.crop_bottom_var.set("0")
    self._update_precrop_info()
    if update_preview:
        self.update_precrop_preview()

def on_precrop_mode_changed(self, update_preview: bool = True):
    if not self.crop_needed_var.get():
        return
    mode = self.precrop_mode_var.get()
    if mode == "Keine (0)":
        self.crop_left_var.set("0")
        self.crop_right_var.set("0")
        self.crop_top_var.set("0")
        self.crop_bottom_var.set("0")
        for w in (getattr(self, "spin_left", None), getattr(self, "spin_right", None), getattr(self, "spin_top", None), getattr(self, "spin_bottom", None)):
            if w is not None:
                w.configure(state="disabled")
    elif mode == "Automatisch":
        for w in (getattr(self, "spin_left", None), getattr(self, "spin_right", None), getattr(self, "spin_top", None), getattr(self, "spin_bottom", None)):
            if w is not None:
                w.configure(state="disabled")
        self.suggest_4x3_precrop(update_preview=False)
    else:
        for w in (getattr(self, "spin_left", None), getattr(self, "spin_right", None), getattr(self, "spin_top", None), getattr(self, "spin_bottom", None)):
            if w is not None:
                w.configure(state="normal")
    self._update_precrop_info()
    if update_preview:
        self.update_precrop_preview()

def clear_precrop(self):
    self.precrop_mode_var.set("Keine (0)")
    self.crop_left_var.set("0")
    self.crop_right_var.set("0")
    self.crop_top_var.set("0")
    self.crop_bottom_var.set("0")
    self.on_precrop_mode_changed()

def _get_precrop(self) -> PreCrop:
    if not self.crop_needed_var.get():
        return PreCrop(0, 0, 0, 0)
    return normalize_precrop(self.crop_left_var.get(), self.crop_right_var.get(), self.crop_top_var.get(), self.crop_bottom_var.get())

def _update_precrop_info(self):
    if not self.video_info:
        self.original_size_var.set("Originalgröße: -")
        self.current_size_var.set("Aktuelle Größe: -")
        return
    info = self.video_info
    self.original_size_var.set(f"Originalgröße: {info.width}x{info.height}")
    try:
        w, h = size_after_precrop(info.width, info.height, self._get_precrop())
        self.current_size_var.set(f"Aktuelle Größe: {w}x{h} | variabler 16:9-Ausschnitt: {w}x{crop_height(w)}")
    except Exception as exc:
        self.current_size_var.set(f"Aktuelle Größe: Fehler - {exc}")

def suggest_4x3_precrop(self, update_preview: bool = True):
    try:
        if not self.video_info:
            source, _, _, _ = self._validate_common()
            self.video_info = get_video_info(source)
        info = self.video_info
        target_w = int(round(info.height * 4 / 3))
        if target_w > info.width:
            raise RuntimeError("Die Quelle ist schmaler als 4:3. Seitlicher 4:3-Vorschnitt ist nicht möglich.")
        total_cut = info.width - target_w
        left = total_cut // 2
        right = total_cut - left
        self.crop_needed_var.set(True)
        self.precrop_mode_var.set("Automatisch")
        self.crop_left_var.set(str(left))
        self.crop_right_var.set(str(right))
        self.crop_top_var.set("0")
        self.crop_bottom_var.set("0")
        for w in (getattr(self, "spin_left", None), getattr(self, "spin_right", None), getattr(self, "spin_top", None), getattr(self, "spin_bottom", None)):
            if w is not None:
                w.configure(state="disabled")
        if update_preview:
            self.update_precrop_preview()
        self.status_var.set(f"4:3-Vorschlag gesetzt: links {left}, rechts {right}.")
    except Exception as exc:
        messagebox.showerror("Fehler", str(exc))
