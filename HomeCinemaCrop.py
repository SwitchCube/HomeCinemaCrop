#!/usr/bin/env python3
"""
HomeCinemaCrop: IMAX (4:3) → 16:9 GUI v31 Kompaktere Oberfläche

Workflow:
1. Datei wählen
2. optionaler manueller Vorschnitt wie in HandBrake (z.B. MakeMKV-16:9 -> echtes 4:3/IMAX-Bild)
3. CSV mit up/center/down laden oder erzeugen
4. Vorschau oder Final-Render ausgeben

Wichtig ab v30:
- Die Tab-Oberflächen werden wirklich aus dem Unterordner tabs/ geladen.
- Diese Datei enthält keine alten eingebauten Tab-Layouts mehr.
- FFmpeg-Logs werden neben HomeCinemaCrop_core.py gespeichert:
  last_ffmpeg_command.txt und last_ffmpeg_error.log
- Python-/GUI-Fehler werden als last_app_error.log gespeichert.
"""
from __future__ import annotations

import queue
import threading
import time
import platform
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from HomeCinemaCrop_core import *
from tabs import file_tab, precrop_tab, preview_tab, render_tab

APP_VERSION = "v31"

TRANSLATIONS_EN = {
    'Sprache': 'Language',
    'Noch keine Quelle geladen.': 'No source loaded yet.',
    'Datei': 'File',
    'Vorschnitt': 'Pre-crop',
    'Vorschau': 'Preview',
    'Final-Render': 'Final render',
    'Status / Protokoll': 'Status / log',
    'Bereit.': 'Ready.',
    'Pause': 'Pause',
    'Abbrechen': 'Cancel',
    'Nach Final-Render PC automatisch herunterfahren': 'Automatically shut down PC after final render',
    'Vergangen': 'Elapsed',
    'Rest': 'Remaining',
    'Fertig ca.': 'Estimated finish',
    'wird berechnet': 'calculating',
    'Fortsetzen': 'Resume',
    'Fehlende Python-Bibliothek': 'Missing Python library',
    'OpenCV/NumPy konnte nicht geladen werden': 'OpenCV/NumPy could not be loaded',
    'Herunterfahren': 'Shutdown',
    'Der PC wird in ca. 60 Sekunden heruntergefahren.': 'The PC will shut down in about 60 seconds.',
    'Automatisches Herunterfahren konnte nicht gestartet werden': 'Automatic shutdown could not be started',
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        try:
            self.tk.call("tk", "scaling", 1.0)
        except Exception:
            pass

        self.title(self._t(f"HomeCinemaCrop: IMAX (4:3) → 16:9 {APP_VERSION}"))
        # Kompakter Startwert, damit Status/Protokoll nicht hinter der Windows-Taskleiste verschwindet.
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        start_w = min(1550, max(1100, screen_w - 90))
        start_h = min(840, max(720, screen_h - 180))
        self.geometry(f"{start_w}x{start_h}")
        self.minsize(1000, 700)

        self.cancel_requested = False
        self.pause_requested = False
        self.worker: Optional[threading.Thread] = None
        self.queue: queue.Queue = queue.Queue()
        self.video_info: Optional[VideoInfo] = None
        self.preview_photo = None
        self._worker_start_time = None
        self._current_task = None

        self.language_var = tk.StringVar(value="Deutsch")
        self.shutdown_after_render_var = tk.BooleanVar(value=False)
        self.timing_info_var = tk.StringVar(value="Zeit: noch nicht gestartet")

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

        self.resolution_limit_var = tk.StringVar(value="Keine")
        self.limit_width_var = tk.StringVar(value="3840")
        self.limit_height_var = tk.StringVar(value="2160")
        self.scaler_var = tk.StringVar(value="Keine")
        self.scale_to_var = tk.StringVar(value="Keine")
        self.scale_width_var = tk.StringVar(value="3840")
        self.scale_height_var = tk.StringVar(value="2160")

        self.fps_choice_var = tk.StringVar(value="Same as source")
        self.fps_type_var = tk.StringVar(value="Konstante Bildfrequenz")

        self.detelecine_var = tk.StringVar(value="Off")
        self.detelecine_custom_var = tk.StringVar(value="")
        self.interlace_detection_var = tk.StringVar(value="Default")
        self.comb_detect_var = tk.StringVar(value="Off")
        self.comb_detect_custom_var = tk.StringVar(value="")
        self.deinterlace_var = tk.StringVar(value="Off")
        self.deinterlace_preset_var = tk.StringVar(value="Default")
        self.deinterlace_custom_var = tk.StringVar(value="")
        self.denoise_var = tk.StringVar(value="Off")
        self.denoise_preset_var = tk.StringVar(value="Medium")
        self.denoise_tune_var = tk.StringVar(value="None")
        self.denoise_custom_var = tk.StringVar(value="")
        self.chroma_smooth_var = tk.StringVar(value="Off")
        self.chroma_smooth_preset_var = tk.StringVar(value="Medium")
        self.chroma_smooth_tune_var = tk.StringVar(value="None")
        self.chroma_smooth_custom_var = tk.StringVar(value="")
        self.sharpen_var = tk.StringVar(value="Off")
        self.sharpen_preset_var = tk.StringVar(value="Medium")
        self.sharpen_tune_var = tk.StringVar(value="None")
        self.sharpen_custom_var = tk.StringVar(value="")
        self.deblock_var = tk.StringVar(value="Off")
        self.deblock_preset_var = tk.StringVar(value="Medium")
        self.deblock_tune_var = tk.StringVar(value="Medium")
        self.deblock_custom_var = tk.StringVar(value="")
        self.rotate_var = tk.StringVar(value="Off")
        self.rotate_custom_var = tk.StringVar(value="")
        self.pad_var = tk.StringVar(value="Off")
        self.pad_custom_var = tk.StringVar(value="")
        self.colorspace_filter_var = tk.StringVar(value="Off")
        self.colorspace_custom_var = tk.StringVar(value="")
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
            messagebox.showerror(
                self._t("Fehlende Python-Bibliothek"),
                f"{self._t('OpenCV/NumPy konnte nicht geladen werden')}:\n{IMPORT_ERROR}",
            )

    def _t(self, text: str) -> str:
        if getattr(self, "language_var", None) is None or self.language_var.get() == "Deutsch":
            return text
        return TRANSLATIONS_EN.get(text, text)

    def on_language_changed(self, _event=None):
        for child in self.winfo_children():
            child.destroy()
        self.title(self._t(f"HomeCinemaCrop: IMAX (4:3) → 16:9 {APP_VERSION}"))
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
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=10)
        style.configure("TButton", padding=6)
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TEntry", padding=4)

    def _build_ui(self):
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 4))
        ttk.Label(header, text=f"HomeCinemaCrop: IMAX (4:3) → 16:9 {APP_VERSION}", style="Title.TLabel").pack(side="left")
        self.project_status_var = tk.StringVar(value="Quelle: fehlt | CSV: fehlt")
        ttk.Label(header, textvariable=self.project_status_var, style="Subtitle.TLabel").pack(side="right", padx=(12, 0))
        lang_box = ttk.Frame(header)
        lang_box.pack(side="right", padx=(12, 0))
        ttk.Label(lang_box, text=self._t("Sprache")).pack(side="left", padx=(0, 6))
        language_combo = ttk.Combobox(lang_box, textvariable=self.language_var, values=["Deutsch", "English"], state="readonly", width=10)
        language_combo.pack(side="left")
        language_combo.bind("<<ComboboxSelected>>", self.on_language_changed)

        self.info_var = tk.StringVar(value=self._t("Noch keine Quelle geladen."))
        ttk.Label(root, textvariable=self.info_var, style="Subtitle.TLabel").pack(anchor="w", pady=(0, 4))

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, pady=(0, 2))
        self.tab_file = ttk.Frame(self.nb, padding=8)
        self.tab_precrop = ttk.Frame(self.nb, padding=8)
        self.tab_preview = ttk.Frame(self.nb, padding=8)
        self.tab_render = ttk.Frame(self.nb, padding=8)
        self.nb.add(self.tab_file, text=self._t("Datei"))
        self.nb.add(self.tab_precrop, text=self._t("Vorschnitt"))
        self.nb.add(self.tab_preview, text=self._t("Vorschau"))
        self.nb.add(self.tab_render, text=self._t("Final-Render"))
        self._build_file_tab()
        self._build_precrop_tab()
        self._build_preview_tab()
        self._build_render_tab()

        status = ttk.LabelFrame(root, text=self._t("Status / Protokoll"), padding=6)
        status.pack(fill="x", pady=(4, 0))
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
        progress_row.pack(fill="x", pady=(4, 4))
        self.progress_percent_var = tk.StringVar(value="0 %")
        ttk.Label(progress_row, textvariable=self.progress_percent_var, width=8).pack(side="left")
        self.progress = ttk.Progressbar(progress_row, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        self.log = tk.Text(status, height=2, wrap="word")
        self.log.pack(fill="x")

    def _update_project_state(self):
        source_ok = Path(self.source_var.get()).is_file()
        csv_ok = Path(self.csv_var.get()).is_file()
        self.project_status_var.set(f"Quelle: {'geladen' if source_ok else 'fehlt'} | CSV: {'geladen' if csv_ok else 'fehlt'}")
        self.nb.tab(self.tab_precrop, state="normal" if source_ok else "disabled")
        state_after_csv = "normal" if (source_ok and csv_ok) else "disabled"
        self.nb.tab(self.tab_preview, state=state_after_csv)
        self.nb.tab(self.tab_render, state=state_after_csv)

    def _paths(self):
        return Path(self.source_var.get()), Path(self.csv_var.get()), Path(self.preview_var.get()), Path(self.output_var.get())

    def _validate_common(self):
        if IMPORT_ERROR is not None:
            raise RuntimeError(f"OpenCV/NumPy fehlt: {IMPORT_ERROR}")
        source, csv_path, preview, output = self._paths()
        if not source.is_file():
            raise RuntimeError("Bitte eine gültige Quelldatei auswählen.")
        return source, csv_path, preview, output

    def _run_worker(self, title: str, func, task_name: str = ""):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Läuft bereits", "Es läuft bereits ein Vorgang.")
            return
        self.cancel_requested = False
        self.pause_requested = False
        self._current_task = task_name
        self._worker_start_time = time.time()
        self.timing_info_var.set(f"{self._t('Vergangen')}: 00:00:00 | {self._t('Rest')}: {self._t('wird berechnet')} | {self._t('Fertig ca.')}: -")
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
            self._write_app_error_log(exc)
            self.queue.put(("error", str(exc)))

    def _write_app_error_log(self, exc: BaseException):
        try:
            path = write_text_log("last_app_error.log", traceback.format_exc())
            self.queue.put(("log", f"Python-/GUI-Fehlerlog gespeichert: {path}"))
        except Exception:
            pass

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
            self.queue.put(("paused", "Pausiert ..."))
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
                elif item[0] == "log":
                    self._log(item[1])
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


# Nur explizit gewünschte Tab-Module installieren.
# Dadurch kann kein alter eingebauter Tab-Code mehr angezeigt werden.
for module in (file_tab, precrop_tab, preview_tab, render_tab):
    for name, value in module.__dict__.items():
        if callable(value) and not name.startswith("__"):
            setattr(App, name, value)


if __name__ == "__main__":
    App().mainloop()
