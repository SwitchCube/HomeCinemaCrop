#!/usr/bin/env python3
"""
HomeCinemaCrop: IMAX (4:3) → 16:9 GUI v24 Encoder+Qualität

Workflow:
1. Datei wählen
2. optionaler manueller Vorschnitt wie in HandBrake (z.B. MakeMKV-16:9 -> echtes 4:3/IMAX-Bild)
3. CSV mit up/center/down laden oder erzeugen
4. Vorschau oder Final-Render ausgeben

Benötigt: Python, FFmpeg/FFprobe im PATH, OpenCV, NumPy. Pillow ist optional für die Vorschnitt-Bildvorschau.
"""
from __future__ import annotations

import csv
import dataclasses
import json
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

try:
    import cv2
    import numpy as np
except Exception as exc:
    cv2 = None
    np = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

POSITIONS = ("up", "center", "down")
POSITION_TO_INDEX = {name: index for index, name in enumerate(POSITIONS)}
INDEX_TO_POSITION = {index: name for index, name in enumerate(POSITIONS)}


@dataclasses.dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    frames: int
    pix_fmt: Optional[str] = None
    color_space: Optional[str] = None
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None


@dataclasses.dataclass
class PreCrop:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclasses.dataclass
class EncoderSettings:
    # Video / Encoder
    video_encoder: str = "H.265 10-bit (x265)"
    preset: str = "slower"
    crf: str = "12"
    tune_grain: bool = True

    # Bildgröße: Auflösungslimit und optionale Skalierung sind getrennt.
    resolution_limit: str = "Keine"
    limit_width: str = "3840"
    limit_height: str = "2160"
    scaler: str = "Keine"
    scale_to: str = "Keine"
    scale_width: str = "3840"
    scale_height: str = "2160"

    # Pixelformat / FPS
    pixel_format_mode: str = "Auto / Quelle"
    fps_choice: str = "Same as source"
    fps_type: str = "Konstante Bildfrequenz"

    # Filter nach HandBrake-Vorbild
    detelecine: str = "Off"
    interlace_detection: str = "Default"
    deinterlace: str = "Off"
    deinterlace_preset: str = "Default"
    denoise: str = "Off"
    chroma_smooth: str = "Off"
    sharpen: str = "Off"
    deblock: str = "Off"
    colorspace_filter: str = "Off"
    grayscale: bool = False

    # Container/Streams
    copy_metadata: bool = True
    copy_chapters: bool = True
    copy_attachments: bool = True
    x265_extra_params: str = ""
    ffmpeg_extra_args: str = ""


class Cancelled(Exception):
    pass


