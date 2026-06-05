from __future__ import annotations

# HomeCinemaCrop audio_tab v40

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from HomeCinemaCrop_core import *


def _build_audio_tab(self):
    f = self.tab_audio
    f.columnconfigure(0, weight=1)
    f.columnconfigure(1, weight=1)
    f.rowconfigure(0, weight=1)

    audio_box = ttk.LabelFrame(f, text="Audiospuren", padding=10)
    audio_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
    audio_box.columnconfigure(0, weight=1)
    audio_box.rowconfigure(1, weight=1)

    audio_buttons = ttk.Frame(audio_box)
    audio_buttons.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    ttk.Button(audio_buttons, text="Alle anwählen", command=lambda: self.set_audio_tracks_checked(True)).pack(side="left")
    ttk.Button(audio_buttons, text="Alle abwählen", command=lambda: self.set_audio_tracks_checked(False)).pack(side="left", padx=(8, 0))
    ttk.Button(audio_buttons, text="Spuren neu laden", command=self.refresh_media_tracks).pack(side="right")

    self.audio_tracks_frame = _make_scroll_frame(audio_box, row=1)
    ttk.Label(audio_box, textvariable=self.audio_track_status_var, style="Subtitle.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))

    subtitle_box = ttk.LabelFrame(f, text="Untertitel", padding=10)
    subtitle_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
    subtitle_box.columnconfigure(0, weight=1)
    subtitle_box.rowconfigure(1, weight=1)

    subtitle_buttons = ttk.Frame(subtitle_box)
    subtitle_buttons.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    ttk.Button(subtitle_buttons, text="Alle anwählen", command=lambda: self.set_subtitle_tracks_checked(True)).pack(side="left")
    ttk.Button(subtitle_buttons, text="Alle abwählen", command=lambda: self.set_subtitle_tracks_checked(False)).pack(side="left", padx=(8, 0))

    self.subtitle_tracks_frame = _make_scroll_frame(subtitle_box, row=1)
    ttk.Label(subtitle_box, textvariable=self.subtitle_track_status_var, style="Subtitle.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))

    options = ttk.LabelFrame(f, text="Übernahme beim Final-Render", padding=10)
    options.grid(row=1, column=0, columnspan=2, sticky="ew")
    options.columnconfigure(0, weight=1)
    ttk.Checkbutton(options, text="Kapitel übernehmen", variable=self.copy_chapters_var).grid(row=0, column=0, sticky="w")
    ttk.Checkbutton(
        options,
        text="Allgemeine Metadaten übernehmen (Video-HDR/Farbdaten bleiben unabhängig davon erhalten)",
        variable=self.copy_metadata_var,
    ).grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Label(
        options,
        text="Audio und Untertitel werden weiterhin nur kopiert, nicht neu encodiert. Der Final-Render übernimmt nur angehakte Spuren.",
        style="Subtitle.TLabel",
    ).grid(row=2, column=0, sticky="w", pady=(10, 0))

    self._rebuild_audio_track_lists()


def _make_scroll_frame(parent, row: int):
    outer = ttk.Frame(parent)
    outer.grid(row=row, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(0, weight=1)
    canvas = tk.Canvas(outer, highlightthickness=0, height=300)
    scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    frame = ttk.Frame(canvas)
    frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
    window = canvas.create_window((0, 0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
    return frame


def refresh_media_tracks(self):
    source = Path(self.source_var.get())
    if not source.is_file():
        self.media_audio_streams = []
        self.media_subtitle_streams = []
        self.audio_track_vars = {}
        self.subtitle_track_vars = {}
        self.audio_track_status_var.set("Noch keine Quelle geladen.")
        self.subtitle_track_status_var.set("Noch keine Quelle geladen.")
        self._rebuild_audio_track_lists()
        return
    try:
        audio, subtitles = get_media_streams(source)
        old_audio_checked = {idx: var.get() for idx, var in getattr(self, "audio_track_vars", {}).items()}
        old_subtitle_checked = {idx: var.get() for idx, var in getattr(self, "subtitle_track_vars", {}).items()}
        self.media_audio_streams = audio
        self.media_subtitle_streams = subtitles
        self.audio_track_vars = {stream.index: tk.BooleanVar(value=old_audio_checked.get(stream.index, True)) for stream in audio}
        self.subtitle_track_vars = {stream.index: tk.BooleanVar(value=old_subtitle_checked.get(stream.index, True)) for stream in subtitles}
        self._rebuild_audio_track_lists()
        self.status_var.set(f"Spuren geladen: {len(audio)} Audio, {len(subtitles)} Untertitel.")
    except Exception as exc:
        messagebox.showerror("Spuren konnten nicht geladen werden", str(exc))


def _rebuild_audio_track_lists(self):
    for frame_name in ("audio_tracks_frame", "subtitle_tracks_frame"):
        frame = getattr(self, frame_name, None)
        if frame is not None:
            for child in frame.winfo_children():
                child.destroy()

    audio_frame = getattr(self, "audio_tracks_frame", None)
    if audio_frame is not None:
        if not getattr(self, "media_audio_streams", []):
            ttk.Label(audio_frame, text="Keine Audiospuren gefunden.", style="Subtitle.TLabel").pack(anchor="w")
        for stream in getattr(self, "media_audio_streams", []):
            ttk.Checkbutton(
                audio_frame,
                text=_format_media_stream_label(stream),
                variable=self.audio_track_vars.setdefault(stream.index, tk.BooleanVar(value=True)),
                command=self._update_track_status_texts,
            ).pack(anchor="w", fill="x", pady=2)

    subtitle_frame = getattr(self, "subtitle_tracks_frame", None)
    if subtitle_frame is not None:
        if not getattr(self, "media_subtitle_streams", []):
            ttk.Label(subtitle_frame, text="Keine Untertitelspuren gefunden.", style="Subtitle.TLabel").pack(anchor="w")
        for stream in getattr(self, "media_subtitle_streams", []):
            ttk.Checkbutton(
                subtitle_frame,
                text=_format_media_stream_label(stream),
                variable=self.subtitle_track_vars.setdefault(stream.index, tk.BooleanVar(value=True)),
                command=self._update_track_status_texts,
            ).pack(anchor="w", fill="x", pady=2)

    self._update_track_status_texts()


def _format_media_stream_label(stream: MediaStreamInfo) -> str:
    parts = [f"#{stream.index}"]
    if stream.language:
        parts.append(stream.language)
    if stream.codec_name:
        parts.append(stream.codec_name)
    if stream.codec_type == "audio":
        if stream.channels:
            parts.append(f"{stream.channels} Kanäle")
        if stream.channel_layout:
            parts.append(stream.channel_layout)
    if stream.title:
        parts.append(f"– {stream.title}")
    flags = []
    if stream.default:
        flags.append("Default")
    if stream.forced:
        flags.append("Forced")
    if flags:
        parts.append("(" + ", ".join(flags) + ")")
    return "  ".join(str(part) for part in parts if str(part).strip())


def _update_track_status_texts(self):
    audio_total = len(getattr(self, "media_audio_streams", []))
    audio_selected = len(self.get_selected_audio_stream_indices()) if hasattr(self, "get_selected_audio_stream_indices") else 0
    subtitle_total = len(getattr(self, "media_subtitle_streams", []))
    subtitle_selected = len(self.get_selected_subtitle_stream_indices()) if hasattr(self, "get_selected_subtitle_stream_indices") else 0
    self.audio_track_status_var.set(f"{audio_selected} von {audio_total} Audiospuren ausgewählt.")
    self.subtitle_track_status_var.set(f"{subtitle_selected} von {subtitle_total} Untertiteln ausgewählt.")


def set_audio_tracks_checked(self, checked: bool):
    for var in getattr(self, "audio_track_vars", {}).values():
        var.set(bool(checked))
    self._update_track_status_texts()


def set_subtitle_tracks_checked(self, checked: bool):
    for var in getattr(self, "subtitle_track_vars", {}).values():
        var.set(bool(checked))
    self._update_track_status_texts()


def get_selected_audio_stream_indices(self) -> tuple[int, ...]:
    selected = []
    for stream in getattr(self, "media_audio_streams", []):
        var = self.audio_track_vars.get(stream.index)
        if var is not None and var.get():
            selected.append(int(stream.index))
    return tuple(selected)


def get_selected_subtitle_stream_indices(self) -> tuple[int, ...]:
    selected = []
    for stream in getattr(self, "media_subtitle_streams", []):
        var = self.subtitle_track_vars.get(stream.index)
        if var is not None and var.get():
            selected.append(int(stream.index))
    return tuple(selected)
