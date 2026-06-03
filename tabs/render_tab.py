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

def _build_render_tab(self):
    f = self.tab_render
    f.columnconfigure(0, weight=1)
    f.columnconfigure(1, weight=1)
    f.rowconfigure(0, weight=1)

    profiles = ["Keine", "4320p 8K Ultra HD", "2160p 4K Ultra HD", "1080p HD", "720p HD", "576p PAL SD", "480p NTSC SD", "Eigene"]
    encoders = [
        "H.264 (x264)",
        "H.264 10-bit (x264)",
        "H.264 (NVENC)",
        "H.265 (x265)",
        "H.265 10-bit (x265)",
        "H.265 12-bit (x265)",
        "H.265 (NVENC)",
        "H.265 10-bit (NVENC)",
    ]
    fps_values = ["Same as source", "5", "10", "12", "15", "20", "23.976", "24", "25", "29.97", "30", "48", "50", "59.94", "60", "72", "75", "90", "100", "120"]

    left = ttk.Frame(f)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    left.columnconfigure(0, weight=1)

    right = ttk.Frame(f)
    right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
    right.columnconfigure(0, weight=1)
    right.rowconfigure(0, weight=1)

    # 1. Final-Render-Bereich bleibt wie bisher.
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

    # 2. Bildgröße: Auflösungslimit + Skalierung.
    size_box = ttk.LabelFrame(left, text="Bildgröße", padding=12)
    size_box.grid(row=1, column=0, sticky="ew", pady=(0, 12))
    for c in range(6):
        size_box.columnconfigure(c, weight=1 if c in (1, 3, 5) else 0)

    ttk.Label(size_box, text="Auflösungslimit:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
    self.resolution_limit_combo = ttk.Combobox(size_box, textvariable=self.resolution_limit_var, values=profiles, state="readonly", width=20)
    self.resolution_limit_combo.grid(row=0, column=1, sticky="ew", pady=(0, 6))
    self.limit_width_entry = ttk.Entry(size_box, textvariable=self.limit_width_var, width=8)
    self.limit_width_entry.grid(row=0, column=2, sticky="ew", padx=(10, 4), pady=(0, 6))
    ttk.Label(size_box, text="x").grid(row=0, column=3, sticky="w", pady=(0, 6))
    self.limit_height_entry = ttk.Entry(size_box, textvariable=self.limit_height_var, width=8)
    self.limit_height_entry.grid(row=0, column=4, sticky="ew", padx=(4, 0), pady=(0, 6))

    ttk.Label(size_box, text="Skalierung:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
    self.scaler_combo = ttk.Combobox(size_box, textvariable=self.scaler_var, values=["Keine", "lanczos", "spline", "bicubic", "bilinear"], state="readonly", width=20)
    self.scaler_combo.grid(row=1, column=1, sticky="ew", pady=(6, 0))
    self.scale_to_combo = ttk.Combobox(size_box, textvariable=self.scale_to_var, values=profiles, state="readonly", width=20)
    self.scale_to_combo.grid(row=1, column=2, columnspan=2, sticky="ew", padx=(10, 4), pady=(6, 0))
    self.scale_width_entry = ttk.Entry(size_box, textvariable=self.scale_width_var, width=8)
    self.scale_width_entry.grid(row=1, column=4, sticky="ew", padx=(4, 4), pady=(6, 0))
    self.scale_height_entry = ttk.Entry(size_box, textvariable=self.scale_height_var, width=8)
    self.scale_height_entry.grid(row=1, column=5, sticky="ew", padx=(4, 0), pady=(6, 0))
    ttk.Label(size_box, text="Limit begrenzt nur die Maximalgröße. Skalierung rechnet gezielt auf das gewählte Zielprofil.", style="Subtitle.TLabel").grid(row=2, column=0, columnspan=6, sticky="w", pady=(10, 0))

    self.resolution_limit_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_size_options_changed())
    self.scaler_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_size_options_changed())
    self.scale_to_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_size_options_changed())

    # 3. Video.
    video_box = ttk.LabelFrame(left, text="Video", padding=12)
    video_box.grid(row=2, column=0, sticky="ew", pady=(0, 12))
    for c in range(4):
        video_box.columnconfigure(c, weight=1)
    ttk.Label(video_box, text="Videoencoder").grid(row=0, column=0, sticky="w")
    ttk.Combobox(video_box, textvariable=self.video_encoder_var, values=encoders, state="readonly").grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=(2, 8))
    ttk.Label(video_box, text="Preset").grid(row=0, column=2, sticky="w")
    ttk.Combobox(video_box, textvariable=self.preset_var, values=["ultrafast", "fast", "medium", "slow", "slower", "veryslow"], width=14).grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(2, 8))
    ttk.Label(video_box, text="CQ Qualität").grid(row=0, column=3, sticky="w")
    ttk.Entry(video_box, textvariable=self.crf_var, width=10).grid(row=1, column=3, sticky="ew", pady=(2, 8))

    ttk.Label(video_box, text="Bildfrequenz (BpS)").grid(row=2, column=0, sticky="w")
    ttk.Combobox(video_box, textvariable=self.fps_choice_var, values=fps_values, state="readonly").grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=(2, 8))
    ttk.Radiobutton(video_box, text="Konstante Bildfrequenz", variable=self.fps_type_var, value="Konstante Bildfrequenz").grid(row=3, column=1, sticky="w", padx=(0, 8))
    ttk.Radiobutton(video_box, text="Variable Bildfrequenz", variable=self.fps_type_var, value="Variable Bildfrequenz").grid(row=3, column=2, sticky="w", padx=(0, 8))
    ttk.Checkbutton(video_box, text="Film-/Grain-schonend encodieren", variable=self.tune_grain_var).grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))

    # 4. Filter rechts wie HandBrake.
    filter_box = ttk.LabelFrame(right, text="Filter", padding=12)
    filter_box.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
    filter_box.columnconfigure(1, weight=1)
    filter_box.columnconfigure(3, weight=1)
    def combo_row(row, label, var, values, col=0, width=18):
        ttk.Label(filter_box, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=(0, 8))
        cb = ttk.Combobox(filter_box, textvariable=var, values=values, state="readonly", width=width)
        cb.grid(row=row, column=col+1, sticky="ew", pady=(0, 8))
        return cb
    combo_row(0, "Detelecine:", self.detelecine_var, ["Off", "Default"])
    combo_row(1, "Interlace-Erkennung:", self.interlace_detection_var, ["Off", "Default", "Less Sensitive", "More Sensitive"])
    combo_row(2, "Deinterlace:", self.deinterlace_var, ["Off", "Decomb", "Yadif", "BWDIF"])
    combo_row(2, "Voreinstellung:", self.deinterlace_preset_var, ["Default", "Fast", "Bob", "EEDI2"], col=2)
    combo_row(3, "Entrauschen:", self.denoise_var, ["Off", "NLMeans", "HQDN3D"])
    combo_row(4, "Chroma-Glättung:", self.chroma_smooth_var, ["Off", "Weak", "Medium", "Strong"])
    combo_row(5, "Schärfen:", self.sharpen_var, ["Off", "Unsharp", "Lapsharp"])
    combo_row(6, "Deblock:", self.deblock_var, ["Off", "Weak", "Medium", "Strong"])
    combo_row(7, "Farbraum:", self.colorspace_filter_var, ["Off", "BT.709", "BT.2020"])
    ttk.Checkbutton(filter_box, text="Graustufen", variable=self.grayscale_var).grid(row=8, column=1, sticky="w", pady=(6, 0))
    ttk.Label(filter_box, text="Für 4K/HDR-Quellen am besten alles auf Off lassen, außer du möchtest bewusst filtern.", style="Subtitle.TLabel", wraplength=520).grid(row=9, column=0, columnspan=4, sticky="w", pady=(14, 0))

    # 5. Start: vorhandene Optionen behalten.
    start_box = ttk.LabelFrame(right, text="Start", padding=12)
    start_box.grid(row=1, column=0, sticky="ew")
    start_box.columnconfigure(1, weight=1)
    ttk.Checkbutton(start_box, text="Metadaten übernehmen (-map_metadata 0)", variable=self.copy_metadata_var).grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Checkbutton(start_box, text="Kapitel übernehmen (-map_chapters 0)", variable=self.copy_chapters_var).grid(row=1, column=0, columnspan=2, sticky="w")
    ttk.Checkbutton(start_box, text="Anhänge/Fonts übernehmen (-c:t copy)", variable=self.copy_attachments_var).grid(row=2, column=0, columnspan=2, sticky="w")
    ttk.Label(start_box, text="Pixelformat").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
    ttk.Combobox(start_box, textvariable=self.pixel_format_mode_var, state="readonly", values=["Auto / Quelle", "Quelle exakt", "10 Bit 4:2:0 (HDR/UHD)", "8 Bit 4:2:0 (SDR)"]).grid(row=3, column=1, sticky="ew", pady=(10, 0))
    ttk.Label(start_box, text="x265 Zusatzparameter").grid(row=4, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(start_box, textvariable=self.x265_extra_params_var).grid(row=4, column=1, sticky="ew", pady=(10, 0))
    ttk.Label(start_box, text="FFmpeg Zusatzargumente").grid(row=5, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(start_box, textvariable=self.ffmpeg_extra_args_var).grid(row=5, column=1, sticky="ew", pady=(10, 0))
    ttk.Button(start_box, text="Final-Render starten", style="Big.TButton", command=self.run_render).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(18, 0))

    self.on_render_limited_changed()
    self.on_size_options_changed()

def on_quality_preset_changed(self):
    # Die Vorlage bleibt für alte Workflows erhalten, auch wenn sie in der neuen Oberfläche nicht prominent angezeigt wird.
    preset = self.quality_preset_var.get()
    if preset == "Normal hochwertig (CRF 16)":
        self.video_encoder_var.set("H.265 (x265)")
        self.preset_var.set("slow")
        self.crf_var.set("16")
    elif preset == "Quellnah / sehr hoch (CRF 12)":
        self.video_encoder_var.set("H.265 10-bit (x265)")
        self.preset_var.set("slower")
        self.crf_var.set("12")
    elif preset == "Nahezu verlustfrei (CRF 10)":
        self.video_encoder_var.set("H.265 10-bit (x265)")
        self.preset_var.set("veryslow")
        self.crf_var.set("10")
    elif preset == "Extrem groß / Test (CRF 8)":
        self.video_encoder_var.set("H.265 10-bit (x265)")
        self.preset_var.set("veryslow")
        self.crf_var.set("8")

def on_size_options_changed(self):
    limit_custom = self.resolution_limit_var.get() == "Eigene"
    for widget in (getattr(self, "limit_width_entry", None), getattr(self, "limit_height_entry", None)):
        if widget is not None:
            widget.configure(state="normal" if limit_custom else "disabled")

    scaler_enabled = self.scaler_var.get() != "Keine"
    scale_custom = scaler_enabled and self.scale_to_var.get() == "Eigene"
    if getattr(self, "scale_to_combo", None) is not None:
        self.scale_to_combo.configure(state="readonly" if scaler_enabled else "disabled")
    for widget in (getattr(self, "scale_width_entry", None), getattr(self, "scale_height_entry", None)):
        if widget is not None:
            widget.configure(state="normal" if scale_custom else "disabled")
    if not scaler_enabled:
        self.scale_to_var.set("Keine")

def _collect_encoder_settings(self) -> EncoderSettings:
    try:
        crf_value = float(str(self.crf_var.get()).replace(",", "."))
    except ValueError as exc:
        raise RuntimeError("CQ/CRF muss eine Zahl sein, z.B. 12 oder 14.5.") from exc
    if crf_value < 0 or crf_value > 51:
        raise RuntimeError("CQ/CRF sollte zwischen 0 und 51 liegen. Für hohe Qualität meist 8–16.")
    return EncoderSettings(
        video_encoder=self.video_encoder_var.get(),
        preset=self.preset_var.get(),
        crf=str(self.crf_var.get()).replace(",", "."),
        tune_grain=bool(self.tune_grain_var.get()),
        resolution_limit=self.resolution_limit_var.get(),
        limit_width=self.limit_width_var.get(),
        limit_height=self.limit_height_var.get(),
        scaler=self.scaler_var.get(),
        scale_to=self.scale_to_var.get(),
        scale_width=self.scale_width_var.get(),
        scale_height=self.scale_height_var.get(),
        pixel_format_mode=self.pixel_format_mode_var.get(),
        fps_choice=self.fps_choice_var.get(),
        fps_type=self.fps_type_var.get(),
        detelecine=self.detelecine_var.get(),
        interlace_detection=self.interlace_detection_var.get(),
        deinterlace=self.deinterlace_var.get(),
        deinterlace_preset=self.deinterlace_preset_var.get(),
        denoise=self.denoise_var.get(),
        chroma_smooth=self.chroma_smooth_var.get(),
        sharpen=self.sharpen_var.get(),
        deblock=self.deblock_var.get(),
        colorspace_filter=self.colorspace_filter_var.get(),
        grayscale=bool(self.grayscale_var.get()),
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

def on_render_range_mode_changed(self):
    new_mode = self.render_mode_var.get()
    old_mode = getattr(self, "_render_last_mode", new_mode)
    self._convert_range_controls(self.render_start_var, self.render_end_var, old_mode, new_mode)
    self._render_last_mode = new_mode

def _range_render(self):
    if not self.render_limited_var.get():
        return None, None
    return (self._parse_range_value(self.render_start_var.get(), self.render_mode_var.get()),
            self._parse_range_value(self.render_end_var.get(), self.render_mode_var.get()))

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