def ffprobe_json(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def parse_fraction(text: str) -> float:
    if "/" in text:
        a, b = text.split("/", 1)
        return float(a) / float(b)
    return float(text)


def get_video_info(path: Path) -> VideoInfo:
    meta = ffprobe_json(path)
    for stream in meta.get("streams", []):
        if stream.get("codec_type") == "video":
            fps = parse_fraction(stream.get("avg_frame_rate", "0/1"))
            try:
                frames = int(stream.get("nb_frames", 0))
            except (TypeError, ValueError):
                frames = 0
            if frames <= 0 and fps > 0 and stream.get("duration"):
                try:
                    frames = int(round(float(stream["duration"]) * fps))
                except Exception:
                    frames = 0
            return VideoInfo(
                width=int(stream["width"]),
                height=int(stream["height"]),
                fps=fps,
                frames=frames,
                pix_fmt=stream.get("pix_fmt"),
                color_space=stream.get("color_space"),
                color_transfer=stream.get("color_transfer"),
                color_primaries=stream.get("color_primaries"),
            )
    raise RuntimeError("Kein Videostream gefunden.")


def crop_height(width: int) -> int:
    return int(round(width * 9 / 16))


def crop_offsets(width: int, height: int):
    ch = crop_height(width)
    slack = height - ch
    return {"up": 0, "center": slack // 2, "down": slack}


def normalize_precrop(left=0, right=0, top=0, bottom=0) -> PreCrop:
    values = []
    for name, value in [("Links", left), ("Rechts", right), ("Oben", top), ("Unten", bottom)]:
        try:
            ivalue = int(str(value).strip() or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{name} muss eine ganze Zahl sein.") from exc
        if ivalue < 0:
            raise RuntimeError(f"{name} darf nicht negativ sein.")
        values.append(ivalue)
    return PreCrop(*values)


def size_after_precrop(width: int, height: int, precrop: PreCrop) -> Tuple[int, int]:
    out_w = width - precrop.left - precrop.right
    out_h = height - precrop.top - precrop.bottom
    if out_w <= 0 or out_h <= 0:
        raise RuntimeError("Der Vorschnitt ist zu groß. Es bleibt kein gültiges Bild übrig.")
    ch = crop_height(out_w)
    if out_h < ch:
        raise RuntimeError(f"Nach dem Vorschnitt ist das Bild zu niedrig für 16:9. Übrig: {out_w}x{out_h}, benötigt mindestens Höhe {ch}.")
    return out_w, out_h


def apply_precrop_to_frame(frame, precrop: PreCrop):
    h, w = frame.shape[:2]
    out_w, out_h = size_after_precrop(w, h, precrop)
    return frame[precrop.top:precrop.top + out_h, precrop.left:precrop.left + out_w, :]


def crop_frame(frame, pos: str):
    h, w = frame.shape[:2]
    ch = crop_height(w)
    y = crop_offsets(w, h)[pos]
    return frame[y:y + ch, :, :]


def write_csv(path: Path, states) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["frame", "position"])
        for i, state in enumerate(states, start=1):
            writer.writerow([i, INDEX_TO_POSITION[int(state)]])


def read_csv(path: Path):
    states = []
    expected_frame = 1
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        if reader.fieldnames != ["frame", "position"]:
            raise RuntimeError("CSV-Kopfzeile muss genau so sein: frame;position")
        for row_index, row in enumerate(reader, start=2):
            frame_text = (row.get("frame") or "").strip()
            pos_text = (row.get("position") or "").strip().lower()
            try:
                frame_number = int(frame_text)
            except ValueError as exc:
                raise RuntimeError(f"Ungültige Frame-Nummer in Zeile {row_index}: {frame_text}") from exc
            if frame_number != expected_frame:
                raise RuntimeError(f"Frames müssen lückenlos aufsteigend sein. Zeile {row_index}: gefunden {frame_number}, erwartet {expected_frame}")
            if pos_text not in POSITION_TO_INDEX:
                raise RuntimeError(f"Ungültige Position in Zeile {row_index}: {pos_text}. Erlaubt: up, center, down")
            states.append(POSITION_TO_INDEX[pos_text])
            expected_frame += 1
    if not states:
        raise RuntimeError("CSV enthält keine Daten.")
    return np.array(states, dtype=np.int32)


def build_crop_expr(states, width: int, height: int) -> str:
    offsets = crop_offsets(width, height)
    segments = []
    start = 0
    current = int(states[0])
    for i in range(1, len(states)):
        if int(states[i]) != current:
            segments.append((start, i - 1, current))
            start = i
            current = int(states[i])
    segments.append((start, len(states) - 1, current))
    parts = []
    for seg_start, seg_end, pos_index in segments:
        pos_name = INDEX_TO_POSITION[pos_index]
        y = offsets[pos_name]
        parts.append(f"between(n\\,{seg_start}\\,{seg_end})*{y}")
    return "+".join(parts)


def create_center_csv(source: Path, csv_out: Path, progress, cancelled):
    info = get_video_info(source)
    total = int(info.frames)
    if total <= 0:
        cap = cv2.VideoCapture(str(source))
        if not cap.isOpened():
            raise RuntimeError(f"Quelle kann nicht geöffnet werden: {source}")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
    if total <= 0:
        raise RuntimeError("Die Frame-Anzahl konnte nicht ermittelt werden. Bitte prüfe die Videodatei oder erstelle die CSV manuell.")
    states = []
    center_state = POSITION_TO_INDEX["center"]
    for frame_index in range(1, total + 1):
        if cancelled():
            raise Cancelled()
        states.append(center_state)
        if frame_index % 1000 == 0 or frame_index == total:
            progress(frame_index, total, "CSV wird mit Center-Werten erstellt ...")
    write_csv(csv_out, states)
    progress(total, total, f"CSV gespeichert: {csv_out}")


def render_preview(source: Path, csv_path: Path, out: Path, start: Optional[int], end: Optional[int], precrop: PreCrop, progress, cancelled):
    info = get_video_info(source)
    base_w, _ = size_after_precrop(info.width, info.height, precrop)
    states = read_csv(csv_path)
    total_csv_frames = len(states)
    start = 1 if start is None else start
    end = total_csv_frames if end is None else min(end, total_csv_frames)
    if start < 1:
        raise RuntimeError("Start-Frame muss >= 1 sein.")
    if end < start:
        raise RuntimeError("End-Frame muss >= Start-Frame sein.")
    start_zero = start - 1
    end_zero = end - 1
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"Quelle kann nicht geöffnet werden: {source}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_zero)
    h = crop_height(base_w)
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), info.fps, (base_w, h))
    if not writer.isOpened():
        raise RuntimeError(f"Vorschau-Ausgabe kann nicht geöffnet werden: {out}")
    total_preview_frames = end_zero - start_zero + 1
    current_zero = start_zero
    written = 0
    while current_zero <= end_zero:
        if cancelled():
            raise Cancelled()
        ok, frame = cap.read()
        if not ok:
            break
        pos = INDEX_TO_POSITION[int(states[current_zero])]
        frame = apply_precrop_to_frame(frame, precrop)
        cropped = crop_frame(frame, pos)
        cv2.putText(cropped, f"Frame {current_zero + 1}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(cropped, pos, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        writer.write(cropped)
        current_zero += 1
        written += 1
        if written % 10 == 0 or written == total_preview_frames:
            progress(written, total_preview_frames, "Vorschau wird erstellt ...")
    cap.release()
    writer.release()
    progress(total_preview_frames, total_preview_frames, f"Vorschau gespeichert: {out}")


def fps_fraction_for_ffmpeg(fps: float) -> Optional[str]:
    if fps <= 0:
        return None
    # Gängige Film-Framerates sauber als Bruch ausgeben.
    if abs(fps - 23.976) < 0.02:
        return "24000/1001"
    if abs(fps - 29.970) < 0.02:
        return "30000/1001"
    if abs(fps - 59.940) < 0.03:
        return "60000/1001"
    if abs(fps - 24.000) < 0.01:
        return "24"
    if abs(fps - 25.000) < 0.01:
        return "25"
    if abs(fps - 30.000) < 0.01:
        return "30"
    return f"{fps:.6f}"


def choose_pix_fmt(info: VideoInfo, settings: EncoderSettings) -> Optional[str]:
    mode = settings.pixel_format_mode
    src = info.pix_fmt or ""
    if mode == "Auto / Quelle":
        if "10" in src:
            return "yuv420p10le"
        return src or None
    if mode == "Quelle exakt":
        return src or None
    if mode == "10 Bit 4:2:0 (HDR/UHD)":
        return "yuv420p10le"
    if mode == "8 Bit 4:2:0 (SDR)":
        return "yuv420p"
    return None


RESOLUTION_PRESETS = {
    "4320p 8K Ultra HD": (7680, 4320),
    "2160p 4K Ultra HD": (3840, 2160),
    "1080p HD": (1920, 1080),
    "720p HD": (1280, 720),
    "576p PAL SD": (720, 576),
    "480p NTSC SD": (720, 480),
}


def _parse_wh_pair(width_text: str, height_text: str, label: str) -> tuple[int, int]:
    try:
        w = int(str(width_text).strip())
        h = int(str(height_text).strip())
    except ValueError as exc:
        raise RuntimeError(f"{label}: Breite und Höhe müssen ganze Zahlen sein.") from exc
    if w <= 0 or h <= 0:
        raise RuntimeError(f"{label}: Breite und Höhe müssen größer als 0 sein.")
    return w, h


def _resolution_from_mode(mode: str, custom_w: str, custom_h: str, label: str) -> Optional[tuple[int, int]]:
    if mode in {"", "Keine", "None"}:
        return None
    if mode in {"Eigene", "Benutzerdefiniert", "Custom"}:
        return _parse_wh_pair(custom_w, custom_h, label)
    if mode in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[mode]
    raise RuntimeError(f"Unbekanntes Auflösungsprofil bei {label}: {mode}")


def _filter_token(value: str) -> str:
    return (value or "").strip().lower()


def build_video_filter(base_w: int, base_h: int, ch: int, precrop: PreCrop, crop_expr: str, info: VideoInfo, settings: EncoderSettings) -> str:
    filters = [
        f"crop={base_w}:{base_h}:{precrop.left}:{precrop.top}",
        f"crop={base_w}:{ch}:0:'{crop_expr}'",
    ]

    # Filter im Stil von HandBrake. Standard ist überall Off, damit UHD/HDR-Material nicht versehentlich verändert wird.
    if _filter_token(settings.detelecine) not in {"", "off"}:
        filters += ["fieldmatch", "decimate"]

    deint = _filter_token(settings.deinterlace)
    if deint in {"yadif"}:
        filters.append("yadif")
    elif deint in {"decomb", "bwdif"}:
        filters.append("bwdif")

    denoise = _filter_token(settings.denoise)
    if denoise == "hqdn3d":
        filters.append("hqdn3d")
    elif denoise == "nlmeans":
        filters.append("nlmeans")

    chroma = _filter_token(settings.chroma_smooth)
    if chroma not in {"", "off"}:
        filters.append("chromanr")

    sharp = _filter_token(settings.sharpen)
    if sharp == "unsharp":
        filters.append("unsharp")
    elif sharp == "lapsharp":
        # FFmpeg hat keinen direkten LapSharp-Filter wie HandBrake; unsharp ist der sichere Ersatz.
        filters.append("unsharp=5:5:0.8:3:3:0.4")

    deblock = _filter_token(settings.deblock)
    if deblock in {"weak", "medium", "strong"}:
        filters.append("pp=de")

    colorspace = _filter_token(settings.colorspace_filter)
    if colorspace in {"bt.709", "bt709", "rec.709", "rec709"}:
        filters.append("colorspace=all=bt709")
    elif colorspace in {"bt.2020", "bt2020", "rec.2020", "rec2020"}:
        filters.append("colorspace=all=bt2020")

    if settings.grayscale:
        filters.append("format=gray")

    # Auflösungslimit: nur herunterskalieren, wenn das Bild größer als das Limit ist.
    limit = _resolution_from_mode(settings.resolution_limit, settings.limit_width, settings.limit_height, "Auflösungslimit")
    if limit is not None:
        lw, lh = limit
        filters.append(
            f"scale='if(gt(iw/{lw},ih/{lh}),min(iw\\,{lw}),-2)':"
            f"'if(gt(iw/{lw},ih/{lh}),-2,min(ih\\,{lh}))':flags=lanczos"
        )

    # Skalierung: gezielt auf eine Zielgröße hoch-/runterskalieren.
    scaler = settings.scaler if settings.scaler not in {"", "Keine"} else None
    scale_to = _resolution_from_mode(settings.scale_to, settings.scale_width, settings.scale_height, "Skalierung")
    if scaler and scale_to is not None:
        sw, sh = scale_to
        filters.append(f"scale={sw}:{sh}:flags={settings.scaler}")

    return ",".join(filters)


def build_x265_params(info: VideoInfo, settings: EncoderSettings, pix_fmt: Optional[str]) -> list[str]:
    params = []
    if pix_fmt and "10" in pix_fmt:
        params.append("profile=main10")
    if info.color_primaries:
        params.append(f"colorprim={info.color_primaries}")
    if info.color_transfer:
        params.append(f"transfer={info.color_transfer}")
    if info.color_space:
        params.append(f"colormatrix={info.color_space}")
    if (info.color_transfer or "").lower() in {"smpte2084", "pq"}:
        # Wichtig für HDR10-Re-Encodes: Header regelmäßig schreiben und HDR10-Modus aktivieren.
        params += ["hdr10=1", "hdr10-opt=1", "repeat-headers=1"]
    if settings.tune_grain:
        # Für Filmkorn und feine Schattenbereiche meistens besser als zu aggressives Glätten.
        params += ["no-sao=1", "strong-intra-smoothing=0"]
    extra = (settings.x265_extra_params or "").strip()
    if extra:
        params += [part.strip() for part in extra.split(":") if part.strip()]
    return params


def render_final(source: Path, csv_path: Path, output: Path, settings: EncoderSettings, precrop: PreCrop, start: Optional[int], end: Optional[int], progress, cancelled):
    info = get_video_info(source)
    states_all = read_csv(csv_path)
    total_csv_frames = len(states_all)
    start = 1 if start is None else start
    end = total_csv_frames if end is None else min(end, total_csv_frames)
    if start < 1:
        raise RuntimeError("Start-Frame muss >= 1 sein.")
    if end < start:
        raise RuntimeError("End-Frame muss >= Start-Frame sein.")
    start_zero = start - 1
    end_zero = end - 1
    states = states_all[start_zero:end_zero + 1]
    total_frames = len(states)
    base_w, base_h = size_after_precrop(info.width, info.height, precrop)
    ch = crop_height(base_w)
    crop_expr = build_crop_expr(states, base_w, base_h)
    filter_v = build_video_filter(base_w, base_h, ch, precrop, crop_expr, info, settings)

    cmd = ["ffmpeg", "-y"]
    if start_zero > 0 and info.fps > 0:
        cmd += ["-ss", f"{start_zero / info.fps:.6f}"]
    cmd += ["-progress", "pipe:1", "-nostats", "-i", str(source)]
    if total_frames > 0 and info.fps > 0 and (start != 1 or end != total_csv_frames):
        cmd += ["-t", f"{total_frames / info.fps:.6f}"]

    cmd += ["-filter:v", filter_v]

    if settings.copy_metadata:
        cmd += ["-map_metadata", "0"]
    if settings.copy_chapters:
        cmd += ["-map_chapters", "0"]

    encoder_label = settings.video_encoder
    encoder_map = {
        "H.264 (x264)": "libx264",
        "H.264 10-bit (x264)": "libx264",
        "H.264 (NVENC)": "h264_nvenc",
        "H.265 (x265)": "libx265",
        "H.265 10-bit (x265)": "libx265",
        "H.265 12-bit (x265)": "libx265",
        "H.265 (NVENC)": "hevc_nvenc",
        "H.265 10-bit (NVENC)": "hevc_nvenc",
    }
    selected_codec = encoder_map.get(encoder_label, "libx265")
    use_nvenc = selected_codec in {"hevc_nvenc", "h264_nvenc"}

    cmd += ["-map", "0", "-c:v", selected_codec]

    pix_fmt = choose_pix_fmt(info, settings)
    if "10-bit" in encoder_label and pix_fmt not in {"yuv420p10le", "p010le"}:
        pix_fmt = "p010le" if use_nvenc else "yuv420p10le"
    elif "12-bit" in encoder_label:
        pix_fmt = "yuv420p12le"
    if use_nvenc and pix_fmt == "yuv420p10le":
        # NVENC erwartet für 10-Bit 4:2:0 normalerweise p010le.
        pix_fmt = "p010le"

    if selected_codec in {"libx265", "libx264"}:
        cmd += ["-preset", settings.preset, "-crf", str(settings.crf)]
    elif selected_codec in {"hevc_nvenc", "h264_nvenc"}:
        # GPU-Encoding: CRF gibt es bei NVENC nicht. Wir nutzen denselben Qualitätswert als CQ.
        # Je kleiner CQ, desto höhere Qualität und desto größere Datei.
        nvenc_preset = "p7" if settings.preset in {"slower", "veryslow"} else "p5" if settings.preset in {"slow", "medium"} else "p3"
        cmd += ["-preset", nvenc_preset, "-rc:v", "vbr", "-cq:v", str(settings.crf), "-b:v", "0"]
    if selected_codec == "libx265" and settings.tune_grain:
        cmd += ["-tune", "grain"]

    if pix_fmt:
        cmd += ["-pix_fmt", pix_fmt]

    if selected_codec == "libx265":
        x265_params = build_x265_params(info, settings, pix_fmt)
        if x265_params:
            cmd += ["-x265-params", ":".join(x265_params)]

    if info.color_space:
        cmd += ["-colorspace", info.color_space]
    if info.color_transfer:
        cmd += ["-color_trc", info.color_transfer]
    if info.color_primaries:
        cmd += ["-color_primaries", info.color_primaries]

    # Framerate wie in HandBrake: Same as source oder explizite FPS, plus CFR/VFR.
    if settings.fps_choice == "Same as source":
        fps_value = fps_fraction_for_ffmpeg(info.fps)
    else:
        fps_value = str(settings.fps_choice)
    if fps_value:
        cmd += ["-r", fps_value]
    if settings.fps_type == "Konstante Bildfrequenz":
        cmd += ["-fps_mode", "cfr"]
    elif settings.fps_type == "Variable Bildfrequenz":
        cmd += ["-fps_mode", "vfr"]

    cmd += ["-c:a", "copy", "-c:s", "copy"]
    if settings.copy_attachments:
        cmd += ["-c:t", "copy"]

    extra_args = (settings.ffmpeg_extra_args or "").strip()
    if extra_args:
        # Einfache Zusatzargumente, z.B. -movflags +faststart. Keine Shell-Auswertung.
        cmd += extra_args.split()

    cmd.append(str(output))

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
    frame_regex = re.compile(r"^frame=(\d+)$")
    if process.stdout is None:
        raise RuntimeError("FFmpeg-Ausgabe konnte nicht gelesen werden.")
    for raw_line in process.stdout:
        if cancelled():
            process.terminate()
            raise Cancelled()
        match = frame_regex.match(raw_line.strip())
        if match:
            progress(min(int(match.group(1)), total_frames), total_frames, "Finales Video wird gerendert ...")
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg wurde mit Fehlercode {process.returncode} beendet.")
    progress(total_frames, total_frames, f"Fertig gespeichert: {output}")

