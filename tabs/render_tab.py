from __future__ import annotations

# HomeCinemaCrop render_tab v35

import tkinter as tk
from tkinter import ttk

from HomeCinemaCrop_core import *

RESOLUTION_PROFILE_NAMES = [
    "Keine",
    "4320p 8K Ultra HD",
    "2160p 4K Ultra HD",
    "1080p HD",
    "720p HD",
    "576p PAL SD",
    "480p NTSC SD",
    "Eigene",
]

ENCODER_NAMES = [
    "H.264 (x264)",
    "H.264 10-bit (x264)",
    "H.264 (NVENC)",
    "H.265 (x265)",
    "H.265 10-bit (x265)",
    "H.265 12-bit (x265)",
    "H.265 (NVENC)",
    "H.265 10-bit (NVENC)",
]

FPS_VALUES = [
    "Same as source", "5", "10", "12", "15", "20", "23.976", "24", "25",
    "29.97", "30", "48", "50", "59.94", "60", "72", "75", "90", "100", "120",
]

FILTER_PRESETS_4 = ["Ultra Light", "Light", "Medium", "Strong", "Custom"]
FILTER_PRESETS_6 = ["Ultra Light", "Light", "Medium", "Strong", "Stronger", "Very Strong", "Custom"]


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
    right.rowconfigure(0, weight=1)

    # 1. Final-Render-Bereich bleibt unverändert.
    range_box = ttk.LabelFrame(left, text="Final-Render-Bereich", padding=8)
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
    self._build_range_value_input(self.render_range_controls, self.render_start_var, "render_start").grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(2, 0))
    self._build_range_value_input(self.render_range_controls, self.render_end_var, "render_end").grid(row=1, column=2, sticky="ew", pady=(2, 0))
    ttk.Button(self.render_range_controls, text="Wie Vorschau-Bereich", command=self.copy_preview_range_to_render).grid(row=2, column=1, columnspan=2, sticky="ew", pady=(10, 0))
    ttk.Label(range_box, text="Ohne Haken wird der komplette Film gerendert. Zeitangaben: 125, 00:02:05 oder 00:02:05.500", style="Subtitle.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

    # 2. Bildgröße: Auflösungslimit und Skalierung getrennt.
    size_box = ttk.LabelFrame(left, text="Bildgröße", padding=8)
    size_box.grid(row=1, column=0, sticky="ew", pady=(0, 12))
    for c in range(5):
        size_box.columnconfigure(c, weight=1)

    ttk.Label(size_box, text="Auflösungslimit").grid(row=0, column=0, sticky="w")
    self.resolution_limit_combo = ttk.Combobox(size_box, textvariable=self.resolution_limit_var, values=RESOLUTION_PROFILE_NAMES, state="readonly")
    self.resolution_limit_combo.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(2, 8))
    self.resolution_limit_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_size_options_changed())
    ttk.Label(size_box, text="Breite").grid(row=0, column=1, sticky="w")
    self.limit_width_entry = ttk.Entry(size_box, textvariable=self.limit_width_var, width=10)
    self.limit_width_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(2, 8))
    ttk.Label(size_box, text="Höhe").grid(row=0, column=2, sticky="w")
    self.limit_height_entry = ttk.Entry(size_box, textvariable=self.limit_height_var, width=10)
    self.limit_height_entry.grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(2, 8))

    ttk.Label(size_box, text="Scaler").grid(row=2, column=0, sticky="w")
    self.scaler_combo = ttk.Combobox(size_box, textvariable=self.scaler_var, values=["Keine", "lanczos", "spline", "bicubic", "bilinear"], state="readonly")
    self.scaler_combo.grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=(2, 0))
    self.scaler_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_size_options_changed())
    ttk.Label(size_box, text="Skalieren auf").grid(row=2, column=1, sticky="w")
    self.scale_to_combo = ttk.Combobox(size_box, textvariable=self.scale_to_var, values=RESOLUTION_PROFILE_NAMES, state="readonly")
    self.scale_to_combo.grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=(2, 0))
    self.scale_to_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_size_options_changed())
    ttk.Label(size_box, text="Breite").grid(row=2, column=2, sticky="w")
    self.scale_width_entry = ttk.Entry(size_box, textvariable=self.scale_width_var, width=10)
    self.scale_width_entry.grid(row=3, column=2, sticky="ew", padx=(0, 8), pady=(2, 0))
    ttk.Label(size_box, text="Höhe").grid(row=2, column=3, sticky="w")
    self.scale_height_entry = ttk.Entry(size_box, textvariable=self.scale_height_var, width=10)
    self.scale_height_entry.grid(row=3, column=3, sticky="ew", pady=(2, 0))

    # 3. Video.
    video_box = ttk.LabelFrame(left, text="Video", padding=8)
    video_box.grid(row=2, column=0, sticky="ew", pady=(0, 12))
    for c in range(4):
        video_box.columnconfigure(c, weight=1)
    ttk.Label(video_box, text="Videoencoder").grid(row=0, column=0, sticky="w")
    ttk.Combobox(video_box, textvariable=self.video_encoder_var, values=ENCODER_NAMES, state="readonly").grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=(2, 8))
    ttk.Label(video_box, text="Preset").grid(row=0, column=2, sticky="w")
    ttk.Combobox(video_box, textvariable=self.preset_var, values=["ultrafast", "fast", "medium", "slow", "slower", "veryslow"], width=14).grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(2, 8))
    ttk.Label(video_box, text="CQ / CRF Qualität").grid(row=0, column=3, sticky="w")
    ttk.Entry(video_box, textvariable=self.crf_var, width=10).grid(row=1, column=3, sticky="ew", pady=(2, 8))
    ttk.Label(video_box, text="Bildfrequenz (BpS)").grid(row=2, column=0, sticky="w")
    ttk.Combobox(video_box, textvariable=self.fps_choice_var, values=FPS_VALUES, state="readonly").grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=(2, 8))
    ttk.Radiobutton(video_box, text="Konstante Bildfrequenz", variable=self.fps_type_var, value="Konstante Bildfrequenz").grid(row=3, column=1, sticky="w", padx=(0, 8))
    ttk.Radiobutton(video_box, text="Variable Bildfrequenz", variable=self.fps_type_var, value="Variable Bildfrequenz").grid(row=3, column=2, sticky="w", padx=(0, 8))
    ttk.Checkbutton(video_box, text="Film-/Grain-schonend encodieren", variable=self.tune_grain_var).grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))

    _build_filter_box(self, right)
    _build_start_box(self, right)

    self._update_range_value_input_modes("render", self.render_mode_var.get())
    self.on_render_limited_changed()
    self.on_size_options_changed()
    self.on_filter_options_changed()


