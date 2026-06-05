#!/usr/bin/env python3
"""
HomeCinemaCrop: IMAX (4:3) → 16:9 GUI v40 Audio- und Untertitel-Spurauswahl

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
import shlex
import shutil
import subprocess
import sys
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


def app_base_dir() -> Path:
    """Ordner, in dem Diagnose-Dateien abgelegt werden.

    Bei normalem Python ist das der Skriptordner. Bei einer späteren EXE ist es
    der Ordner der EXE. So findest du die Logs immer neben dem gestarteten Tool.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def write_text_log(filename: str, text: str) -> Path:
    path = app_base_dir() / filename
    path.write_text(text, encoding="utf-8", errors="replace")
    return path


def format_command_for_log(cmd: list[str]) -> str:
    try:
        return shlex.join([str(part) for part in cmd])
    except Exception:
        return " ".join(str(part) for part in cmd)


POSITIONS = ("up", "half-up", "center", "half-down", "down")
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
    hdr_master_display: Optional[str] = None
    hdr_max_cll: Optional[str] = None


@dataclasses.dataclass
class MediaStreamInfo:
    index: int
    codec_type: str
    codec_name: str = ""
    language: str = ""
    title: str = ""
    channels: Optional[int] = None
    channel_layout: str = ""
    forced: bool = False
    default: bool = False


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
    detelecine_custom: str = ""
    interlace_detection: str = "Default"
    comb_detect: str = "Off"
    comb_detect_custom: str = ""
    deinterlace: str = "Off"
    deinterlace_preset: str = "Default"
    deinterlace_custom: str = ""
    denoise: str = "Off"
    denoise_preset: str = "Medium"
    denoise_tune: str = "None"
    denoise_custom: str = ""
    chroma_smooth: str = "Off"
    chroma_smooth_preset: str = "Medium"
    chroma_smooth_tune: str = "None"
    chroma_smooth_custom: str = ""
    sharpen: str = "Off"
    sharpen_preset: str = "Medium"
    sharpen_tune: str = "None"
    sharpen_custom: str = ""
    deblock: str = "Off"
    deblock_preset: str = "Medium"
    deblock_tune: str = "Medium"
    deblock_custom: str = ""
    rotate: str = "Off"
    rotate_custom: str = ""
    pad: str = "Off"
    pad_custom: str = ""
    colorspace_filter: str = "Off"
    colorspace_custom: str = ""
    grayscale: bool = False

    # Container/Streams
    copy_metadata: bool = True
    copy_chapters: bool = True
    copy_attachments: bool = True
    selected_audio_stream_indices: Optional[tuple[int, ...]] = None
    selected_subtitle_stream_indices: Optional[tuple[int, ...]] = None
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


def _ratio_to_float(value) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if "/" in text:
            a, b = text.split("/", 1)
            return float(a) / float(b)
        return float(text)
    except Exception:
        return None


def _chromaticity_to_hdr_int(value) -> Optional[int]:
    number = _ratio_to_float(value)
    if number is None:
        return None
    # FFprobe liefert die Primärfarben meist als 0.0-1.0 Ratio.
    # FFmpeg/x265 erwarten HDR10-Chromatizität in 1/50000-Schritten.
    return int(round(number * 50000))


def _luminance_to_hdr_int(value) -> Optional[int]:
    number = _ratio_to_float(value)
    if number is None:
        return None
    # FFprobe liefert Luminanz meist in cd/m². HDR10-SEI erwartet 1/10000 cd/m².
    return int(round(number * 10000))


