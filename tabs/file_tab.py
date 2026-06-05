from __future__ import annotations

# HomeCinemaCrop file_tab v40

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from HomeCinemaCrop_core import *

def _build_file_tab(self):
    f = self.tab_file
    f.columnconfigure(1, weight=1)
    ttk.Label(f, text="Quelldatei (meist MakeMKV 16:9)").grid(row=0, column=0, sticky="w", pady=(0, 4))
    ttk.Entry(f, textvariable=self.source_var).grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8))
    ttk.Button(f, text="Durchsuchen", command=self.pick_video).grid(row=1, column=2, sticky="ew")

    ttk.Label(f, text="CSV-Datei").grid(row=2, column=0, sticky="w", pady=(18, 4))
    ttk.Entry(f, textvariable=self.csv_var).grid(row=3, column=0, columnspan=2, sticky="ew", padx=(0, 8))
    btns = ttk.Frame(f)
    btns.grid(row=3, column=2, sticky="ew")
    ttk.Button(btns, text="Öffnen", command=self.pick_csv_open).pack(side="left", fill="x", expand=True)
    ttk.Button(btns, text="Speichern unter", command=self.pick_csv_save).pack(side="left", fill="x", expand=True, padx=(6, 0))
    ttk.Button(f, text="CSV erstellen", style="Big.TButton", command=self.run_create_csv).grid(row=4, column=1, sticky="e", pady=(8, 0))

    ttk.Label(f, text="Vorschau MP4").grid(row=5, column=0, sticky="w", pady=(18, 4))
    ttk.Entry(f, textvariable=self.preview_var).grid(row=6, column=0, columnspan=2, sticky="ew", padx=(0, 8))
    ttk.Button(f, text="Speichern unter", command=self.pick_preview_save).grid(row=6, column=2, sticky="ew")

    ttk.Label(f, text="Finales Video").grid(row=7, column=0, sticky="w", pady=(18, 4))
    ttk.Entry(f, textvariable=self.output_var).grid(row=8, column=0, columnspan=2, sticky="ew", padx=(0, 8))
    ttk.Button(f, text="Speichern unter", command=self.pick_output_save).grid(row=8, column=2, sticky="ew")

    hint = "Alle Reiter werden aktiv, sobald eine Quelle und eine vorhandene CSV geladen sind. Alternativ kannst du die CSV hier neu erstellen."
    ttk.Label(f, text=hint, style="Subtitle.TLabel").grid(row=9, column=0, columnspan=3, sticky="w", pady=(22, 0))

def pick_video(self):
    path = filedialog.askopenfilename(filetypes=[("Videos", "*.mp4 *.mkv *.mov *.avi *.m4v *.ts"), ("Alle Dateien", "*.*")])
    if path:
        self.source_var.set(path)
        self._autofill_outputs(Path(path))
        self.load_video_info()
        if hasattr(self, "refresh_media_tracks"):
            self.refresh_media_tracks()
        self.update_precrop_preview()
        self._update_project_state()

def pick_csv_open(self):
    path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Alle Dateien", "*.*")])
    if path:
        self.csv_var.set(path)
        self._update_project_state()
        self._log(f"CSV geladen: {path}")

def pick_csv_save(self):
    path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
    if path:
        self.csv_var.set(path)
        self._update_project_state()

def pick_preview_save(self):
    path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4")])
    if path:
        self.preview_var.set(path)

def pick_output_save(self):
    path = filedialog.asksaveasfilename(defaultextension=".mkv", filetypes=[("MKV", "*.mkv"), ("MP4", "*.mp4"), ("Alle Dateien", "*.*")])
    if path:
        self.output_var.set(path)

def _autofill_outputs(self, source: Path):
    base = source.with_suffix("")
    if not self.csv_var.get():
        self.csv_var.set(str(base) + "_crop.csv")
    if not self.preview_var.get():
        self.preview_var.set(str(base) + "_preview.mp4")
    if not self.output_var.get():
        self.output_var.set(str(base) + "_16x9.mkv")

def load_video_info(self):
    try:
        source = Path(self.source_var.get())
        if source.is_file():
            self.video_info = get_video_info(source)
            info = self.video_info
            aspect = info.width / info.height if info.height else 0
            hdr = "HDR/PQ" if (info.color_transfer or "").lower() in {"smpte2084", "pq"} else ""
            self.info_var.set(f"Quelle: {source.name} | {info.width}x{info.height} | {aspect:.3f}:1 | {info.fps:.3f} FPS | {info.frames} Frames | {info.pix_fmt or ''} {hdr}")
            if abs(aspect - (4 / 3)) < 0.03 or aspect < 1.50:
                self.crop_needed_var.set(False)
                self.precrop_mode_var.set("Keine (0)")
            else:
                self.crop_needed_var.set(True)
                self.precrop_mode_var.set("Manuell")
            self.on_crop_needed_changed(update_preview=False)
            self._update_precrop_info()
    except Exception as exc:
        messagebox.showerror("Fehler", str(exc))

def run_create_csv(self):
    def job():
        source, csv_path, _, _ = self._validate_common()
        create_center_csv(source, csv_path, self._progress_callback, self._cancelled)
    self._run_worker("Center-CSV wird erstellt ...", job)