def _build_filter_box(self, parent):
    outer = ttk.LabelFrame(parent, text="Filter", padding=6)
    outer.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
    outer.rowconfigure(0, weight=1)
    outer.columnconfigure(0, weight=1)

    canvas = tk.Canvas(outer, highlightthickness=0)
    scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    frame = ttk.Frame(canvas)
    frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set, height=365)
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(canvas_window, width=event.width))

    for c in range(6):
        frame.columnconfigure(c, weight=1)

    def row_header(row, text):
        ttk.Label(frame, text=text, style="Subtitle.TLabel").grid(row=row, column=0, columnspan=6, sticky="w", pady=(8, 2))

    def combo(row, col, label, var, values, width=14):
        ttk.Label(frame, text=label).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=(2, 2))
        cb = ttk.Combobox(frame, textvariable=var, values=values, state="readonly", width=width)
        cb.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=(2, 2))
        cb.bind("<<ComboboxSelected>>", lambda _event: self.on_filter_options_changed())
        return cb

    def entry(row, col, label, var, attr_name):
        ttk.Label(frame, text=label).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=(2, 2))
        ent = ttk.Entry(frame, textvariable=var)
        ent.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=(2, 2))
        setattr(self, attr_name, ent)
        return ent

    row_header(0, "Telecine / Interlace")
    self.detelecine_combo = combo(1, 0, "Detelecine", self.detelecine_var, ["Off", "Default", "Custom"])
    entry(1, 2, "Custom", self.detelecine_custom_var, "detelecine_custom_entry")
    self.comb_detect_combo = combo(2, 0, "Comb Detect", self.comb_detect_var, ["Off", "Default", "Fast", "Permissive", "Custom"])
    entry(2, 2, "Custom", self.comb_detect_custom_var, "comb_detect_custom_entry")
    self.deinterlace_combo = combo(3, 0, "Deinterlace", self.deinterlace_var, ["Off", "Yadif", "Bwdif", "Decomb"])
    self.deinterlace_preset_combo = combo(3, 2, "Preset", self.deinterlace_preset_var, ["Default", "Skip Spatial", "Bob", "EEDI2", "EEDI2 Bob", "Custom"])
    entry(4, 2, "Custom", self.deinterlace_custom_var, "deinterlace_custom_entry")

    row_header(5, "Rausch- und Farbrauschfilter")
    self.denoise_combo = combo(6, 0, "Denoise", self.denoise_var, ["Off", "NLMeans", "HQDN3D"])
    self.denoise_preset_combo = combo(6, 2, "Preset", self.denoise_preset_var, FILTER_PRESETS_4)
    self.denoise_tune_combo = combo(7, 0, "Tune", self.denoise_tune_var, ["None", "Film", "Grain", "High Motion", "Animation", "Tape", "Sprite"])
    entry(7, 2, "Custom", self.denoise_custom_var, "denoise_custom_entry")
    self.chroma_smooth_combo = combo(8, 0, "Chroma Smooth", self.chroma_smooth_var, ["Off", "On"])
    self.chroma_smooth_preset_combo = combo(8, 2, "Preset", self.chroma_smooth_preset_var, FILTER_PRESETS_6)
    self.chroma_smooth_tune_combo = combo(9, 0, "Tune", self.chroma_smooth_tune_var, ["None", "Tiny", "Small", "Medium", "Wide", "Very Wide"])
    entry(9, 2, "Custom", self.chroma_smooth_custom_var, "chroma_smooth_custom_entry")

    row_header(10, "Schärfen / Deblock")
    self.sharpen_combo = combo(11, 0, "Sharpen", self.sharpen_var, ["Off", "Unsharp", "Lapsharp"])
    self.sharpen_preset_combo = combo(11, 2, "Preset", self.sharpen_preset_var, FILTER_PRESETS_6)
    self.sharpen_tune_combo = combo(12, 0, "Tune", self.sharpen_tune_var, ["None", "Ultra Fine", "Fine", "Medium", "Coarse", "Very Coarse", "Film", "Grain", "Animation", "Sprite"])
    entry(12, 2, "Custom", self.sharpen_custom_var, "sharpen_custom_entry")
    self.deblock_combo = combo(13, 0, "Deblock", self.deblock_var, ["Off", "On"])
    self.deblock_preset_combo = combo(13, 2, "Preset", self.deblock_preset_var, FILTER_PRESETS_6)
    self.deblock_tune_combo = combo(14, 0, "Tune", self.deblock_tune_var, ["Small", "Medium", "Large"])
    entry(14, 2, "Custom", self.deblock_custom_var, "deblock_custom_entry")

    row_header(15, "Geometrie / Farbe")
    self.rotate_combo = combo(16, 0, "Rotate / Flip", self.rotate_var, ["Off", "90", "180", "270", "Horizontal spiegeln", "Vertikal spiegeln", "Custom"])
    entry(16, 2, "Custom", self.rotate_custom_var, "rotate_custom_entry")
    self.pad_combo = combo(17, 0, "Pad", self.pad_var, ["Off", "Custom"])
    entry(17, 2, "Custom", self.pad_custom_var, "pad_custom_entry")
    self.colorspace_filter_combo = combo(18, 0, "Colorspace", self.colorspace_filter_var, ["Off", "BT.2020", "BT.709", "BT.601 SMPTE-C", "BT.601 EBU", "Custom"])
    entry(18, 2, "Custom", self.colorspace_custom_var, "colorspace_custom_entry")
    ttk.Checkbutton(frame, text="Grayscale / Schwarzweiß", variable=self.grayscale_var).grid(row=19, column=1, sticky="w", pady=(6, 0))
    ttk.Label(
        frame,
        text="Hinweis: HandBrake-Filter werden hier mit FFmpeg-Äquivalenten umgesetzt. Für 4K/HDR-Master besser alles auf Off lassen, außer du willst bewusst filtern.",
        style="Subtitle.TLabel",
        wraplength=520,
    ).grid(row=20, column=0, columnspan=6, sticky="w", pady=(12, 0))