def _format_master_display(side_data: dict) -> Optional[str]:
    try:
        red_x = _chromaticity_to_hdr_int(side_data.get("red_x"))
        red_y = _chromaticity_to_hdr_int(side_data.get("red_y"))
        green_x = _chromaticity_to_hdr_int(side_data.get("green_x"))
        green_y = _chromaticity_to_hdr_int(side_data.get("green_y"))
        blue_x = _chromaticity_to_hdr_int(side_data.get("blue_x"))
        blue_y = _chromaticity_to_hdr_int(side_data.get("blue_y"))
        white_x = _chromaticity_to_hdr_int(side_data.get("white_point_x"))
        white_y = _chromaticity_to_hdr_int(side_data.get("white_point_y"))
        max_lum = _luminance_to_hdr_int(side_data.get("max_luminance"))
        min_lum = _luminance_to_hdr_int(side_data.get("min_luminance"))
        values = [green_x, green_y, blue_x, blue_y, red_x, red_y, white_x, white_y, max_lum, min_lum]
        if any(v is None for v in values):
            return None
        return f"G({green_x},{green_y})B({blue_x},{blue_y})R({red_x},{red_y})WP({white_x},{white_y})L({max_lum},{min_lum})"
    except Exception:
        return None


def _format_max_cll(side_data: dict) -> Optional[str]:
    max_content = side_data.get("max_content")
    max_average = side_data.get("max_average")
    try:
        if max_content is None or max_average is None:
            return None
        return f"{int(max_content)},{int(max_average)}"
    except Exception:
        return None


# Fallback für Zack Snyder's Justice League / typische UHD-HDR10-Metadaten,
# falls FFprobe die SEI-Daten nicht als side_data_list ausgibt.
# Werte entsprechen MediaInfo: Display P3, min 0.0001 / max 1000 cd/m², MaxCLL 597, MaxFALL 122.
ZSJL_HDR10_MASTER_DISPLAY = "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)"
ZSJL_HDR10_MAX_CLL = "597,122"


def _stream_is_hdr10_pq_bt2020(stream: dict) -> bool:
    transfer = (stream.get("color_transfer") or "").lower()
    primaries = (stream.get("color_primaries") or "").lower()
    colorspace = (stream.get("color_space") or "").lower()
    pix_fmt = (stream.get("pix_fmt") or "").lower()
    return (
        transfer in {"smpte2084", "pq"}
        and "bt2020" in primaries
        and (not colorspace or "bt2020" in colorspace)
        and ("10" in pix_fmt or pix_fmt in {"p010le", "p010"})
    )


def _extract_hdr_metadata(stream: dict) -> tuple[Optional[str], Optional[str]]:
    master_display = None
    max_cll = None
    for side_data in stream.get("side_data_list", []) or []:
        side_type = (side_data.get("side_data_type") or "").lower()
        if "mastering display" in side_type:
            master_display = _format_master_display(side_data) or master_display
        elif "content light" in side_type:
            max_cll = _format_max_cll(side_data) or max_cll

    # Manche MakeMKV/FFprobe-Kombinationen zeigen BT.2020/PQ korrekt an,
    # liefern aber keine auswertbare side_data_list. Ohne diese Werte schreibt
    # hevc_nvenc nur PQ/BT.2020 und Programme wie HandBrake melden trotzdem SDR.
    # Deshalb nutzen wir für diese HDR10-Quelle den bekannten MediaInfo-Fallback.
    if _stream_is_hdr10_pq_bt2020(stream):
        master_display = master_display or ZSJL_HDR10_MASTER_DISPLAY
        max_cll = max_cll or ZSJL_HDR10_MAX_CLL

    return master_display, max_cll


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
            hdr_master_display, hdr_max_cll = _extract_hdr_metadata(stream)
            return VideoInfo(
                width=int(stream["width"]),
                height=int(stream["height"]),
                fps=fps,
                frames=frames,
                pix_fmt=stream.get("pix_fmt"),
                color_space=stream.get("color_space"),
                color_transfer=stream.get("color_transfer"),
                color_primaries=stream.get("color_primaries"),
                hdr_master_display=hdr_master_display,
                hdr_max_cll=hdr_max_cll,
            )
    raise RuntimeError("Kein Videostream gefunden.")


def _stream_to_media_info(stream: dict) -> MediaStreamInfo:
    tags = stream.get("tags") or {}
    disposition = stream.get("disposition") or {}
    return MediaStreamInfo(
        index=int(stream.get("index", 0)),
        codec_type=str(stream.get("codec_type") or ""),
        codec_name=str(stream.get("codec_name") or ""),
        language=str(tags.get("language") or tags.get("LANGUAGE") or "und"),
        title=str(tags.get("title") or tags.get("TITLE") or ""),
        channels=stream.get("channels"),
        channel_layout=str(stream.get("channel_layout") or ""),
        forced=bool(disposition.get("forced")),
        default=bool(disposition.get("default")),
    )


