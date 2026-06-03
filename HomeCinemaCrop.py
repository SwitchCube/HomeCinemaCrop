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

from tabs.file_tab import (
    _build_file_tab, pick_video, pick_csv_open, pick_csv_save, pick_preview_save,
    pick_output_save, _autofill_outputs, load_video_info, run_create_csv,
)
from tabs.precrop_tab import (
    _build_precrop_tab, _set_children_state, on_crop_needed_changed, on_precrop_mode_changed,
    clear_precrop, _get_precrop, _update_precrop_info, suggest_4x3_precrop,
)
from tabs.preview_tab import (
    _get_total_frames_for_preview, _sync_preview_controls_to_frame, _preview_percent_changed,
    _preview_frame_entry_changed, jump_precrop_preview_frame, _build_preview_tab,
    update_precrop_preview, _format_time_seconds, _convert_one_range_value,
    _convert_range_controls, on_preview_range_mode_changed, jump_preview_to_range_value,
    _parse_range_value, _parse_time_seconds, _range_preview, run_preview,
)
from tabs.render_tab import (
    _build_render_tab, on_quality_preset_changed, on_size_options_changed, _collect_encoder_settings,
    on_render_limited_changed, copy_preview_range_to_render, on_render_range_mode_changed,
    _range_render, run_render,
)


