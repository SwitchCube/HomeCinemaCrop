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