def get_media_streams(path: Path) -> tuple[list[MediaStreamInfo], list[MediaStreamInfo]]:
    """Liest kopierbare Audio- und Untertitelspuren für die Auswahl im Audio-Tab aus."""
    meta = ffprobe_json(path)
    audio: list[MediaStreamInfo] = []
    subtitles: list[MediaStreamInfo] = []
    for stream in meta.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "audio":
            audio.append(_stream_to_media_info(stream))
        elif codec_type == "subtitle":
            subtitles.append(_stream_to_media_info(stream))
    return audio, subtitles



def _find_mkvmerge() -> Optional[str]:
    """Findet mkvmerge für den verlustfreien HDR10-Metadaten-Remux.

    FFmpeg/hevc_nvenc kann bei vielen Builds zwar 10 Bit, BT.2020 und PQ
    signalisieren, schreibt aber keine vollständigen HDR10-Mastering-Display-
    und MaxCLL/MaxFALL-Daten in den HEVC-Bitstream. Für MKV-Ausgaben setzen wir
    diese Werte deshalb nach dem Encode sauber als Matroska-Video-Colour-Elemente
    mit MKVToolNix/mkvmerge. Das ist ein Remux ohne erneutes Encodieren.
    """
    candidates = ["mkvmerge", "mkvmerge.exe"]
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    if sys.platform.startswith("win"):
        for candidate in [
            Path(r"C:\Program Files\MKVToolNix\mkvmerge.exe"),
            Path(r"C:\Program Files (x86)\MKVToolNix\mkvmerge.exe"),
        ]:
            if candidate.is_file():
                return str(candidate)
    return None


def _format_float(value: float, digits: int = 6) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _parse_master_display_for_mkvmerge(master_display: Optional[str]) -> Optional[dict]:
    if not master_display:
        return None
    pattern = (
        r"G\((\d+),(\d+)\)"
        r"B\((\d+),(\d+)\)"
        r"R\((\d+),(\d+)\)"
        r"WP\((\d+),(\d+)\)"
        r"L\((\d+),(\d+)\)"
    )
    match = re.fullmatch(pattern, master_display.strip())
    if not match:
        return None
    gx, gy, bx, by, rx, ry, wx, wy, max_lum, min_lum = [int(v) for v in match.groups()]
    return {
        "red": (rx / 50000.0, ry / 50000.0),
        "green": (gx / 50000.0, gy / 50000.0),
        "blue": (bx / 50000.0, by / 50000.0),
        "white": (wx / 50000.0, wy / 50000.0),
        "max_luminance": max_lum / 10000.0,
        "min_luminance": min_lum / 10000.0,
    }


def _parse_max_cll_for_mkvmerge(max_cll: Optional[str]) -> Optional[tuple[int, int]]:
    if not max_cll:
        return None
    parts = [part.strip() for part in max_cll.split(",", 1)]
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _needs_nvenc_hdr10_mkv_remux(selected_codec: str, info: VideoInfo, output: Path) -> bool:
    return (
        selected_codec == "hevc_nvenc"
        and output.suffix.lower() == ".mkv"
        and (info.color_transfer or "").lower() in {"smpte2084", "pq"}
        and bool(info.hdr_master_display or info.hdr_max_cll)
    )