TRANSLATIONS_EN = {'Sprache': 'Language', 'Noch keine Quelle geladen.': 'No source loaded yet.', 'Datei': 'File', 'Vorschnitt': 'Pre-crop', 'Vorschau': 'Preview', 'Final-Render': 'Final render', 'Quelldatei (meist MakeMKV 16:9)': 'Source file (usually MakeMKV 16:9)', 'Durchsuchen': 'Browse', 'CSV-Datei': 'CSV file', 'Öffnen': 'Open', 'Speichern unter': 'Save as', 'CSV erstellen': 'Create CSV', 'Vorschau MP4': 'Preview MP4', 'Finales Video': 'Final video', 'Alle Reiter werden aktiv, sobald eine Quelle und eine vorhandene CSV geladen sind. Alternativ kannst du die CSV hier neu erstellen.': 'All tabs become active once a source and an existing CSV are loaded. Alternatively, you can create the CSV here.', 'Status / Protokoll': 'Status / log', 'Bereit.': 'Ready.', 'Pause': 'Pause', 'Abbrechen': 'Cancel', 'Vorschnitt einstellen': 'Set pre-crop', 'Vorschnitt nötig': 'Pre-crop needed', 'Größeninformationen': 'Size information', 'Originalgröße: -': 'Original size: -', 'Aktuelle Größe: -': 'Current size: -', 'Beschnitt': 'Crop', 'Modus': 'Mode', 'Automatisch': 'Automatic', 'Manuell': 'Manual', 'Keine (0)': 'None (0)', 'Automatisch erkennen': 'Auto detect', 'Vorschnitt (Pixel)': 'Pre-crop (pixels)', 'Oben': 'Top', 'Links': 'Left', 'Rechts': 'Right', 'Unten': 'Bottom', 'Ergebnisbereich': 'Result area', 'Bildvorschau / Frame-Auswahl': 'Image preview / frame selection', 'Vorschau (nur Ergebnisbereich)': 'Preview (result area only)', 'Vorschau-Frame für Anzeige:': 'Preview frame for display:', 'Position in %': 'Position in %', 'Bestimmter Frame': 'Specific frame', 'Bildvorschau aktualisieren': 'Refresh image preview', 'Vorschau-MP4 erstellen': 'Create preview MP4', 'Bereich für Vorschau-Video': 'Range for preview video', 'Frames': 'Frames', 'Sekunden / Zeit': 'Seconds / time', 'Start': 'Start', 'Ende': 'End', 'Zum Start springen': 'Jump to start', 'Zum Ende springen': 'Jump to end', 'Vorschau erstellen': 'Create preview', 'Final-Render-Bereich': 'Final render range', 'Welcher Teil soll gerendert werden?': 'Which part should be rendered?', 'Nur bestimmten Bereich rendern': 'Render only a specific range', 'Wie Vorschau-Bereich': 'Use preview range', 'Qualität / Codec': 'Quality / codec', 'Qualitäts-Vorlage': 'Quality preset', 'Codec': 'Codec', 'Preset': 'Preset', 'CRF / CQ Qualität': 'CRF / CQ quality', 'Film-/Grain-schonend encodieren (-tune grain, weniger Glättung)': 'Encode film/grain-friendly (-tune grain, less smoothing)', 'Zielauflösung / Skalierung': 'Target resolution / scaling', 'Ausgabegröße': 'Output size', 'Breite': 'Width', 'Höhe': 'Height', 'Scaler': 'Scaler', 'Erweiterte Encoder-Einstellungen': 'Advanced encoder settings', 'Pixelformat': 'Pixel format', 'Framerate': 'Frame rate', 'Metadaten übernehmen (-map_metadata 0)': 'Copy metadata (-map_metadata 0)', 'Kapitel übernehmen (-map_chapters 0)': 'Copy chapters (-map_chapters 0)', 'Anhänge/Fonts übernehmen (-c:t copy)': 'Copy attachments/fonts (-c:t copy)', 'x265 Zusatzparameter': 'x265 extra parameters', 'FFmpeg Zusatzargumente': 'FFmpeg extra arguments', 'Empfehlung für deine UHD-HDR-Quelle': 'Recommendation for your UHD HDR source', 'Final-Render starten': 'Start final render', 'Encoder': 'Encoder', 'Fehlende Python-Bibliothek': 'Missing Python library', 'OpenCV/NumPy konnte nicht geladen werden': 'OpenCV/NumPy could not be loaded', 'Normal hochwertig (CRF 16)': 'Normal high quality (CRF 16)', 'Quellnah / sehr hoch (CRF 12)': 'Source-like / very high (CRF 12)', 'Nahezu verlustfrei (CRF 10)': 'Almost lossless (CRF 10)', 'Extrem groß / Test (CRF 8)': 'Extremely large / test (CRF 8)', 'Benutzerdefiniert': 'Custom', 'Nativ nach Crop': 'Native after crop', 'UHD 3840x2160 hochskalieren': 'Upscale to UHD 3840x2160', 'Quellgröße hochskalieren': 'Upscale to source size', 'Quelle CFR erzwingen': 'Force source CFR', 'FPS Passthrough': 'FPS passthrough', 'Nicht anfassen': 'Do not touch', 'Auto / Quelle': 'Auto / source', 'Quelle exakt': 'Exact source', '10 Bit 4:2:0 (HDR/UHD)': '10-bit 4:2:0 (HDR/UHD)', '8 Bit 4:2:0 (SDR)': '8-bit 4:2:0 (SDR)', 'Für maximale Quellnähe: Nativ nach Crop, libx265, veryslow/slower, CRF 10–12, 10 Bit Auto, Quelle CFR erzwingen.': 'For maximum source fidelity: Native after crop, libx265, veryslow/slower, CRF 10–12, 10-bit auto, force source CFR.', 'Für UHD-kompatible Ausgabe: UHD 3840x2160 hochskalieren mit lanczos oder spline.': 'For UHD-compatible output: upscale to UHD 3840x2160 with lanczos or spline.', 'Audio, Untertitel, Kapitel, Metadaten und Anhänge werden auf Wunsch kopiert.': 'Audio, subtitles, chapters, metadata and attachments can be copied.', 'Kleiner CRF = bessere Qualität und größere Datei. Für UHD/HDR: libx265, slower/veryslow, CRF 10–12.': 'Lower CRF/CQ = better quality and larger file. For UHD/HDR: libx265, slower/veryslow, CRF/CQ 10–12.', 'Zeitangaben: z.B. 125, 00:02:05 oder 00:02:05.500': 'Time values: e.g. 125, 00:02:05 or 00:02:05.500', 'Standard: 25%. Alternativ kannst du direkt eine Frame-Nummer eingeben.': 'Default: 25%. Alternatively, enter a frame number directly.', 'Die Vorschau zeigt den eingestellten Ergebnisbereich. Der blaue Rahmen kommt aus der CSV-Position up/center/down.': 'The preview shows the configured result area. The blue frame comes from the CSV position up/center/down.', 'Ohne Haken wird der komplette Film gerendert. Zeitangaben: 125, 00:02:05 oder 00:02:05.500': 'Without the checkbox, the full movie is rendered. Time values: 125, 00:02:05 or 00:02:05.500', 'Nach Final-Render PC automatisch herunterfahren': 'Automatically shut down PC after final render', 'Zeit: noch nicht gestartet': 'Time: not started yet', 'Vergangen': 'Elapsed', 'Rest': 'Remaining', 'Fertig ca.': 'Estimated finish', 'wird berechnet': 'calculating', 'Herunterfahren': 'Shutdown', 'Der PC wird in ca. 60 Sekunden heruntergefahren.': 'The PC will shut down in about 60 seconds.', 'Automatisches Herunterfahren konnte nicht gestartet werden': 'Automatic shutdown could not be started', 'Fortsetzen': 'Resume'}

