#!/usr/bin/env python3
from __future__ import annotations

import queue
import threading
import time
import platform
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from HomeCinemaCrop_core import *

TRANSLATIONS_EN = {'Sprache': 'Language', 'Noch keine Quelle geladen.': 'No source loaded yet.', 'Datei': 'File', 'Vorschnitt': 'Pre-crop', 'Vorschau': 'Preview', 'Final-Render': 'Final render', 'Quelldatei (meist MakeMKV 16:9)': 'Source file (usually MakeMKV 16:9)', 'Durchsuchen': 'Browse', 'CSV-Datei': 'CSV file', 'Öffnen': 'Open', 'Speichern unter': 'Save as', 'CSV erstellen': 'Create CSV', 'Vorschau MP4': 'Preview MP4', 'Finales Video': 'Final video', 'Alle Reiter werden aktiv, sobald eine Quelle und eine vorhandene CSV geladen sind. Alternativ kannst du die CSV hier neu erstellen.': 'All tabs become active once a source and an existing CSV are loaded. Alternatively, you can create the CSV here.', 'Status / Protokoll': 'Status / log', 'Bereit.': 'Ready.', 'Pause': 'Pause', 'Abbrechen': 'Cancel', 'Vorschnitt einstellen': 'Set pre-crop', 'Vorschnitt nötig': 'Pre-crop needed', 'Größeninformationen': 'Size information', 'Originalgröße: -': 'Original size: -', 'Aktuelle Größe: -': 'Current size: -', 'Beschnitt': 'Crop', 'Modus': 'Mode', 'Automatisch': 'Automatic', 'Manuell': 'Manual', 'Keine (0)': 'None (0)', 'Automatisch erkennen': 'Auto detect', 'Vorschnitt (Pixel)': 'Pre-crop (pixels)', 'Oben': 'Top', 'Links': 'Left', 'Rechts': 'Right', 'Unten': 'Bottom', 'Ergebnisbereich': 'Result area', 'Bildvorschau / Frame-Auswahl': 'Image preview / frame selection', 'Vorschau (nur Ergebnisbereich)': 'Preview (result area only)', 'Vorschau-Frame für Anzeige:': 'Preview frame for display:', 'Position in %': 'Position in %', 'Bestimmter Frame': 'Specific frame', 'Bildvorschau aktualisieren': 'Refresh image preview', 'Vorschau-MP4 erstellen': 'Create preview MP4', 'Bereich für Vorschau-Video': 'Range for preview video', 'Frames': 'Frames', 'Sekunden / Zeit': 'Seconds / time', 'Start': 'Start', 'Ende': 'End', 'Zum Start springen': 'Jump to start', 'Zum Ende springen': 'Jump to end', 'Vorschau erstellen': 'Create preview', 'Final-Render-Bereich': 'Final render range', 'Welcher Teil soll gerendert werden?': 'Which part should be rendered?', 'Nur bestimmten Bereich rendern': 'Render only a specific range', 'Wie Vorschau-Bereich': 'Use preview range', 'Qualität / Codec': 'Quality / codec', 'Qualitäts-Vorlage': 'Quality preset', 'Codec': 'Codec', 'Preset': 'Preset', 'CRF / CQ Qualität': 'CRF / CQ quality', 'Film-/Grain-schonend encodieren (-tune grain, weniger Glättung)': 'Encode film/grain-friendly (-tune grain, less smoothing)', 'Zielauflösung / Skalierung': 'Target resolution / scaling', 'Ausgabegröße': 'Output size', 'Breite': 'Width', 'Höhe': 'Height', 'Scaler': 'Scaler', 'Erweiterte Encoder-Einstellungen': 'Advanced encoder settings', 'Pixelformat': 'Pixel format', 'Framerate': 'Frame rate', 'Metadaten übernehmen (-map_metadata 0)': 'Copy metadata (-map_metadata 0)', 'Kapitel übernehmen (-map_chapters 0)': 'Copy chapters (-map_chapters 0)', 'Anhänge/Fonts übernehmen (-c:t copy)': 'Copy attachments/fonts (-c:t copy)', 'x265 Zusatzparameter': 'x265 extra parameters', 'FFmpeg Zusatzargumente': 'FFmpeg extra arguments', 'Empfehlung für deine UHD-HDR-Quelle': 'Recommendation for your UHD HDR source', 'Final-Render starten': 'Start final render', 'Encoder': 'Encoder', 'Fehlende Python-Bibliothek': 'Missing Python library', 'OpenCV/NumPy konnte nicht geladen werden': 'OpenCV/NumPy could not be loaded', 'Normal hochwertig (CRF 16)': 'Normal high quality (CRF 16)', 'Quellnah / sehr hoch (CRF 12)': 'Source-like / very high (CRF 12)', 'Nahezu verlustfrei (CRF 10)': 'Almost lossless (CRF 10)', 'Extrem groß / Test (CRF 8)': 'Extremely large / test (CRF 8)', 'Benutzerdefiniert': 'Custom', 'Nativ nach Crop': 'Native after crop', 'UHD 3840x2160 hochskalieren': 'Upscale to UHD 3840x2160', 'Quellgröße hochskalieren': 'Upscale to source size', 'Quelle CFR erzwingen': 'Force source CFR', 'FPS Passthrough': 'FPS passthrough', 'Nicht anfassen': 'Do not touch', 'Auto / Quelle': 'Auto / source', 'Quelle exakt': 'Exact source', '10 Bit 4:2:0 (HDR/UHD)': '10-bit 4:2:0 (HDR/UHD)', '8 Bit 4:2:0 (SDR)': '8-bit 4:2:0 (SDR)', 'Für maximale Quellnähe: Nativ nach Crop, libx265, veryslow/slower, CRF 10–12, 10 Bit Auto, Quelle CFR erzwingen.': 'For maximum source fidelity: Native after crop, libx265, veryslow/slower, CRF 10–12, 10-bit auto, force source CFR.', 'Für UHD-kompatible Ausgabe: UHD 3840x2160 hochskalieren mit lanczos oder spline.': 'For UHD-compatible output: upscale to UHD 3840x2160 with lanczos or spline.', 'Audio, Untertitel, Kapitel, Metadaten und Anhänge werden auf Wunsch kopiert.': 'Audio, subtitles, chapters, metadata and attachments can be copied.', 'Kleiner CRF = bessere Qualität und größere Datei. Für UHD/HDR: libx265, slower/veryslow, CRF 10–12.': 'Lower CRF/CQ = better quality and larger file. For UHD/HDR: libx265, slower/veryslow, CRF/CQ 10–12.', 'Zeitangaben: z.B. 125, 00:02:05 oder 00:02:05.500': 'Time values: e.g. 125, 00:02:05 or 00:02:05.500', 'Standard: 25%. Alternativ kannst du direkt eine Frame-Nummer eingeben.': 'Default: 25%. Alternatively, enter a frame number directly.', 'Die Vorschau zeigt den eingestellten Ergebnisbereich. Der blaue Rahmen kommt aus der CSV-Position up/center/down.': 'The preview shows the configured result area. The blue frame comes from the CSV position up/center/down.', 'Ohne Haken wird der komplette Film gerendert. Zeitangaben: 125, 00:02:05 oder 00:02:05.500': 'Without the checkbox, the full movie is rendered. Time values: 125, 00:02:05 or 00:02:05.500', 'Nach Final-Render PC automatisch herunterfahren': 'Automatically shut down PC after final render', 'Zeit: noch nicht gestartet': 'Time: not started yet', 'Vergangen': 'Elapsed', 'Rest': 'Remaining', 'Fertig ca.': 'Estimated finish', 'wird berechnet': 'calculating', 'Herunterfahren': 'Shutdown', 'Der PC wird in ca. 60 Sekunden heruntergefahren.': 'The PC will shut down in about 60 seconds.', 'Automatisches Herunterfahren konnte nicht gestartet werden': 'Automatic shutdown could not be started', 'Fortsetzen': 'Resume'}

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # Windows DPI / Skalierungs-Fix
        try:
            self.tk.call("tk", "scaling", 1.0)
        except Exception:
            pass

        self.title(self._t("HomeCinemaCrop: IMAX (4:3) → 16:9"))
        self.geometry("1450x900")
        self.minsize(1000, 680)
        self.cancel_requested = False
        self.pause_requested = False
        self.worker: Optional[threading.Thread] = None
        self.queue: queue.Queue = queue.Queue()
        self.video_info: Optional[VideoInfo] = None
        self.preview_photo = None
        self.language_var = tk.StringVar(value="Deutsch")
        self.shutdown_after_render_var = tk.BooleanVar(value=False)
        self.timing_info_var = tk.StringVar(value="Zeit: noch nicht gestartet")
        self._worker_start_time = None
        self._current_task = None

        self.source_var = tk.StringVar()
        self.csv_var = tk.StringVar()
        self.preview_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.crop_needed_var = tk.BooleanVar(value=True)
        self.precrop_mode_var = tk.StringVar(value="Manuell")
        self.crop_left_var = tk.StringVar(value="0")
        self.crop_right_var = tk.StringVar(value="0")
        self.crop_top_var = tk.StringVar(value="0")
        self.crop_bottom_var = tk.StringVar(value="0")
        self.preview_start_var = tk.StringVar()
        self.preview_end_var = tk.StringVar()
        self.preview_mode_var = tk.StringVar(value="frames")
        self._preview_last_mode = "frames"
        self.render_start_var = tk.StringVar()
        self.render_end_var = tk.StringVar()
        self.render_mode_var = tk.StringVar(value="frames")
        self._render_last_mode = "frames"
        self.render_limited_var = tk.BooleanVar(value=False)
        self.encoder_engine_var = tk.StringVar(value="CPU (x264/x265)")
        self.codec_var = tk.StringVar(value="libx265")
        self.preset_var = tk.StringVar(value="slower")
        self.crf_var = tk.StringVar(value="12")
        self.quality_preset_var = tk.StringVar(value="Quellnah / sehr hoch (CRF 12)")
        self.tune_grain_var = tk.BooleanVar(value=True)
        self.pixel_format_mode_var = tk.StringVar(value="Auto / Quelle")
        self.output_size_mode_var = tk.StringVar(value="Nativ nach Crop")
        self.custom_width_var = tk.StringVar(value="3840")
        self.custom_height_var = tk.StringVar(value="2160")
        self.scale_flags_var = tk.StringVar(value="lanczos")
        self.fps_mode_var = tk.StringVar(value="Quelle CFR erzwingen")
        self.copy_metadata_var = tk.BooleanVar(value=True)
        self.copy_chapters_var = tk.BooleanVar(value=True)
        self.copy_attachments_var = tk.BooleanVar(value=True)
        self.x265_extra_params_var = tk.StringVar(value="")
        self.ffmpeg_extra_args_var = tk.StringVar(value="")
        self.precrop_preview_percent_var = tk.IntVar(value=25)
        self.precrop_preview_percent_text_var = tk.StringVar(value="25%")
        self.precrop_preview_mode_var = tk.StringVar(value="percent")
        self.precrop_preview_custom_frame_var = tk.StringVar(value="")
        self.precrop_preview_frame_info_var = tk.StringVar(value="Angezeigtes Frame: -")

        self._build_style()
        self._build_ui()
        self._update_project_state()
        self.after(100, self._poll_queue)
        if IMPORT_ERROR is not None:
            messagebox.showerror(self._t("Fehlende Python-Bibliothek"), f"{self._t('OpenCV/NumPy konnte nicht geladen werden')}:\n{IMPORT_ERROR}")

    def _t(self, text: str) -> str:
        if getattr(self, "language_var", None) is None or self.language_var.get() == "Deutsch":
            return text
        return TRANSLATIONS_EN.get(text, text)

    def on_language_changed(self, _event=None):
        # Oberfläche neu aufbauen, damit alle festen Texte sofort wechseln.
        for child in self.winfo_children():
            child.destroy()
        self.title(self._t("HomeCinemaCrop: IMAX (4:3) → 16:9"))
        self._build_style()
        self._build_ui()
        self._update_project_state()
        self._update_precrop_info()

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=10)
        style.configure("TButton", padding=6)
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TEntry", padding=4)

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="HomeCinemaCrop: IMAX (4:3) → 16:9", style="Title.TLabel").pack(side="left")
        self.project_status_var = tk.StringVar(value="Quelle: fehlt | CSV: fehlt")
        ttk.Label(header, textvariable=self.project_status_var, style="Subtitle.TLabel").pack(side="right", padx=(12, 0))
        lang_box = ttk.Frame(header)
        lang_box.pack(side="right", padx=(12, 0))
        ttk.Label(lang_box, text=self._t("Sprache")).pack(side="left", padx=(0, 6))
        language_combo = ttk.Combobox(lang_box, textvariable=self.language_var, values=["Deutsch", "English"], state="readonly", width=10)
        language_combo.pack(side="left")
        language_combo.bind("<<ComboboxSelected>>", self.on_language_changed)

        self.info_var = tk.StringVar(value=self._t("Noch keine Quelle geladen."))
        ttk.Label(root, textvariable=self.info_var, style="Subtitle.TLabel").pack(anchor="w", pady=(0, 8))

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, pady=(0,4))
        self.tab_file = ttk.Frame(self.nb, padding=14)
        self.tab_precrop = ttk.Frame(self.nb, padding=14)
        self.tab_preview = ttk.Frame(self.nb, padding=14)
        self.tab_render = ttk.Frame(self.nb, padding=14)
        self.nb.add(self.tab_file, text=self._t("Datei"))
        self.nb.add(self.tab_precrop, text=self._t("Vorschnitt"))
        self.nb.add(self.tab_preview, text=self._t("Vorschau"))
        self.nb.add(self.tab_render, text=self._t("Final-Render"))
        self._build_file_tab()
        self._build_precrop_tab()
        self._build_preview_tab()
        self._build_render_tab()

        status = ttk.LabelFrame(root, text="Status / Protokoll", padding=10)
        status.pack(fill="x", pady=(10, 0))
        top = ttk.Frame(status)
        top.pack(fill="x")
        self.status_var = tk.StringVar(value=self._t("Bereit."))
        ttk.Label(top, textvariable=self.status_var).pack(side="left", fill="x", expand=True)
        ttk.Label(top, textvariable=self.timing_info_var, style="Subtitle.TLabel").pack(side="left", padx=(12, 12))

        self.shutdown_check = ttk.Checkbutton(top, text=self._t("Nach Final-Render PC automatisch herunterfahren"), variable=self.shutdown_after_render_var)
        self.shutdown_check.pack(side="right", padx=(8, 0))
        self.pause_button = ttk.Button(top, text=self._t("Pause"), command=self.toggle_pause, state="disabled")
        self.pause_button.pack(side="right", padx=(8, 0))
        ttk.Button(top, text=self._t("Abbrechen"), command=self.cancel).pack(side="right")

        progress_row = ttk.Frame(status)
        progress_row.pack(fill="x", pady=(8, 8))
        self.progress_percent_var = tk.StringVar(value="0 %")
        ttk.Label(progress_row, textvariable=self.progress_percent_var, width=8).pack(side="left")
        self.progress = ttk.Progressbar(progress_row, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)

        self.log = tk.Text(status, height=3, wrap="word")
        self.log.pack(fill="x")
        self._apply_translations_to_widgets()

    def _apply_translations_to_widgets(self):
        if self.language_var.get() == "Deutsch":
            return
        def walk(widget):
            try:
                txt = widget.cget("text")
                if txt in TRANSLATIONS_EN:
                    widget.configure(text=TRANSLATIONS_EN[txt])
            except Exception:
                pass
            for child in widget.winfo_children():
                walk(child)
        walk(self)

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

    def _get_total_frames_for_preview(self) -> int:
        if self.video_info and self.video_info.frames > 0:
            return int(self.video_info.frames)
        source = Path(self.source_var.get())
        if source.is_file() and cv2 is not None:
            cap = cv2.VideoCapture(str(source))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            cap.release()
            return total
        return 0

    def _sync_preview_controls_to_frame(self, frame_no: int, total: Optional[int] = None):
        total = int(total or self._get_total_frames_for_preview() or 0)
        if frame_no < 1:
            frame_no = 1
        if total > 0:
            frame_no = min(frame_no, total)
            percent = int(round(((frame_no - 1) / max(total - 1, 1)) * 100))
        else:
            percent = int(self.precrop_preview_percent_var.get() or 0)
        percent = max(0, min(100, percent))
        self.precrop_preview_custom_frame_var.set(str(frame_no))
        self.precrop_preview_percent_var.set(percent)
        self.precrop_preview_percent_text_var.set(f"{percent}%")

    def _preview_percent_changed(self, value=None):
        try:
            percent = int(round(float(value if value is not None else self.precrop_preview_percent_var.get())))
        except Exception:
            percent = 25
        percent = max(0, min(100, percent))
        self.precrop_preview_percent_var.set(percent)
        self.precrop_preview_percent_text_var.set(f"{percent}%")
        self.precrop_preview_mode_var.set("percent")
        total = self._get_total_frames_for_preview()
        if total > 0:
            frame_no = int(round((percent / 100) * (total - 1))) + 1
            self.precrop_preview_custom_frame_var.set(str(frame_no))

    def _preview_frame_entry_changed(self, _event=None):
        self.precrop_preview_mode_var.set("frame")
        try:
            frame_no = int((self.precrop_preview_custom_frame_var.get() or "1").strip())
        except ValueError:
            return
        self._sync_preview_controls_to_frame(frame_no)

    def jump_precrop_preview_frame(self, delta: int):
        self.precrop_preview_mode_var.set("frame")
        try:
            current = int((self.precrop_preview_custom_frame_var.get() or "1").strip())
        except ValueError:
            current = 1
        total = self.video_info.frames if self.video_info and self.video_info.frames > 0 else None
        new_value = current + int(delta)
        if total:
            new_value = max(1, min(total, new_value))
        else:
            new_value = max(1, new_value)
        self.precrop_preview_custom_frame_var.set(str(new_value))
        self.update_precrop_preview()

    def _build_preview_tab(self):
        f = self.tab_preview
        f.columnconfigure(0, weight=0)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)

        left = ttk.Frame(f)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        left.columnconfigure(0, weight=1)

        right = ttk.LabelFrame(f, text="Vorschau (nur Ergebnisbereich)", padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        control = ttk.LabelFrame(left, text="Bildvorschau / Frame-Auswahl", padding=10)
        control.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        control.columnconfigure(1, weight=1)
        ttk.Label(control, text="Vorschau-Frame für Anzeige:").grid(row=0, column=0, columnspan=4, sticky="w")

        ttk.Radiobutton(control, text="Position in %", variable=self.precrop_preview_mode_var, value="percent", command=self.update_precrop_preview).grid(row=1, column=0, sticky="w", pady=(6, 2))
        ttk.Scale(control, from_=0, to=100, orient="horizontal", variable=self.precrop_preview_percent_var, command=self._preview_percent_changed).grid(row=1, column=1, columnspan=2, sticky="ew", pady=(6, 2), padx=(8, 8))
        ttk.Label(control, textvariable=self.precrop_preview_percent_text_var, width=5).grid(row=1, column=3, sticky="e", pady=(6, 2))

        ttk.Radiobutton(control, text="Bestimmter Frame", variable=self.precrop_preview_mode_var, value="frame", command=self.update_precrop_preview).grid(row=2, column=0, sticky="w", pady=(6, 2))
        frame_entry = ttk.Entry(control, textvariable=self.precrop_preview_custom_frame_var, width=12)
        frame_entry.grid(row=2, column=1, sticky="w", padx=(8, 8), pady=(6, 2))
        frame_entry.bind("<FocusIn>", lambda _event: self.precrop_preview_mode_var.set("frame"))
        frame_entry.bind("<Button-1>", lambda _event: self.precrop_preview_mode_var.set("frame"))
        frame_entry.bind("<Return>", lambda _event: (self._preview_frame_entry_changed(), self.update_precrop_preview()))
        frame_entry.bind("<FocusOut>", self._preview_frame_entry_changed)
        ttk.Button(control, text="-100", command=lambda: self.jump_precrop_preview_frame(-100)).grid(row=2, column=2, sticky="ew", padx=(0, 4), pady=(6, 2))
        ttk.Button(control, text="+100", command=lambda: self.jump_precrop_preview_frame(100)).grid(row=2, column=3, sticky="ew", pady=(6, 2))

        small = ttk.Frame(control)
        small.grid(row=3, column=1, columnspan=3, sticky="ew", pady=(2, 0))
        ttk.Button(small, text="-1000", command=lambda: self.jump_precrop_preview_frame(-1000)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(small, text="+1000", command=lambda: self.jump_precrop_preview_frame(1000)).pack(side="left", fill="x", expand=True)

        ttk.Button(control, text="Bildvorschau aktualisieren", command=self.update_precrop_preview).grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        ttk.Label(control, text="Standard: 25%. Alternativ kannst du direkt eine Frame-Nummer eingeben.", style="Subtitle.TLabel").grid(row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))

        render_preview_box = ttk.LabelFrame(left, text="Vorschau-MP4 erstellen", padding=10)
        render_preview_box.grid(row=1, column=0, sticky="ew")
        render_preview_box.columnconfigure(1, weight=1)
        ttk.Label(render_preview_box, text="Bereich für Vorschau-Video").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Radiobutton(render_preview_box, text="Frames", variable=self.preview_mode_var, value="frames", command=self.on_preview_range_mode_changed).grid(row=1, column=0, sticky="w", pady=(12, 2))
        ttk.Radiobutton(render_preview_box, text="Sekunden / Zeit", variable=self.preview_mode_var, value="time", command=self.on_preview_range_mode_changed).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(render_preview_box, text="Start").grid(row=1, column=1, sticky="w")
        ttk.Entry(render_preview_box, textvariable=self.preview_start_var, width=18).grid(row=2, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(render_preview_box, text="Ende").grid(row=1, column=2, sticky="w")
        ttk.Entry(render_preview_box, textvariable=self.preview_end_var, width=18).grid(row=2, column=2, sticky="ew")
        ttk.Button(render_preview_box, text="Zum Start springen", command=lambda: self.jump_preview_to_range_value(self.preview_start_var, self.preview_mode_var)).grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=(8, 0))
        ttk.Button(render_preview_box, text="Zum Ende springen", command=lambda: self.jump_preview_to_range_value(self.preview_end_var, self.preview_mode_var)).grid(row=3, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(render_preview_box, text="Vorschau erstellen", style="Big.TButton", command=self.run_preview).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(18, 0))
        ttk.Label(render_preview_box, text="Zeitangaben: z.B. 125, 00:02:05 oder 00:02:05.500", style="Subtitle.TLabel").grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.canvas = tk.Canvas(right, width=700, height=380, bg="#222222", highlightthickness=1, highlightbackground="#777777")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ttk.Label(right, textvariable=self.precrop_preview_frame_info_var, style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(right, text="Die Vorschau zeigt den eingestellten Ergebnisbereich. Der blaue Rahmen kommt aus der CSV-Position up/center/down.", style="Subtitle.TLabel").grid(row=2, column=0, sticky="w")

    def _build_render_tab(self):
        f = self.tab_render
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)

        left = ttk.Frame(f)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(f)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.columnconfigure(0, weight=1)

        range_box = ttk.LabelFrame(left, text="Final-Render-Bereich", padding=12)
        range_box.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        range_box.columnconfigure(1, weight=1)
        range_box.columnconfigure(2, weight=1)

        header = ttk.Frame(range_box)
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Welcher Teil soll gerendert werden?").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(header, text="Nur bestimmten Bereich rendern", variable=self.render_limited_var, command=self.on_render_limited_changed).grid(row=0, column=1, sticky="e")

        self.render_range_controls = ttk.Frame(range_box)
        self.render_range_controls.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.render_range_controls.columnconfigure(1, weight=1)
        self.render_range_controls.columnconfigure(2, weight=1)
        mode_col = ttk.Frame(self.render_range_controls)
        mode_col.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 14))
        ttk.Radiobutton(mode_col, text="Frames", variable=self.render_mode_var, value="frames", command=self.on_render_range_mode_changed).pack(anchor="w", pady=(0, 6))
        ttk.Radiobutton(mode_col, text="Sekunden / Zeit", variable=self.render_mode_var, value="time", command=self.on_render_range_mode_changed).pack(anchor="w")
        ttk.Label(self.render_range_controls, text="Start").grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(self.render_range_controls, text="Ende").grid(row=0, column=2, sticky="w")
        ttk.Entry(self.render_range_controls, textvariable=self.render_start_var, width=18).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(2, 0))
        ttk.Entry(self.render_range_controls, textvariable=self.render_end_var, width=18).grid(row=1, column=2, sticky="ew", pady=(2, 0))
        ttk.Button(self.render_range_controls, text="Wie Vorschau-Bereich", command=self.copy_preview_range_to_render).grid(row=2, column=1, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Label(range_box, text="Ohne Haken wird der komplette Film gerendert. Zeitangaben: 125, 00:02:05 oder 00:02:05.500", style="Subtitle.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        quality_box = ttk.LabelFrame(left, text="Qualität / Codec", padding=12)
        quality_box.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for c in range(3):
            quality_box.columnconfigure(c, weight=1)
        ttk.Label(quality_box, text="Qualitäts-Vorlage").grid(row=0, column=0, columnspan=3, sticky="w")
        preset_combo = ttk.Combobox(quality_box, textvariable=self.quality_preset_var, state="readonly", values=[
            "Normal hochwertig (CRF 16)",
            "Quellnah / sehr hoch (CRF 12)",
            "Nahezu verlustfrei (CRF 10)",
            "Extrem groß / Test (CRF 8)",
            "Benutzerdefiniert",
        ])
        preset_combo.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 8))
        preset_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_quality_preset_changed())

        ttk.Label(quality_box, text=self._t("Encoder")).grid(row=2, column=0, sticky="w")
        ttk.Combobox(quality_box, textvariable=self.encoder_engine_var, values=["CPU (x264/x265)", "NVIDIA NVENC (GPU)"], state="readonly", width=18).grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=(2, 0))
        ttk.Label(quality_box, text="Codec").grid(row=2, column=1, sticky="w")
        ttk.Combobox(quality_box, textvariable=self.codec_var, values=["libx265", "libx264"], state="readonly", width=14).grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=(2, 0))
        ttk.Label(quality_box, text="Preset").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(quality_box, textvariable=self.preset_var, values=["ultrafast", "fast", "medium", "slow", "slower", "veryslow"], width=14).grid(row=5, column=0, sticky="ew", padx=(0, 8), pady=(2, 0))
        ttk.Label(quality_box, text="CRF / CQ Qualität").grid(row=4, column=1, sticky="w", pady=(8, 0))
        ttk.Entry(quality_box, textvariable=self.crf_var, width=10).grid(row=5, column=1, sticky="ew", pady=(2, 0))
        ttk.Checkbutton(quality_box, text="Film-/Grain-schonend encodieren (-tune grain, weniger Glättung)", variable=self.tune_grain_var).grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(quality_box, text="Kleiner CRF = bessere Qualität und größere Datei. Für UHD/HDR: libx265, slower/veryslow, CRF 10–12.", style="Subtitle.TLabel").grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))

        size_box = ttk.LabelFrame(left, text="Zielauflösung / Skalierung", padding=12)
        size_box.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        size_box.columnconfigure(1, weight=1)
        ttk.Label(size_box, text="Ausgabegröße").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Combobox(size_box, textvariable=self.output_size_mode_var, state="readonly", values=["Nativ nach Crop", "UHD 3840x2160 hochskalieren", "Quellgröße hochskalieren", "Benutzerdefiniert"]).grid(row=0, column=1, columnspan=3, sticky="ew")
        ttk.Label(size_box, text="Breite").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(size_box, textvariable=self.custom_width_var, width=10).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(8, 0))
        ttk.Label(size_box, text="Höhe").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(size_box, textvariable=self.custom_height_var, width=10).grid(row=1, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(size_box, text="Scaler").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(size_box, textvariable=self.scale_flags_var, values=["lanczos", "spline", "bicubic", "bilinear"], width=14).grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(8, 0))
        ttk.Label(size_box, text="Nativ = keine künstliche Hochskalierung. UHD-Modus macht aus z.B. 2880x1620 wieder 3840x2160.", style="Subtitle.TLabel").grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))

        action_box = ttk.LabelFrame(left, text="Start", padding=12)
        action_box.grid(row=3, column=0, sticky="ew")
        action_box.columnconfigure(0, weight=1)
        ttk.Button(action_box, text="Final-Render starten", style="Big.TButton", command=self.run_render).grid(row=0, column=0, sticky="ew")
        ttk.Label(action_box, text="Audio, Untertitel, Kapitel, Metadaten und Anhänge werden auf Wunsch kopiert.", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))

        tech_box = ttk.LabelFrame(right, text="Erweiterte Encoder-Einstellungen", padding=12)
        tech_box.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        tech_box.columnconfigure(1, weight=1)
        ttk.Label(tech_box, text="Pixelformat").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Combobox(tech_box, textvariable=self.pixel_format_mode_var, state="readonly", values=["Auto / Quelle", "Quelle exakt", "10 Bit 4:2:0 (HDR/UHD)", "8 Bit 4:2:0 (SDR)"]).grid(row=0, column=1, sticky="ew")
        ttk.Label(tech_box, text="Framerate").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Combobox(tech_box, textvariable=self.fps_mode_var, state="readonly", values=["Quelle CFR erzwingen", "FPS Passthrough", "Nicht anfassen"]).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(tech_box, text="Metadaten übernehmen (-map_metadata 0)", variable=self.copy_metadata_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Checkbutton(tech_box, text="Kapitel übernehmen (-map_chapters 0)", variable=self.copy_chapters_var).grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(tech_box, text="Anhänge/Fonts übernehmen (-c:t copy)", variable=self.copy_attachments_var).grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Label(tech_box, text="x265 Zusatzparameter").grid(row=5, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(tech_box, textvariable=self.x265_extra_params_var).grid(row=5, column=1, sticky="ew", pady=(10, 0))
        ttk.Label(tech_box, text="z.B. aq-mode=3:aq-strength=0.9. Wird an -x265-params angehängt.", style="Subtitle.TLabel").grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(tech_box, text="FFmpeg Zusatzargumente").grid(row=7, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(tech_box, textvariable=self.ffmpeg_extra_args_var).grid(row=7, column=1, sticky="ew", pady=(10, 0))
        ttk.Label(tech_box, text="z.B. -movflags +faststart. Vorsicht: nur nutzen, wenn du weißt, was du setzt.", style="Subtitle.TLabel").grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 0))

        info_box = ttk.LabelFrame(right, text="Empfehlung für deine UHD-HDR-Quelle", padding=12)
        info_box.grid(row=1, column=0, sticky="ew")
        ttk.Label(info_box, text="Für maximale Quellnähe: Nativ nach Crop, libx265, veryslow/slower, CRF 10–12, 10 Bit Auto, Quelle CFR erzwingen.", style="Subtitle.TLabel", wraplength=520).pack(anchor="w")
        ttk.Label(info_box, text="Für UHD-kompatible Ausgabe: UHD 3840x2160 hochskalieren mit lanczos oder spline.", style="Subtitle.TLabel", wraplength=520).pack(anchor="w", pady=(8, 0))

        self.on_render_limited_changed()
        self.on_quality_preset_changed()

    def on_quality_preset_changed(self):
        preset = self.quality_preset_var.get()
        if preset == "Normal hochwertig (CRF 16)":
            self.codec_var.set("libx265")
            self.preset_var.set("slow")
            self.crf_var.set("16")
        elif preset == "Quellnah / sehr hoch (CRF 12)":
            self.codec_var.set("libx265")
            self.preset_var.set("slower")
            self.crf_var.set("12")
        elif preset == "Nahezu verlustfrei (CRF 10)":
            self.codec_var.set("libx265")
            self.preset_var.set("veryslow")
            self.crf_var.set("10")
        elif preset == "Extrem groß / Test (CRF 8)":
            self.codec_var.set("libx265")
            self.preset_var.set("veryslow")
            self.crf_var.set("8")

    def _collect_encoder_settings(self) -> EncoderSettings:
        try:
            crf_value = float(str(self.crf_var.get()).replace(",", "."))
        except ValueError as exc:
            raise RuntimeError("CRF muss eine Zahl sein, z.B. 12 oder 14.5.") from exc
        if crf_value < 0 or crf_value > 51:
            raise RuntimeError("CRF sollte zwischen 0 und 51 liegen. Für hohe Qualität meist 8–16.")
        return EncoderSettings(
            encoder_engine=self.encoder_engine_var.get(),
            video_codec=self.codec_var.get(),
            preset=self.preset_var.get(),
            crf=str(self.crf_var.get()).replace(",", "."),
            tune_grain=bool(self.tune_grain_var.get()),
            pixel_format_mode=self.pixel_format_mode_var.get(),
            output_size_mode=self.output_size_mode_var.get(),
            custom_width=self.custom_width_var.get(),
            custom_height=self.custom_height_var.get(),
            scale_flags=self.scale_flags_var.get(),
            fps_mode=self.fps_mode_var.get(),
            copy_metadata=bool(self.copy_metadata_var.get()),
            copy_chapters=bool(self.copy_chapters_var.get()),
            copy_attachments=bool(self.copy_attachments_var.get()),
            x265_extra_params=self.x265_extra_params_var.get(),
            ffmpeg_extra_args=self.ffmpeg_extra_args_var.get(),
        )

    def on_render_limited_changed(self):
        enabled = bool(self.render_limited_var.get())
        state = "normal" if enabled else "disabled"
        controls = getattr(self, "render_range_controls", None)
        if controls is not None:
            self._set_children_state(controls, state)
        if not enabled:
            self.render_start_var.set("")
            self.render_end_var.set("")

    def copy_preview_range_to_render(self):
        self.render_limited_var.set(True)
        self.on_render_limited_changed()
        self.render_mode_var.set(self.preview_mode_var.get())
        self._render_last_mode = self.render_mode_var.get()
        self.render_start_var.set(self.preview_start_var.get())
        self.render_end_var.set(self.preview_end_var.get())
        self.status_var.set("Vorschau-Bereich in Final-Render übernommen.")

    def _paths(self):
        return Path(self.source_var.get()), Path(self.csv_var.get()), Path(self.preview_var.get()), Path(self.output_var.get())

    def _validate_common(self):
        if IMPORT_ERROR is not None:
            raise RuntimeError(f"OpenCV/NumPy fehlt: {IMPORT_ERROR}")
        source, csv_path, preview, output = self._paths()
        if not source.is_file():
            raise RuntimeError("Bitte eine gültige Quelldatei auswählen.")
        return source, csv_path, preview, output

    def pick_video(self):
        path = filedialog.askopenfilename(filetypes=[("Videos", "*.mp4 *.mkv *.mov *.avi *.m4v *.ts"), ("Alle Dateien", "*.*")])
        if path:
            self.source_var.set(path)
            self._autofill_outputs(Path(path))
            self.load_video_info()
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

    def update_precrop_preview(self):
        self._update_precrop_info()
        # Wichtig: Hier NICHT _preview_percent_changed() aufrufen.
        # Diese Funktion würde immer wieder auf Prozent-Auswahl zurückschalten.
        try:
            percent = int(round(float(self.precrop_preview_percent_var.get())))
        except Exception:
            percent = 25
        percent = max(0, min(100, percent))
        self.precrop_preview_percent_var.set(percent)
        self.precrop_preview_percent_text_var.set(f"{percent}%")
        if Image is None or ImageTk is None or cv2 is None:
            self.canvas.delete("all")
            self.canvas.create_text(280, 180, text="Bildvorschau benötigt Pillow.\nDie Render-Funktion arbeitet trotzdem.", fill="white")
            return
        source = Path(self.source_var.get())
        if not source.is_file():
            self.canvas.delete("all")
            self.canvas.create_text(280, 180, text="Keine Quelle geladen", fill="white")
            self.precrop_preview_frame_info_var.set("Angezeigtes Frame: -")
            return
        try:
            cap = cv2.VideoCapture(str(source))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if total <= 0 and self.video_info and self.video_info.frames > 0:
                total = self.video_info.frames
            percent = max(0, min(100, int(self.precrop_preview_percent_var.get())))
            mode = self.precrop_preview_mode_var.get()
            used_label = f"{percent}%"
            target_zero = 0
            if mode == "frame":
                raw_frame = (self.precrop_preview_custom_frame_var.get() or "").strip()
                if not raw_frame:
                    raise RuntimeError("Bitte eine Frame-Nummer eingeben oder wieder Prozent-Auswahl nutzen.")
                try:
                    requested_frame = int(raw_frame)
                except ValueError as exc:
                    raise RuntimeError("Die Frame-Nummer muss eine ganze Zahl sein.") from exc
                if requested_frame < 1:
                    requested_frame = 1
                if total > 0:
                    requested_frame = min(requested_frame, total)
                self.precrop_preview_custom_frame_var.set(str(requested_frame))
                target_zero = requested_frame - 1
                used_label = f"Frame {requested_frame}"
            else:
                if total > 1:
                    target_zero = int(round((percent / 100) * (total - 1)))
            # Beide Eingabemöglichkeiten synchron halten: Prozent-Regler und Frame-Feld.
            self._sync_preview_controls_to_frame(target_zero + 1, total)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_zero)
            ok, frame = cap.read()
            if not ok and target_zero != 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
                target_zero = 0
            cap.release()
            if not ok:
                raise RuntimeError("Vorschau-Frame konnte nicht gelesen werden.")

            # Wichtig: Hier wird zuerst nur der eingestellte Vorschnitt angewendet.
            # Die Anzeige bezieht sich also auf den Ergebnisbereich/Basisbereich.
            frame = apply_precrop_to_frame(frame, self._get_precrop())
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            cw = max(self.canvas.winfo_width(), 560)
            chh = max(self.canvas.winfo_height(), 360)
            img.thumbnail((cw - 24, chh - 24))
            self.preview_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            x = (cw - img.width) // 2
            y = (chh - img.height) // 2
            self.canvas.create_image(x, y, anchor="nw", image=self.preview_photo)

            basis_w, basis_h = frame.shape[1], frame.shape[0]
            box_h = crop_height(basis_w)

            # CSV-Position für genau diesen Frame verwenden.
            # Wenn keine CSV vorhanden ist oder der Frame außerhalb der CSV liegt,
            # wird nur für die Anzeige auf "center" zurückgefallen.
            frame_no = target_zero + 1
            self._sync_preview_controls_to_frame(frame_no, total)
            csv_pos = "center"
            csv_note = "CSV: center (Fallback)"
            csv_path = Path(self.csv_var.get())
            if csv_path.is_file():
                try:
                    states = read_csv(csv_path)
                    if 1 <= frame_no <= len(states):
                        csv_pos = INDEX_TO_POSITION[int(states[frame_no - 1])]
                        csv_note = f"CSV-Position: {csv_pos}"
                    else:
                        csv_note = f"CSV: Frame {frame_no} liegt außerhalb der CSV ({len(states)} Frames)"
                except Exception as csv_exc:
                    csv_note = f"CSV konnte nicht gelesen werden: {csv_exc}"

            box_y = crop_offsets(basis_w, basis_h)[csv_pos]
            scale_x = img.width / basis_w
            scale_y = img.height / basis_h
            self.canvas.create_rectangle(
                x, y + box_y * scale_y,
                x + img.width, y + (box_y + box_h) * scale_y,
                outline="blue", width=3
            )
            # Kleiner Hinweis direkt im Bild, damit man sofort sieht,
            # ob up / center / down aus der CSV angekommen ist.
            self.canvas.create_text(
                x + 12, y + 12, anchor="nw",
                text=csv_note,
                fill="white",
                font=("Segoe UI", 11, "bold")
            )
            total_text = total if total > 0 else "?"
            self.precrop_preview_frame_info_var.set(
                f"Angezeigtes Frame: {used_label} (Frame {frame_no} / {total_text}) | Ergebnisbereich: {basis_w}x{basis_h} | {csv_note}"
            )
        except Exception as exc:
            self.canvas.delete("all")
            self.canvas.create_text(280, 180, text=str(exc), fill="white", width=520)
            self.precrop_preview_frame_info_var.set("Angezeigtes Frame: Fehler")

    def _format_time_seconds(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        sec = seconds - hours * 3600 - minutes * 60
        if abs(sec - round(sec)) < 0.0005:
            return f"{hours:02d}:{minutes:02d}:{int(round(sec)):02d}"
        return f"{hours:02d}:{minutes:02d}:{sec:06.3f}"

    def _convert_one_range_value(self, value: str, old_mode: str, new_mode: str) -> str:
        value = (value or "").strip()
        if not value or old_mode == new_mode:
            return value
        fps = self.video_info.fps if self.video_info else 0
        if fps <= 0:
            raise RuntimeError("FPS der Quelle ist unbekannt. Umrechnung zwischen Frames und Zeit ist nicht möglich.")
        if old_mode == "frames" and new_mode == "time":
            frame = int(value)
            return self._format_time_seconds((max(frame, 1) - 1) / fps)
        if old_mode == "time" and new_mode == "frames":
            seconds = self._parse_time_seconds(value)
            return str(int(round(seconds * fps)) + 1)
        return value

    def _convert_range_controls(self, start_var, end_var, old_mode: str, new_mode: str):
        try:
            start_var.set(self._convert_one_range_value(start_var.get(), old_mode, new_mode))
            end_var.set(self._convert_one_range_value(end_var.get(), old_mode, new_mode))
        except Exception as exc:
            messagebox.showerror("Umrechnung nicht möglich", str(exc))

    def on_preview_range_mode_changed(self):
        new_mode = self.preview_mode_var.get()
        old_mode = getattr(self, "_preview_last_mode", new_mode)
        self._convert_range_controls(self.preview_start_var, self.preview_end_var, old_mode, new_mode)
        self._preview_last_mode = new_mode

    def on_render_range_mode_changed(self):
        new_mode = self.render_mode_var.get()
        old_mode = getattr(self, "_render_last_mode", new_mode)
        self._convert_range_controls(self.render_start_var, self.render_end_var, old_mode, new_mode)
        self._render_last_mode = new_mode

    def jump_preview_to_range_value(self, value_var, mode_var):
        try:
            frame_no = self._parse_range_value(value_var.get(), mode_var.get())
            if frame_no is None:
                raise RuntimeError("Das Feld ist leer.")
            self.precrop_preview_mode_var.set("frame")
            self._sync_preview_controls_to_frame(frame_no)
            self.update_precrop_preview()
        except Exception as exc:
            messagebox.showerror("Springen nicht möglich", str(exc))

    def _update_project_state(self):
        source_ok = Path(self.source_var.get()).is_file()
        csv_ok = Path(self.csv_var.get()).is_file()
        self.project_status_var.set(f"Quelle: {'geladen' if source_ok else 'fehlt'} | CSV: {'geladen' if csv_ok else 'fehlt'}")
        self.nb.tab(self.tab_precrop, state="normal" if source_ok else "disabled")
        state_after_csv = "normal" if (source_ok and csv_ok) else "disabled"
        self.nb.tab(self.tab_preview, state=state_after_csv)
        self.nb.tab(self.tab_render, state=state_after_csv)

    def _parse_range_value(self, value: str, mode: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        fps = self.video_info.fps if self.video_info else 0
        if mode == "frames":
            return int(value)
        seconds = self._parse_time_seconds(value)
        if fps <= 0:
            raise RuntimeError("FPS der Quelle ist unbekannt. Zeitangaben können nicht in Frames umgerechnet werden.")
        return int(round(seconds * fps)) + 1

    def _parse_time_seconds(self, value: str) -> float:
        value = value.strip().replace(",", ".")
        if ":" not in value:
            return float(value)
        parts = [float(p) for p in value.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        raise RuntimeError(f"Ungültige Zeitangabe: {value}")

    def _range_preview(self):
        return (self._parse_range_value(self.preview_start_var.get(), self.preview_mode_var.get()),
                self._parse_range_value(self.preview_end_var.get(), self.preview_mode_var.get()))

    def _range_render(self):
        if not self.render_limited_var.get():
            return None, None
        return (self._parse_range_value(self.render_start_var.get(), self.render_mode_var.get()),
                self._parse_range_value(self.render_end_var.get(), self.render_mode_var.get()))

    def _run_worker(self, title: str, func, task_name: str = ""):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Läuft bereits", "Es läuft bereits ein Vorgang.")
            return
        self.cancel_requested = False
        self.pause_requested = False
        self._current_task = task_name
        self._worker_start_time = time.time()
        self.timing_info_var.set(self._t("Vergangen") + ": 00:00:00 | " + self._t("Rest") + ": " + self._t("wird berechnet") + " | " + self._t("Fertig ca.") + ": -")
        self.pause_button.config(text=self._t("Pause"), state="normal")
        self.progress["value"] = 0
        self.progress_percent_var.set("0 %")
        self.status_var.set(title)
        self._log("\n" + title)
        self.worker = threading.Thread(target=lambda: self._worker_wrapper(func), daemon=True)
        self.worker.start()

    def _worker_wrapper(self, func):
        try:
            func()
            self.queue.put(("done", "Fertig."))
        except Cancelled:
            self.queue.put(("error", "Abgebrochen."))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def _format_duration(self, seconds: float) -> str:
        seconds = max(0, int(seconds or 0))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        sec = seconds % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _update_timing_info(self, current: int, total: int):
        if not self._worker_start_time:
            return
        elapsed = time.time() - self._worker_start_time
        if total > 0 and current > 0:
            remaining = max(0.0, elapsed * (total - current) / current)
            eta = datetime.now() + timedelta(seconds=remaining)
            eta_text = eta.strftime("%Y-%m-%d %H:%M:%S")
            remaining_text = self._format_duration(remaining)
        else:
            eta_text = "-"
            remaining_text = self._t("wird berechnet")
        self.timing_info_var.set(
            f"{self._t('Vergangen')}: {self._format_duration(elapsed)} | "
            f"{self._t('Rest')}: {remaining_text} | "
            f"{self._t('Fertig ca.')}: {eta_text}"
        )

    def _progress_callback(self, current: int, total: int, text: str):
        percent = 0 if total <= 0 else max(0, min(100, current / total * 100))
        self.queue.put(("progress", percent, text, current, total))

    def _cancelled(self):
        while self.pause_requested and not self.cancel_requested:
            try:
                self.queue.put(("paused", "Pausiert ..."))
            except Exception:
                pass
            import time
            time.sleep(0.15)
        return self.cancel_requested

    def toggle_pause(self):
        if not (self.worker and self.worker.is_alive()):
            return
        self.pause_requested = not self.pause_requested
        if self.pause_requested:
            self.pause_button.config(text=self._t("Fortsetzen"))
            self.status_var.set("Pausiert ...")
            self._log("Pausiert.")
        else:
            self.pause_button.config(text=self._t("Pause"))
            self.status_var.set("Wird fortgesetzt ...")
            self._log("Fortgesetzt.")

    def _poll_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                if item[0] == "progress":
                    _, percent, text, current, total = item
                    self.progress["value"] = percent
                    self.progress_percent_var.set(f"{percent:5.1f} %")
                    self._update_timing_info(current, total)
                    if not self.pause_requested:
                        self.status_var.set(text)
                elif item[0] == "paused":
                    if self.pause_requested:
                        self.status_var.set(item[1])
                elif item[0] == "done":
                    self.progress["value"] = 100
                    self.progress_percent_var.set("100 %")
                    self.pause_requested = False
                    self.pause_button.config(text=self._t("Pause"), state="disabled")
                    self.status_var.set(item[1])
                    self._log(item[1])
                    if self._worker_start_time:
                        self._update_timing_info(1, 1)
                    should_shutdown = self._current_task == "render" and bool(self.shutdown_after_render_var.get())
                    self._current_task = None
                    self._worker_start_time = None
                    self._update_project_state()
                    if should_shutdown:
                        self._shutdown_computer()
                elif item[0] == "error":
                    self.pause_requested = False
                    self.pause_button.config(text=self._t("Pause"), state="disabled")
                    self.status_var.set(item[1])
                    self._log(item[1])
                    if item[1] != "Abgebrochen.":
                        messagebox.showerror("Fehler", item[1])
                    self._current_task = None
                    self._worker_start_time = None
                    self._update_project_state()
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _shutdown_computer(self):
        try:
            system = platform.system().lower()
            if "windows" in system:
                subprocess.Popen(["shutdown", "/s", "/t", "60"], shell=False)
            elif "darwin" in system:
                subprocess.Popen(["osascript", "-e", 'tell application "System Events" to shut down'], shell=False)
            else:
                subprocess.Popen(["shutdown", "-h", "+1"], shell=False)
            msg = self._t("Der PC wird in ca. 60 Sekunden heruntergefahren.")
            self.status_var.set(msg)
            self._log(msg)
            messagebox.showinfo(self._t("Herunterfahren"), msg)
        except Exception as exc:
            messagebox.showerror(self._t("Automatisches Herunterfahren konnte nicht gestartet werden"), str(exc))

    def _log(self, text: str):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def cancel(self):
        self.cancel_requested = True
        self.status_var.set("Abbruch angefordert ...")

    def run_create_csv(self):
        def job():
            source, csv_path, _, _ = self._validate_common()
            create_center_csv(source, csv_path, self._progress_callback, self._cancelled)
        self._run_worker("Center-CSV wird erstellt ...", job)

    def run_preview(self):
        def job():
            source, csv_path, preview, _ = self._validate_common()
            if not csv_path.is_file():
                raise RuntimeError("CSV-Datei fehlt. Bitte zuerst Center-CSV erstellen oder vorhandene CSV öffnen.")
            if not str(preview):
                raise RuntimeError("Bitte einen Speicherort für die Vorschau wählen.")
            start, end = self._range_preview()
            render_preview(source, csv_path, preview, start, end, self._get_precrop(), self._progress_callback, self._cancelled)
        self._run_worker("Vorschau wird gestartet ...", job)

    def run_render(self):
        def job():
            source, csv_path, _, output = self._validate_common()
            if not csv_path.is_file():
                raise RuntimeError("CSV-Datei fehlt. Bitte zuerst Center-CSV erstellen oder vorhandene CSV öffnen.")
            if not str(output):
                raise RuntimeError("Bitte einen Speicherort für das finale Video wählen.")
            start, end = self._range_render()
            settings = self._collect_encoder_settings()
            render_final(source, csv_path, output, settings, self._get_precrop(), start, end, self._progress_callback, self._cancelled)
        self._run_worker("Finaler Render wird gestartet ...", job, task_name="render")


if __name__ == "__main__":
    App().mainloop()