def _run_mkvmerge_hdr10_remux(temp_output: Path, final_output: Path, info: VideoInfo) -> None:
    mkvmerge = _find_mkvmerge()
    if not mkvmerge:
        raise RuntimeError(
            "NVENC-HDR10-Metadaten können für MKV ohne MKVToolNix/mkvmerge nicht sauber gesetzt werden.\n"
            "Bitte MKVToolNix installieren oder mkvmerge.exe in den PATH aufnehmen.\n"
            f"Der FFmpeg-Zwischenstand liegt hier: {temp_output}"
        )

    master = _parse_master_display_for_mkvmerge(info.hdr_master_display)
    cll = _parse_max_cll_for_mkvmerge(info.hdr_max_cll)

    cmd = [
        mkvmerge,
        "-o", str(final_output),
        "--colour-matrix", "0:9",                    # BT.2020 non-constant
        "--colour-range", "0:1",                     # Limited / broadcast range
        "--colour-transfer-characteristics", "0:16", # SMPTE ST 2084 / PQ
        "--colour-primaries", "0:9",                 # BT.2020
    ]

    if cll:
        max_content, max_frame_avg = cll
        cmd += ["--max-content-light", f"0:{max_content}"]
        cmd += ["--max-frame-light", f"0:{max_frame_avg}"]

    if master:
        rx, ry = master["red"]
        gx, gy = master["green"]
        bx, by = master["blue"]
        wx, wy = master["white"]
        cmd += [
            "--chromaticity-coordinates",
            "0:"
            + ",".join(_format_float(v) for v in (rx, ry, gx, gy, bx, by)),
            "--white-color-coordinates",
            "0:" + ",".join(_format_float(v) for v in (wx, wy)),
            "--max-luminance",
            "0:" + _format_float(master["max_luminance"], 4),
            "--min-luminance",
            "0:" + _format_float(master["min_luminance"], 6),
        ]

    cmd.append(str(temp_output))
    command_text = format_command_for_log(cmd)
    command_log = write_text_log("last_mkvmerge_command.txt", command_text + "\n")

    if final_output.exists():
        final_output.unlink()

    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    combined_output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        error_log = write_text_log(
            "last_mkvmerge_error.log",
            f"mkvmerge wurde mit Fehlercode {result.returncode} beendet.\n\n"
            f"Befehl:\n{command_text}\n\n"
            f"Ausgabe:\n{combined_output}"
        )
        raise RuntimeError(
            f"mkvmerge wurde mit Fehlercode {result.returncode} beendet.\n\n"
            f"Logdateien:\n{error_log}\n{command_log}\n\n"
            f"Ausgabe:\n{combined_output[-2500:]}"
        )

    write_text_log(
        "last_mkvmerge_error.log",
        "mkvmerge erfolgreich beendet.\n\nBefehl:\n" + command_text + "\n\nAusgabe:\n" + combined_output
    )
    try:
        temp_output.unlink()
    except Exception:
        pass


def crop_height(width: int) -> int:
    return int(round(width * 9 / 16))


def crop_offsets(width: int, height: int):
    ch = crop_height(width)
    slack = height - ch
    # Fünf feste CSV-Positionen von oben nach unten.
    # half-up liegt genau zwischen up und center, half-down zwischen center und down.
    return {
        "up": 0,
        "half-up": int(round(slack * 0.25)),
        "center": int(round(slack * 0.50)),
        "half-down": int(round(slack * 0.75)),
        "down": slack,
    }


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
                raise RuntimeError(f"Ungültige Position in Zeile {row_index}: {pos_text}. Erlaubt: up, half-up, center, half-down, down")
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



def _safe_int(value, default: int, min_value: int, max_value: int) -> int:
    try:
        number = int(float(str(value).replace(",", ".")))
    except Exception:
        number = default
    return max(min_value, min(max_value, number))


def _safe_float(value, default: float, min_value: float, max_value: float) -> float:
    try:
        number = float(str(value).replace(",", "."))
    except Exception:
        number = default
    return max(min_value, min(max_value, number))


def draw_crop_frame_on_cv2_image(frame, box_y: int, box_h: int, line_width: int = 3, alpha: float = 1.0):
    """Zeichnet den beweglichen 16:9-Rahmen für die Vorschau direkt ins Bild.

    Wird nur für die neue Rahmen-Preview verwendet. Der finale Render bleibt davon
    unberührt.
    """
    h, w = frame.shape[:2]
    line_width = _safe_int(line_width, 3, 1, 50)
    alpha = _safe_float(alpha, 1.0, 0.0, 1.0)
    x1, y1 = 0, max(0, int(box_y))
    x2, y2 = max(0, w - 1), min(h - 1, int(box_y + box_h - 1))
    if alpha <= 0:
        return frame
    if alpha >= 0.999:
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), line_width)
        return frame
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 0, 0), line_width)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, dst=frame)
    return frame