class App(tk.Tk):

    # Tab-Code ist ausgelagert in einzelne Dateien unter tabs/
    _build_file_tab = _build_file_tab
    pick_video = pick_video
    pick_csv_open = pick_csv_open
    pick_csv_save = pick_csv_save
    pick_preview_save = pick_preview_save
    pick_output_save = pick_output_save
    _autofill_outputs = _autofill_outputs
    load_video_info = load_video_info
    run_create_csv = run_create_csv

    _build_precrop_tab = _build_precrop_tab
    _set_children_state = _set_children_state
    on_crop_needed_changed = on_crop_needed_changed
    on_precrop_mode_changed = on_precrop_mode_changed
    clear_precrop = clear_precrop
    _get_precrop = _get_precrop
    _update_precrop_info = _update_precrop_info
    suggest_4x3_precrop = suggest_4x3_precrop

    _get_total_frames_for_preview = _get_total_frames_for_preview
    _sync_preview_controls_to_frame = _sync_preview_controls_to_frame
    _preview_percent_changed = _preview_percent_changed
    _preview_frame_entry_changed = _preview_frame_entry_changed
    jump_precrop_preview_frame = jump_precrop_preview_frame
    _build_preview_tab = _build_preview_tab
    update_precrop_preview = update_precrop_preview
    _format_time_seconds = _format_time_seconds
    _convert_one_range_value = _convert_one_range_value
    _convert_range_controls = _convert_range_controls
    on_preview_range_mode_changed = on_preview_range_mode_changed
    jump_preview_to_range_value = jump_preview_to_range_value
    _parse_range_value = _parse_range_value
    _parse_time_seconds = _parse_time_seconds
    _range_preview = _range_preview
    run_preview = run_preview

    _build_render_tab = _build_render_tab
    on_quality_preset_changed = on_quality_preset_changed
    on_size_options_changed = on_size_options_changed
    _collect_encoder_settings = _collect_encoder_settings
    on_render_limited_changed = on_render_limited_changed
    copy_preview_range_to_render = copy_preview_range_to_render
    on_render_range_mode_changed = on_render_range_mode_changed
    _range_render = _range_render
    run_render = run_render

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
        self.video_encoder_var = tk.StringVar(value="H.265 10-bit (x265)")
        self.preset_var = tk.StringVar(value="slower")
        self.crf_var = tk.StringVar(value="12")
        self.quality_preset_var = tk.StringVar(value="Quellnah / sehr hoch (CRF 12)")
        self.tune_grain_var = tk.BooleanVar(value=True)
        self.pixel_format_mode_var = tk.StringVar(value="Auto / Quelle")

        # Neue HandBrake-ähnliche Struktur: Bildgröße = Auflösungslimit + Skalierung
        self.resolution_limit_var = tk.StringVar(value="Keine")
        self.limit_width_var = tk.StringVar(value="3840")
        self.limit_height_var = tk.StringVar(value="2160")
        self.scaler_var = tk.StringVar(value="Keine")
        self.scale_to_var = tk.StringVar(value="Keine")
        self.scale_width_var = tk.StringVar(value="3840")
        self.scale_height_var = tk.StringVar(value="2160")

        # Bildfrequenz wie HandBrake
        self.fps_choice_var = tk.StringVar(value="Same as source")
        self.fps_type_var = tk.StringVar(value="Konstante Bildfrequenz")

        # Filter wie HandBrake
        self.detelecine_var = tk.StringVar(value="Off")
        self.interlace_detection_var = tk.StringVar(value="Default")
        self.deinterlace_var = tk.StringVar(value="Off")
        self.deinterlace_preset_var = tk.StringVar(value="Default")
        self.denoise_var = tk.StringVar(value="Off")
        self.chroma_smooth_var = tk.StringVar(value="Off")
        self.sharpen_var = tk.StringVar(value="Off")
        self.deblock_var = tk.StringVar(value="Off")
        self.colorspace_filter_var = tk.StringVar(value="Off")
        self.grayscale_var = tk.BooleanVar(value=False)

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




















    def _paths(self):
        return Path(self.source_var.get()), Path(self.csv_var.get()), Path(self.preview_var.get()), Path(self.output_var.get())

    def _validate_common(self):
        if IMPORT_ERROR is not None:
            raise RuntimeError(f"OpenCV/NumPy fehlt: {IMPORT_ERROR}")
        source, csv_path, preview, output = self._paths()
        if not source.is_file():
            raise RuntimeError("Bitte eine gültige Quelldatei auswählen.")
        return source, csv_path, preview, output


















    def _update_project_state(self):
        source_ok = Path(self.source_var.get()).is_file()
        csv_ok = Path(self.csv_var.get()).is_file()
        self.project_status_var.set(f"Quelle: {'geladen' if source_ok else 'fehlt'} | CSV: {'geladen' if csv_ok else 'fehlt'}")
        self.nb.tab(self.tab_precrop, state="normal" if source_ok else "disabled")
        state_after_csv = "normal" if (source_ok and csv_ok) else "disabled"
        self.nb.tab(self.tab_preview, state=state_after_csv)
        self.nb.tab(self.tab_render, state=state_after_csv)





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





if __name__ == "__main__":
    App().mainloop()