def _build_start_box(self, parent):
    start_box = ttk.LabelFrame(parent, text="Start", padding=8)
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
    ttk.Button(start_box, text="Final-Render starten", style="Big.TButton", command=self.run_render).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))


def on_quality_preset_changed(self):
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


def _set_widget_state(widget, enabled: bool, readonly: bool = False):
    if widget is None:
        return
    try:
        widget.configure(state=("readonly" if readonly and enabled else "normal" if enabled else "disabled"))
    except tk.TclError:
        pass


def on_filter_options_changed(self):
    def is_on(value):
        return (value or "").lower() not in {"", "off", "none", "keine"}

    _set_widget_state(getattr(self, "detelecine_custom_entry", None), self.detelecine_var.get() == "Custom")
    _set_widget_state(getattr(self, "comb_detect_custom_entry", None), self.comb_detect_var.get() == "Custom")

    deint_on = is_on(self.deinterlace_var.get())
    _set_widget_state(getattr(self, "deinterlace_preset_combo", None), deint_on, readonly=True)
    _set_widget_state(getattr(self, "deinterlace_custom_entry", None), deint_on and self.deinterlace_preset_var.get() == "Custom")

    denoise_on = is_on(self.denoise_var.get())
    _set_widget_state(getattr(self, "denoise_preset_combo", None), denoise_on, readonly=True)
    _set_widget_state(getattr(self, "denoise_tune_combo", None), denoise_on and self.denoise_var.get() == "NLMeans", readonly=True)
    _set_widget_state(getattr(self, "denoise_custom_entry", None), denoise_on and self.denoise_preset_var.get() == "Custom")

    chroma_on = is_on(self.chroma_smooth_var.get())
    _set_widget_state(getattr(self, "chroma_smooth_preset_combo", None), chroma_on, readonly=True)
    _set_widget_state(getattr(self, "chroma_smooth_tune_combo", None), chroma_on, readonly=True)
    _set_widget_state(getattr(self, "chroma_smooth_custom_entry", None), chroma_on and self.chroma_smooth_preset_var.get() == "Custom")

    sharpen_on = is_on(self.sharpen_var.get())
    _set_widget_state(getattr(self, "sharpen_preset_combo", None), sharpen_on, readonly=True)
    _set_widget_state(getattr(self, "sharpen_tune_combo", None), sharpen_on, readonly=True)
    _set_widget_state(getattr(self, "sharpen_custom_entry", None), sharpen_on and self.sharpen_preset_var.get() == "Custom")

    deblock_on = is_on(self.deblock_var.get())
    _set_widget_state(getattr(self, "deblock_preset_combo", None), deblock_on, readonly=True)
    _set_widget_state(getattr(self, "deblock_tune_combo", None), deblock_on, readonly=True)
    _set_widget_state(getattr(self, "deblock_custom_entry", None), deblock_on and self.deblock_preset_var.get() == "Custom")

    _set_widget_state(getattr(self, "rotate_custom_entry", None), self.rotate_var.get() == "Custom")
    _set_widget_state(getattr(self, "pad_custom_entry", None), self.pad_var.get() == "Custom")
    _set_widget_state(getattr(self, "colorspace_custom_entry", None), self.colorspace_filter_var.get() == "Custom")


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
        detelecine_custom=self.detelecine_custom_var.get(),
        comb_detect=self.comb_detect_var.get(),
        comb_detect_custom=self.comb_detect_custom_var.get(),
        deinterlace=self.deinterlace_var.get(),
        deinterlace_preset=self.deinterlace_preset_var.get(),
        deinterlace_custom=self.deinterlace_custom_var.get(),
        denoise=self.denoise_var.get(),
        denoise_preset=self.denoise_preset_var.get(),
        denoise_tune=self.denoise_tune_var.get(),
        denoise_custom=self.denoise_custom_var.get(),
        chroma_smooth=self.chroma_smooth_var.get(),
        chroma_smooth_preset=self.chroma_smooth_preset_var.get(),
        chroma_smooth_tune=self.chroma_smooth_tune_var.get(),
        chroma_smooth_custom=self.chroma_smooth_custom_var.get(),
        sharpen=self.sharpen_var.get(),
        sharpen_preset=self.sharpen_preset_var.get(),
        sharpen_tune=self.sharpen_tune_var.get(),
        sharpen_custom=self.sharpen_custom_var.get(),
        deblock=self.deblock_var.get(),
        deblock_preset=self.deblock_preset_var.get(),
        deblock_tune=self.deblock_tune_var.get(),
        deblock_custom=self.deblock_custom_var.get(),
        rotate=self.rotate_var.get(),
        rotate_custom=self.rotate_custom_var.get(),
        pad=self.pad_var.get(),
        pad_custom=self.pad_custom_var.get(),
        colorspace_filter=self.colorspace_filter_var.get(),
        colorspace_custom=self.colorspace_custom_var.get(),
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
    self._update_range_value_input_modes("render", self.render_mode_var.get())


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
    self._update_range_value_input_modes("render", new_mode)


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