def render_preview(source: Path, csv_path: Path, out: Path, start: Optional[int], end: Optional[int], precrop: PreCrop, progress, cancelled, frame_preview: bool = False, frame_width: int = 3, frame_alpha: float = 1.0):
    info = get_video_info(source)
    base_w, base_h = size_after_precrop(info.width, info.height, precrop)
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
    writer_size = (base_w, base_h) if frame_preview else (base_w, h)
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), info.fps, writer_size)
    if not writer.isOpened():
        raise RuntimeError(f"Vorschau-Ausgabe kann nicht geöffnet werden: {out}")
    total_preview_frames = end_zero - start_zero + 1
    current_zero = start_zero
    written = 0
    frame_width = _safe_int(frame_width, 3, 1, 50)
    frame_alpha = _safe_float(frame_alpha, 1.0, 0.0, 1.0)
    while current_zero <= end_zero:
        if cancelled():
            raise Cancelled()
        ok, frame = cap.read()
        if not ok:
            break
        pos = INDEX_TO_POSITION[int(states[current_zero])]
        frame = apply_precrop_to_frame(frame, precrop)
        if frame_preview:
            # Rahmen-Preview: komplettes Bild nach Vorschnitt ausgeben und den
            # beweglichen 16:9-Ausschnitt aus der CSV als blauen Rahmen einbrennen.
            box_y = crop_offsets(base_w, base_h)[pos]
            output_frame = frame.copy()
            draw_crop_frame_on_cv2_image(output_frame, box_y, h, frame_width, frame_alpha)
        else:
            # Normale Vorschau bleibt unverändert: nur den fertigen 16:9-Ausschnitt ausgeben.
            output_frame = crop_frame(frame, pos)
        cv2.putText(output_frame, f"Frame {current_zero + 1}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(output_frame, pos, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        writer.write(output_frame)
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


def _custom_or_empty(value: str) -> str:
    return (value or "").strip()


def _hb_strength_to_float(value: str, default: float = 0.8) -> float:
    token = _filter_token(value).replace(" ", "-")
    return {
        "ultra-light": 0.25,
        "light": 0.45,
        "medium": 0.75,
        "strong": 1.0,
        "stronger": 1.25,
        "very-strong": 1.5,
    }.get(token, default)


def _hb_denoise_strength(value: str) -> str:
    token = _filter_token(value).replace(" ", "-")
    return {
        "ultra-light": "1.5:1.5:4:4",
        "light": "2:2:6:6",
        "medium": "3:3:8:8",
        "strong": "4:4:10:10",
        "stronger": "6:6:12:12",
        "very-strong": "8:8:16:16",
    }.get(token, "3:3:8:8")


def _append_custom_or_default(filters: list[str], custom_value: str, default_filter: str):
    custom = _custom_or_empty(custom_value)
    filters.append(custom if custom else default_filter)


def build_video_filter(base_w: int, base_h: int, ch: int, precrop: PreCrop, crop_expr: str, info: VideoInfo, settings: EncoderSettings) -> str:
    filters = [
        f"crop={base_w}:{base_h}:{precrop.left}:{precrop.top}",
        f"crop={base_w}:{ch}:0:'{crop_expr}'",
    ]

    # Filter im Stil von HandBrake. Standard ist überall Off, damit UHD/HDR-Material nicht versehentlich verändert wird.
    if _filter_token(settings.detelecine) == "custom":
        _append_custom_or_default(filters, settings.detelecine_custom, "fieldmatch,decimate")
    elif _filter_token(settings.detelecine) not in {"", "off"}:
        filters += ["fieldmatch", "decimate"]

    # Comb Detect hat in FFmpeg keinen 1:1-Filter. Für Decomb wird unten bwdif/yadif verwendet.
    # Custom erlaubt trotzdem gezielte FFmpeg-Filterketten.
    if _filter_token(settings.comb_detect) == "custom":
        custom = _custom_or_empty(settings.comb_detect_custom)
        if custom:
            filters.append(custom)

    deint = _filter_token(settings.deinterlace)
    deint_preset = _filter_token(settings.deinterlace_preset)
    if deint == "custom" or deint_preset == "custom":
        custom = _custom_or_empty(settings.deinterlace_custom)
        if custom:
            filters.append(custom)
    elif deint == "yadif":
        filters.append("yadif=mode=1" if deint_preset in {"bob"} else "yadif")
    elif deint in {"decomb", "bwdif"}:
        filters.append("bwdif=mode=1" if deint_preset in {"bob", "eedi2-bob", "eedi2 bob"} else "bwdif")

    denoise = _filter_token(settings.denoise)
    denoise_preset = _filter_token(settings.denoise_preset)
    if denoise_preset == "custom":
        custom = _custom_or_empty(settings.denoise_custom)
        if custom:
            filters.append(custom)
    elif denoise == "hqdn3d":
        filters.append("hqdn3d=" + _hb_denoise_strength(settings.denoise_preset))
    elif denoise == "nlmeans":
        strength = _hb_strength_to_float(settings.denoise_preset, 0.8)
        filters.append(f"nlmeans=s={strength:.2f}")

    chroma = _filter_token(settings.chroma_smooth)
    chroma_preset = _filter_token(settings.chroma_smooth_preset)
    if chroma_preset == "custom":
        custom = _custom_or_empty(settings.chroma_smooth_custom)
        if custom:
            filters.append(custom)
    elif chroma not in {"", "off"}:
        strength = _hb_strength_to_float(settings.chroma_smooth_preset, 0.7)
        filters.append(f"chromanr=thres={max(1, int(strength * 20))}")

    sharp = _filter_token(settings.sharpen)
    sharp_preset = _filter_token(settings.sharpen_preset)
    if sharp_preset == "custom":
        custom = _custom_or_empty(settings.sharpen_custom)
        if custom:
            filters.append(custom)
    elif sharp == "unsharp":
        amount = _hb_strength_to_float(settings.sharpen_preset, 0.75)
        filters.append(f"unsharp=5:5:{amount:.2f}:3:3:{amount/2:.2f}")
    elif sharp == "lapsharp":
        # FFmpeg hat keinen direkten LapSharp-Filter wie HandBrake; unsharp ist der sichere Ersatz.
        amount = _hb_strength_to_float(settings.sharpen_preset, 0.8)
        filters.append(f"unsharp=5:5:{amount:.2f}:3:3:{amount/2:.2f}")

    deblock = _filter_token(settings.deblock)
    deblock_preset = _filter_token(settings.deblock_preset)
    if deblock_preset == "custom":
        custom = _custom_or_empty(settings.deblock_custom)
        if custom:
            filters.append(custom)
    elif deblock not in {"", "off"}:
        filters.append("pp=de")

    rotate = _filter_token(settings.rotate)
    if rotate == "custom":
        custom = _custom_or_empty(settings.rotate_custom)
        if custom:
            filters.append(custom)
    elif rotate == "90":
        filters.append("transpose=1")
    elif rotate == "180":
        filters.append("hflip,vflip")
    elif rotate == "270":
        filters.append("transpose=2")
    elif "horizontal" in rotate:
        filters.append("hflip")
    elif "vertikal" in rotate or "vertical" in rotate:
        filters.append("vflip")

    if _filter_token(settings.pad) == "custom":
        custom = _custom_or_empty(settings.pad_custom)
        if custom:
            filters.append(custom)

    colorspace = _filter_token(settings.colorspace_filter)
    if colorspace == "custom":
        custom = _custom_or_empty(settings.colorspace_custom)
        if custom:
            filters.append(custom)
    elif colorspace in {"bt.709", "bt709", "rec.709", "rec709"}:
        # HDR/PQ -> BT.709 braucht Tonemapping. Ein einfacher colorspace-Filter kann dabei fehlschlagen.
        if (info.color_transfer or "").lower() in {"smpte2084", "pq"}:
            filters.append("zscale=t=linear:npl=100,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:p=bt709")
        else:
            filters.append("colorspace=all=bt709")
    elif colorspace in {"bt.2020", "bt2020", "rec.2020", "rec2020"}:
        filters.append("colorspace=all=bt2020")
    elif colorspace in {"bt.601 smpte-c", "smpte-c", "bt601 smpte-c"}:
        filters.append("colorspace=all=smpte170m")
    elif colorspace in {"bt.601 ebu", "ebu", "bt601 ebu"}:
        filters.append("colorspace=all=bt470bg")

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

    # Bei Ausschnitt-Rendern Zeitstempel der neuen Videospur sauber bei 0 starten.
    # Das verhindert falsche FPS-Anzeigen in einigen Analyseprogrammen.
    filters.append("setpts=PTS-STARTPTS")

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
        if info.hdr_master_display:
            params.append(f"master-display={info.hdr_master_display}")
        if info.hdr_max_cll:
            params.append(f"max-cll={info.hdr_max_cll}")
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
    else:
        cmd += ["-map_metadata", "-1"]
    if settings.copy_chapters:
        cmd += ["-map_chapters", "0"]
    else:
        cmd += ["-map_chapters", "-1"]

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
    nvenc_hdr10_mkv_remux = _needs_nvenc_hdr10_mkv_remux(selected_codec, info, output)
    ffmpeg_output_path = output
    if nvenc_hdr10_mkv_remux:
        ffmpeg_output_path = output.with_name(output.stem + "_ffmpeg_tmp" + output.suffix)

    cmd += ["-map", "0:v:0"]
    for stream_index in settings.selected_audio_stream_indices or ():
        cmd += ["-map", f"0:{int(stream_index)}"]
    for stream_index in settings.selected_subtitle_stream_indices or ():
        cmd += ["-map", f"0:{int(stream_index)}"]
    if settings.copy_attachments:
        cmd += ["-map", "0:t?"]
    cmd += ["-c:v", selected_codec]

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

    cmd.append(str(ffmpeg_output_path))

    command_text = format_command_for_log(cmd)
    command_log = write_text_log("last_ffmpeg_command.txt", command_text + "\n")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True, errors="replace")
    frame_regex = re.compile(r"^frame=(\d+)$")
    ffmpeg_lines: list[str] = []
    if process.stdout is None:
        raise RuntimeError("FFmpeg-Ausgabe konnte nicht gelesen werden.")
    for raw_line in process.stdout:
        ffmpeg_lines.append(raw_line)
        if cancelled():
            process.terminate()
            write_text_log("last_ffmpeg_error.log", "Abgebrochen durch Benutzer.\n\nBefehl:\n" + command_text + "\n\nAusgabe:\n" + "".join(ffmpeg_lines))
            raise Cancelled()
        match = frame_regex.match(raw_line.strip())
        if match:
            progress(min(int(match.group(1)), total_frames), total_frames, "Finales Video wird gerendert ...")
    process.wait()
    ffmpeg_output = "".join(ffmpeg_lines)
    if process.returncode != 0:
        error_log = write_text_log(
            "last_ffmpeg_error.log",
            f"FFmpeg wurde mit Fehlercode {process.returncode} beendet.\n\n"
            f"Befehl:\n{command_text}\n\n"
            f"FFmpeg-Ausgabe:\n{ffmpeg_output}"
        )
        tail_lines = [line for line in ffmpeg_output.strip().splitlines() if line.strip()][-18:]
        tail = "\n".join(tail_lines) if tail_lines else "Keine FFmpeg-Ausgabe empfangen."
        raise RuntimeError(
            f"FFmpeg wurde mit Fehlercode {process.returncode} beendet.\n\n"
            f"Logdateien:\n{error_log}\n{command_log}\n\n"
            f"Letzte FFmpeg-Meldungen:\n{tail}"
        )
    write_text_log("last_ffmpeg_error.log", "FFmpeg erfolgreich beendet.\n\nBefehl:\n" + command_text + "\n\nAusgabe:\n" + ffmpeg_output)

    if nvenc_hdr10_mkv_remux:
        progress(total_frames, total_frames, "NVENC-HDR10-Metadaten werden mit MKVToolNix gesetzt ...")
        _run_mkvmerge_hdr10_remux(ffmpeg_output_path, output, info)

    progress(total_frames, total_frames, f"Fertig gespeichert: {output}")

