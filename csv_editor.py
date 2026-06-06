from __future__ import annotations

# HomeCinemaCrop CSV Editor v15 - fenstergebundene Tastatursteuerung

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import ctypes
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Optional

from HomeCinemaCrop_core import *

CSV_EDITOR_VERSION = "v15"


class MpvIpcClient:
    """Kleiner JSON-IPC-Client fuer mpv.

    Der Editor liest wichtige Player-Properties aktiv von mpv zurück.
    Dadurch stimmen Pause, Frame-Anzeige und CSV-Schreibposition besser mit
    dem tatsächlich angezeigten Bild überein.
    """

    def __init__(self, pipe_path: str):
        self.pipe_path = pipe_path
        self.is_windows = platform.system().lower().startswith("win")

    def command(self, command: list, expect_response: bool = False):
        request_id = int(time.time() * 1000000) % 2147483647
        payload = json.dumps({"command": command, "request_id": request_id}, ensure_ascii=False) + "\n"
        data = payload.encode("utf-8", errors="replace")
        if self.is_windows:
            # Windows named pipe. Eine bidirektionale Verbindung erlaubt das
            # Zurücklesen von get_property-Antworten. Das ist wichtig, damit
            # die CSV-Position wirklich dem angezeigten mpv-Frame entspricht.
            with open(self.pipe_path, "r+b", buffering=0) as handle:
                handle.write(data)
                handle.flush()
                if expect_response:
                    line = handle.readline().decode("utf-8", errors="replace")
                    return json.loads(line) if line.strip() else None
                return None
        else:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(self.pipe_path)
                sock.sendall(data)
                if expect_response:
                    chunks = []
                    while True:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        if b"\n" in chunk:
                            break
                    text = b"".join(chunks).decode("utf-8", errors="replace").split("\n", 1)[0]
                    return json.loads(text) if text.strip() else None
                return None


class CsvEditorWindow(tk.Toplevel):
    """Separater CSV-Editor mit eingebettetem mpv-Player.

    Der Editor wird weiterhin aus HomeCinemaCrop heraus geoeffnet und bekommt
    Quelle, CSV und Vorschnitt direkt vom Hauptprogramm. HomeCinemaCrop selbst
    bleibt davon unabhaengig.
    """

    def __init__(self, master, source: Path, csv_path: Path, precrop: PreCrop):
        super().__init__(master)
        self.source = Path(source)
        self.csv_path = Path(csv_path)
        self.precrop = precrop
        self.info = get_video_info(self.source)
        self.states = read_csv(self.csv_path)
        self.total_frames = len(self.states)
        self.current_frame = 1
        self.playing = False
        self._play_started_at = 0.0
        self._play_started_frame = 1
        self._pending_range_start: Optional[int] = None
        self._pending_range_position: Optional[str] = None
        self._scrubbing = False
        self._mpv_process: Optional[subprocess.Popen] = None
        self._mpv: Optional[MpvIpcClient] = None
        self._last_overlay_position: Optional[str] = None
        self._mpv_ready = False
        self._ass_overlay_path: Optional[Path] = None
        self._last_status_osd = ""
        self._last_status_osd_time = 0.0
        self._held_arrow_direction: Optional[int] = None
        self._keyboard_prev = {"space": False, "left": False, "right": False, "up": False, "down": False}
        self._keyboard_last_step_at = 0.0
        self._keyboard_poll_enabled = False


        self.preview_width_var = tk.StringVar(value="1280")
        self.frame_width_var = tk.StringVar(value="5")
        self.frame_alpha_var = tk.StringVar(value="100")
        self.step_frames_var = tk.StringVar(value="1")
        self.audio_track_var = tk.StringVar(value="Standard-Audio")
        self.current_frame_var = tk.StringVar(value="1")
        self.current_time_var = tk.StringVar(value="00:00:00")
        self.last_mark_var = tk.StringVar(value="Noch kein Startpunkt gesetzt")
        self.position_var = tk.StringVar(value="center")
        self.status_var = tk.StringVar(value="Bereit.")
        self.persistent_info_var = tk.StringVar(value="Frame 1 | 00:00:00 | CSV-Position: center")
        self._scrub_var = tk.IntVar(value=1)

        self.title(f"HomeCinemaCrop CSV-Editor {CSV_EDITOR_VERSION}")
        self.geometry("1340x840")
        self.minsize(1050, 680)
        self.protocol("WM_DELETE_WINDOW", self.close_editor)
        try:
            # Der CSV-Editor bleibt ein eigenes Fenster, blockiert HomeCinemaCrop aber nicht.
            # Tastaturbefehle gelten nur fuer das aktuell aktive/angeklickte Fenster.
            self.transient(master)
            self.focus_force()
        except Exception:
            pass

        self._load_media_tracks_for_settings()
        self._build_ui()
        self._install_key_bindings()
        self.after(200, self._start_mpv_after_widget_exists)
        self.after(40, self._ui_loop)

    # ------------------------------------------------------------------
    # mpv backend
    # ------------------------------------------------------------------
    def _find_mpv(self) -> Optional[str]:
        """Findet mpv zuerst lokal im HomeCinemaCrop-Projektordner.

        Erwartete portable Struktur unter Windows:
            HomeCinemaCrop/
            ├─ HomeCinemaCrop.py
            ├─ csv_editor.py
            └─ mpv/
               └─ mpv.exe

        Danach wird wie bisher PATH/Standard-Installationsorte geprüft.
        """
        script_dir = Path(__file__).resolve().parent
        cwd = Path.cwd().resolve()
        base_candidates = [script_dir, cwd]
        if getattr(sys, "frozen", False):
            base_candidates.insert(0, Path(sys.executable).resolve().parent)

        names = ["mpv.exe", "mpv.com", "mpv"] if platform.system().lower().startswith("win") else ["mpv"]
        for base in base_candidates:
            for name in names:
                for candidate in (
                    base / "mpv" / name,
                    base / name,
                ):
                    if candidate.is_file():
                        return str(candidate)

        for name in ("mpv", "mpv.exe"):
            found = shutil.which(name)
            if found:
                return found
        if platform.system().lower().startswith("win"):
            for candidate in (
                Path(r"C:\Program Files\mpv\mpv.exe"),
                Path(r"C:\Program Files (x86)\mpv\mpv.exe"),
                Path(r"C:\Tools\mpv\mpv.exe"),
            ):
                if candidate.is_file():
                    return str(candidate)
        return None

    def _make_ipc_path(self) -> str:
        if platform.system().lower().startswith("win"):
            return rf"\\.\pipe\homecinemacrop_csv_editor_{os.getpid()}_{int(time.time() * 1000)}"
        return str(Path(tempfile.gettempdir()) / f"homecinemacrop_csv_editor_{os.getpid()}_{int(time.time() * 1000)}.sock")

    def _write_editor_log(self, filename: str, text: str) -> None:
        """Schreibt Diagnose-Dateien neben csv_editor.py."""
        try:
            path = Path(__file__).resolve().parent / filename
            path.write_text(text, encoding="utf-8", errors="replace")
        except Exception:
            pass

    def _start_mpv_after_widget_exists(self):
        try:
            self.video_panel.update_idletasks()
            wid = self.video_panel.winfo_id()
            self._start_mpv(wid)
        except Exception as exc:
            messagebox.showerror("mpv konnte nicht gestartet werden", str(exc))
            self.status_var.set(f"mpv konnte nicht gestartet werden: {exc}")


    def _write_mpv_input_conf(self) -> Path:
        """mpv-Keymap für eingebettete Wiedergabe.

        Wenn das mpv-Fenster den Tastaturfokus hat, kommen Tkinter-Keybindings
        unter Windows nicht zuverlässig an. Darum bekommt mpv eigene Bindings
        für Play/Pause und Frame-Step. Die GUI synchronisiert sich danach über
        IPC-Properties wieder auf den tatsächlich angezeigten Frame.
        """
        path = Path(tempfile.gettempdir()) / f"homecinemacrop_csv_editor_input_{os.getpid()}.conf"
        path.write_text(
            # Die eigentliche Logik liegt im Lua-Script. Hier werden die Tasten
            # nur neutral gelassen, damit mpv sie nicht mit Standard-Shortcuts
            # belegt, falls das Lua-Script noch nicht geladen ist.
            "SPACE ignore\n"
            "RIGHT ignore\n"
            "LEFT ignore\n",
            encoding="utf-8",
            errors="replace",
        )
        self._mpv_input_conf_path = path
        return path

    def _write_mpv_editor_lua(self) -> Path:
        """Lua-Script fuer mpv-interne Tastatursteuerung.

        Wichtig fuer Windows: Sobald der Benutzer in das eingebettete mpv-Bild
        klickt, bekommt mpv den Tastaturfokus und Tkinter-Keybindings kommen
        nicht mehr sicher an. Dieses Script bindet Leertaste und Pfeiltasten
        direkt in mpv. Dadurch funktionieren Play/Pause und Halten der
        Pfeiltasten auch dann, wenn der Fokus im Player liegt.
        """
        fps = max(1.0, float(self.info.fps or 23.976))
        path = Path(tempfile.gettempdir()) / f"homecinemacrop_csv_editor_keys_{os.getpid()}.lua"
        lua = """
local step_busy = false

local function pause_player()
    mp.set_property_bool("pause", true)
end

local function request_step(dir)
    -- Keine Timer, keine Warteschlange: jede echte Taste bzw. jede
    -- Betriebssystem-Wiederholung darf genau einen Step anfragen. Wenn mpv noch
    -- arbeitet, wird der neue Request ignoriert. Dadurch gibt es beim Loslassen
    -- keinen langen Nachlauf.
    if step_busy then
        return
    end
    step_busy = true
    pause_player()
    local command = (dir > 0) and {"frame-step"} or {"frame-back-step"}
    mp.command_native_async(command, function()
        step_busy = false
        pause_player()
    end)
end

local function right_key(e)
    if e.event == "down" or e.event == "repeat" then
        request_step(1)
    elseif e.event == "up" then
        pause_player()
    end
end

local function left_key(e)
    if e.event == "down" or e.event == "repeat" then
        request_step(-1)
    elseif e.event == "up" then
        pause_player()
    end
end

mp.add_forced_key_binding("SPACE", "hcc_space", function(e)
    if e.event == "down" then
        local p = mp.get_property_bool("pause", true)
        mp.set_property_bool("pause", not p)
    end
end, {complex=true, repeatable=false})

mp.add_forced_key_binding("RIGHT", "hcc_right", right_key, {complex=true, repeatable=true})
mp.add_forced_key_binding("LEFT", "hcc_left", left_key, {complex=true, repeatable=true})
""".replace("__FPS__", f"{fps:.6f}")
        path.write_text(lua, encoding="utf-8", errors="replace")
        self._mpv_lua_script_path = path
        return path

    def _start_mpv(self, window_id: int):
        mpv = self._find_mpv()
        if not mpv:
            raise RuntimeError(
                "mpv wurde nicht gefunden.\n\n"
                "Fuer fluessige Wiedergabe mit Audio und Frame-Step braucht der CSV-Editor v5 mpv.\n"
                "Bitte mpv installieren oder als HomeCinemaCrop\\mpv\\mpv.exe ablegen."
            )
        self._ipc_path = self._make_ipc_path()
        start_time = 0.0
        crop_option = self._build_mpv_crop_option()
        ass_overlay = self._write_ass_overlay()
        cmd = [
            mpv,
            str(self.source),
            f"--wid={window_id}",
            "--idle=no",
            "--keep-open=yes",
            "--force-window=yes",
            "--osc=no",
            "--osd-level=0",
            "--no-terminal",
            f"--input-conf={self._write_mpv_input_conf()}",
            "--pause=yes",
            f"--start={start_time:.6f}",
            "--hwdec=auto-safe",
            "--hr-seek=yes",
            "--hr-seek-framedrop=no",
            f"--input-ipc-server={self._ipc_path}",
            f"--video-crop={crop_option}",
            "--sub-auto=no",
            "--sub-visibility=yes",
        ]
        if ass_overlay is not None:
            cmd.append(f"--sub-file={ass_overlay}")
        aid = self._audio_aid_argument()
        if aid:
            cmd.append(aid)
        self._write_editor_log("last_csv_editor_mpv_command.txt", format_command_for_log(cmd) + "\n")
        err_log_path = Path(__file__).resolve().parent / "last_csv_editor_mpv_error.log"
        self._mpv_error_handle = open(err_log_path, "w", encoding="utf-8", errors="replace")
        self._mpv_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=self._mpv_error_handle)
        self._mpv = MpvIpcClient(self._ipc_path)
        self._wait_for_ipc()
        self._mpv_ready = True
        self._set_frame_state(1, seek=False)
        self.after(100, self._update_visual_overlays)
        self._mpv_set_pause(True)
        self.status_var.set("mpv bereit. Leertaste: Play/Pause. Links/Rechts: 1 Frame; Halten: schneller Avidemux-artiger Step.")

    def _wait_for_ipc(self):
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                self._mpv_command(["get_property", "pause"], ignore_errors=False)
                return
            except Exception:
                time.sleep(0.05)
        raise RuntimeError("mpv IPC-Verbindung konnte nicht aufgebaut werden.")

    def _mpv_command(self, command: list, ignore_errors: bool = True, expect_response: bool = False):
        if not self._mpv:
            return None
        try:
            return self._mpv.command(command, expect_response=expect_response)
        except Exception:
            if not ignore_errors:
                raise
            return None

    def _mpv_get_property(self, name: str, default=None):
        response = self._mpv_command(["get_property", name], ignore_errors=True, expect_response=True)
        if isinstance(response, dict) and response.get("error") == "success":
            return response.get("data", default)
        return default

    def _mpv_set_pause(self, paused: bool):
        self._mpv_command(["set_property", "pause", bool(paused)])

    def _audio_aid_argument(self) -> Optional[str]:
        value = self.audio_track_var.get()
        if value == "Keine Audioausgabe":
            return "--aid=no"
        if value == "Standard-Audio":
            return "--aid=auto"
        # mpv track IDs stimmen nicht in jedem Container 1:1 mit ffprobe stream indices ueberein.
        # Fuer viele MKV-Dateien funktioniert die Reihenfolge aber brauchbar: erste Audio = aid 1.
        try:
            marker = value.split(" ", 1)[0]
            if marker.startswith("Audio"):
                aid = int(marker.replace("Audio", ""))
                return f"--aid={aid}"
        except Exception:
            pass
        return "--aid=auto"

    def _apply_audio_setting_live(self):
        value = self.audio_track_var.get()
        if value == "Keine Audioausgabe":
            self._mpv_command(["set_property", "aid", "no"])
        elif value == "Standard-Audio":
            self._mpv_command(["set_property", "aid", "auto"])
        else:
            try:
                marker = value.split(" ", 1)[0]
                if marker.startswith("Audio"):
                    aid = int(marker.replace("Audio", ""))
                    self._mpv_command(["set_property", "aid", aid])
            except Exception:
                self._mpv_command(["set_property", "aid", "auto"])

    def _build_mpv_crop_option(self) -> str:
        """Erzeugt den festen Vorschnitt als mpv video-crop-Option.

        Wichtig: v8 nutzt nicht mehr den mpv/lavfi-Cropfilter. Der hatte bei
        einigen Windows/mpv-Builds nach kurzer Zeit ein schwarzes Bild erzeugt.
        Stattdessen wird die native mpv-Property video-crop benutzt:
        Breite x Höhe + X + Y.
        """
        base_w, base_h = size_after_precrop(self.info.width, self.info.height, self.precrop)
        return f"{base_w}x{base_h}+{self.precrop.left}+{self.precrop.top}"

    def _ass_time(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds - h * 3600 - m * 60
        cs = int(round((s - int(s)) * 100))
        if cs >= 100:
            cs = 0
            s = int(s) + 1
        return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"

    def _ass_draw_rect_event(self, start: str, end: str, x: int, y: int, w: int, h: int, alpha_hex: str) -> str:
        # ASS-Farbe: &HAABBGGRR. Blau = BB=FF, RR/GG=00.
        color = f"&H{alpha_hex}FF0000"
        drawing = f"m 0 0 l {max(1,w)} 0 l {max(1,w)} {max(1,h)} l 0 {max(1,h)}"
        text = r"{\an7\bord0\shad0\p1\pos(%d,%d)\1c%s}%s" % (int(x), int(y), color, drawing)
        return f"Dialogue: 0,{start},{end},Box,,0,0,0,,{text}"

    def _write_ass_overlay(self) -> Optional[Path]:
        """Schreibt den blauen 16:9-Rahmen als natives ASS-Subtitle-Overlay.

        Dadurch zeichnet mpv den Rahmen selbst. Tkinter muss nicht mehr ueber
        das eingebettete mpv-Fenster malen, was unter Windows unzuverlaessig ist
        und das schwarze Bild verursachen konnte.
        """
        try:
            base_w, base_h = size_after_precrop(self.info.width, self.info.height, self.precrop)
            box_h = crop_height(base_w)
            line = max(1, int(self._frame_width()))
            alpha = max(0.0, min(1.0, self._frame_alpha()))
            ass_alpha = int(round((1.0 - alpha) * 255))
            alpha_hex = f"{ass_alpha:02X}"
            fps = max(self.info.fps, 1.0)
            events: list[str] = []

            start_idx = 0
            current = int(self.states[0]) if len(self.states) else POSITION_TO_INDEX["center"]
            for i in range(1, len(self.states)):
                if int(self.states[i]) != current:
                    events += self._ass_events_for_segment(start_idx, i - 1, current, fps, base_w, base_h, box_h, line, alpha_hex)
                    start_idx = i
                    current = int(self.states[i])
            if len(self.states):
                events += self._ass_events_for_segment(start_idx, len(self.states) - 1, current, fps, base_w, base_h, box_h, line, alpha_hex)

            header = f"""[Script Info]
ScriptType: v4.00+
ScaledBorderAndShadow: yes
PlayResX: {base_w}
PlayResY: {base_h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,Arial,20,&H00FF0000,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            if self._ass_overlay_path is None:
                self._ass_overlay_path = Path(tempfile.gettempdir()) / f"homecinemacrop_csv_editor_overlay_{os.getpid()}.ass"
            self._ass_overlay_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8", errors="replace")
            return self._ass_overlay_path
        except Exception as exc:
            self._write_editor_log("last_csv_editor_overlay_error.log", str(exc))
            return None

    def _ass_events_for_segment(self, seg_start: int, seg_end: int, pos_index: int, fps: float, base_w: int, base_h: int, box_h: int, line: int, alpha_hex: str) -> list[str]:
        pos_name = INDEX_TO_POSITION[int(pos_index)]
        box_y = crop_offsets(base_w, base_h)[pos_name]
        start = self._ass_time(seg_start / fps)
        # Ein kleines Stueck laenger, damit der letzte Frame sicher noch den Rahmen hat.
        end = self._ass_time((seg_end + 1.25) / fps)
        y1 = int(box_y)
        y2 = int(box_y + box_h - line)
        w = int(base_w)
        h = int(base_h)
        return [
            self._ass_draw_rect_event(start, end, 0, y1, w, line, alpha_hex),
            self._ass_draw_rect_event(start, end, 0, y2, w, line, alpha_hex),
            self._ass_draw_rect_event(start, end, 0, y1, line, box_h, alpha_hex),
            self._ass_draw_rect_event(start, end, max(0, w - line), y1, line, box_h, alpha_hex),
        ]

    def _reload_ass_overlay(self):
        path = self._write_ass_overlay()
        if not path or not self._mpv_ready:
            return
        # mpv kann externe Untertitel neu laden. Falls das mit einem Build nicht
        # klappt, wird beim naechsten Oeffnen trotzdem die aktualisierte Datei genutzt.
        self._mpv_command(["sub-reload"])

    def _update_mpv_overlay_if_needed(self, frame_no: int):
        self._update_visual_overlays()
    def _display_geometry(self) -> tuple[int, int, int, int, float]:
        panel_w = max(1, int(self.video_panel.winfo_width()))
        panel_h = max(1, int(self.video_panel.winfo_height()))
        base_w, base_h = size_after_precrop(self.info.width, self.info.height, self.precrop)
        video_aspect = base_w / max(base_h, 1)
        panel_aspect = panel_w / max(panel_h, 1)
        if panel_aspect > video_aspect:
            disp_h = panel_h
            disp_w = int(round(disp_h * video_aspect))
            x = (panel_w - disp_w) // 2
            y = 0
        else:
            disp_w = panel_w
            disp_h = int(round(disp_w / video_aspect))
            x = 0
            y = (panel_h - disp_h) // 2
        scale = disp_h / max(base_h, 1)
        return x, y, disp_w, disp_h, scale

    def _ensure_overlay_widgets(self):
        # v8 zeichnet den Rahmen nicht mehr mit Tk ueber dem mpv-Fenster.
        # Native Windows-Child-Fenster von mpv liegen sonst oft ueber Tk-Widgets
        # oder werden schwarz. Der blaue Rahmen kommt jetzt als ASS-Overlay aus mpv.
        return

    def _update_visual_overlays(self):
        """Aktualisiert die Statusanzeige ueber mpv-OSD und unten im Editor."""
        try:
            pos = self._position_for_frame(self.current_frame)
            text = (
                f"Frame {self.current_frame} / {self.total_frames} | "
                f"{self.current_time_var.get()} | "
                f"{self.info.fps:.3f} FPS | CSV-Position: {pos}"
            )
            self.persistent_info_var.set(text)
            now = time.time()
            if self._mpv_ready and (text != self._last_status_osd or now - self._last_status_osd_time > 2.0):
                self._last_status_osd = text
                self._last_status_osd_time = now
                self._mpv_command(["show-text", text, 5000])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=10)
        left.grid(row=0, column=0, sticky="nsw")
        left.columnconfigure(0, weight=1)

        pos_box = ttk.LabelFrame(left, text="CSV-Position aktueller Frame", padding=8)
        pos_box.grid(row=0, column=0, sticky="ew")
        for pos in POSITIONS:
            ttk.Radiobutton(
                pos_box,
                text=pos,
                value=pos,
                variable=self.position_var,
                command=self.apply_position_to_current_frame,
            ).pack(fill="x", anchor="w", pady=3)

        nav_box = ttk.LabelFrame(left, text="Position", padding=8)
        nav_box.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(nav_box, text="Zeit").grid(row=0, column=0, sticky="w")
        time_entry = ttk.Entry(nav_box, textvariable=self.current_time_var, width=14)
        time_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Button(nav_box, text="Springen", command=self.jump_to_time_entry).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(nav_box, text="Frame").grid(row=1, column=0, sticky="w")
        frame_entry = ttk.Entry(nav_box, textvariable=self.current_frame_var, width=14)
        frame_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Button(nav_box, text="Springen", command=self.jump_to_frame_entry).grid(row=1, column=2, padx=(6, 0))

        info_box = ttk.LabelFrame(left, text="Bereich setzen", padding=8)
        info_box.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(info_box, textvariable=self.last_mark_var, wraplength=230).pack(anchor="w")
        ttk.Button(info_box, text="● Start/Ende setzen", command=self.mark_or_apply_range).pack(fill="x", pady=(8, 0))
        ttk.Label(
            info_box,
            text="1. Startframe + Position wählen und klicken.\n2. Endframe wählen und erneut klicken.",
            style="Subtitle.TLabel",
            wraplength=230,
        ).pack(anchor="w", pady=(8, 0))

        main = ttk.Frame(self, padding=(0, 10, 10, 10))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        self.video_panel = tk.Frame(main, bg="#000000", width=960, height=540)
        self.video_panel.grid(row=0, column=0, sticky="nsew")
        self.video_panel.grid_propagate(False)
        self.video_panel.bind("<Configure>", lambda _event: self._update_visual_overlays())

        ttk.Label(main, textvariable=self.persistent_info_var, style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))

        scrub = ttk.Scale(main, from_=1, to=max(1, self.total_frames), orient="horizontal", variable=self._scrub_var)
        scrub.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        scrub.bind("<ButtonPress-1>", self._start_scrub)
        scrub.bind("<ButtonRelease-1>", self._end_scrub)
        scrub.bind("<B1-Motion>", self._do_scrub)
        self.scrub = scrub

        bottom = ttk.Frame(main)
        bottom.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(4, weight=1)
        ttk.Button(bottom, text="⏮", command=lambda: self.step_frame(-self._step_frames())).grid(row=0, column=1, padx=4)
        self.play_button = ttk.Button(bottom, text="▶", width=8, command=self.toggle_play)
        self.play_button.grid(row=0, column=2, padx=4)
        ttk.Button(bottom, text="⏭", command=lambda: self.step_frame(self._step_frames())).grid(row=0, column=3, padx=4)
        ttk.Button(bottom, text="💾", command=self.save_csv).grid(row=0, column=5, padx=(20, 4))
        ttk.Button(bottom, text="⚙", command=self.open_settings).grid(row=0, column=6, padx=4)
        ttk.Label(main, textvariable=self.status_var, style="Subtitle.TLabel").grid(row=4, column=0, sticky="w", pady=(6, 0))

    def _install_key_bindings(self):
        # v15: Keine globale Tastatursteuerung und kein Windows-Key-Polling.
        # Tk verarbeitet Tasten nur, wenn der CSV-Editor aktiv ist.
        # Wenn das eingebettete mpv-Bild den Fokus hat, uebernimmt das mpv-Lua-Script.
        self.bind("<space>", self._on_space, add="+")
        self.bind("<KeyPress-Left>", lambda event: self._on_arrow_press(event, -1), add="+")
        self.bind("<KeyRelease-Left>", lambda event: self._on_arrow_release(event, -1), add="+")
        self.bind("<KeyPress-Right>", lambda event: self._on_arrow_press(event, 1), add="+")
        self.bind("<KeyRelease-Right>", lambda event: self._on_arrow_release(event, 1), add="+")
        self.bind("<Up>", lambda event: self._on_key_position(event, -1), add="+")
        self.bind("<Down>", lambda event: self._on_key_position(event, 1), add="+")

    def _vk_down(self, vk: int) -> bool:
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return False

    def _editor_accepts_keyboard(self) -> bool:
        try:
            return bool(self.winfo_exists()) and self.state() != "withdrawn"
        except Exception:
            return False

    def _keyboard_poll_loop(self):
        if not getattr(self, "_keyboard_poll_enabled", False):
            return
        try:
            if self._editor_accepts_keyboard() and not self._key_should_be_ignored():
                states = {
                    "space": self._vk_down(0x20),
                    "left": self._vk_down(0x25),
                    "up": self._vk_down(0x26),
                    "right": self._vk_down(0x27),
                    "down": self._vk_down(0x28),
                }
                prev = getattr(self, "_keyboard_prev", {})

                if states["space"] and not prev.get("space", False):
                    self.toggle_play()

                if states["up"] and not prev.get("up", False):
                    self.move_position(-1)
                if states["down"] and not prev.get("down", False):
                    self.move_position(1)

                direction = 0
                if states["right"] and not states["left"]:
                    direction = 1
                elif states["left"] and not states["right"]:
                    direction = -1

                now = time.time()
                just_pressed = (
                    (direction == 1 and not prev.get("right", False))
                    or (direction == -1 and not prev.get("left", False))
                )
                # Avidemux-artig: kurzer Druck = 1 Frame, Halten = kontrollierter Repeat.
                # Kein Event-Stapel: der Polling-Loop sendet nur in festen Intervallen.
                if direction and (just_pressed or now - getattr(self, "_keyboard_last_step_at", 0.0) >= 0.055):
                    self._keyboard_last_step_at = now
                    self.step_frame(direction)

                if not states["left"] and not states["right"] and (prev.get("left", False) or prev.get("right", False)):
                    self._mpv_set_pause(True)
                    self.after(20, lambda: self._sync_from_mpv(force=True))

                self._keyboard_prev = states
            else:
                self._keyboard_prev = {"space": False, "left": False, "right": False, "up": False, "down": False}
        except Exception:
            pass
        try:
            self.after(20, self._keyboard_poll_loop)
        except Exception:
            pass

    def _key_should_be_ignored(self) -> bool:
        focus = self.focus_get()
        widget_class = focus.winfo_class() if focus is not None else ""
        return widget_class in {"Entry", "TEntry", "Spinbox", "TSpinbox", "Text"}

    def _on_space(self, event=None):
        if self._key_should_be_ignored():
            return
        self.toggle_play()
        return "break"

    def _on_arrow_press(self, event, direction: int):
        if self._key_should_be_ignored():
            return
        # Jeder echte KeyPress bzw. jede OS-Wiederholung wird an mpv/Lua als
        # einzelner Keypress weitergegeben. Das Lua-Script ignoriert Requests,
        # solange der vorherige Frame-Step noch laeuft. Dadurch entsteht keine
        # Warteschlange und beim Loslassen kein Nachlauf.
        self._mpv_command(["keypress", "RIGHT" if direction > 0 else "LEFT"])
        self.after(25, lambda: self._sync_from_mpv(force=True))
        return "break"

    def _on_arrow_release(self, event, direction: int):
        if self._key_should_be_ignored():
            return
        self._mpv_command(["keyup", "RIGHT" if direction > 0 else "LEFT"])
        self.after(25, lambda: self._sync_from_mpv(force=True))
        return "break"

    def _on_key_step(self, event, delta: int):
        if self._key_should_be_ignored():
            return
        self._mpv_command(["keypress", "RIGHT" if delta > 0 else "LEFT"])
        self.after(40, lambda: self._sync_from_mpv(force=True))
        return "break"

    def _on_key_position(self, event, delta: int):
        if self._key_should_be_ignored():
            return
        self.move_position(delta)
        return "break"

    # ------------------------------------------------------------------
    # data helpers
    # ------------------------------------------------------------------
    def _load_media_tracks_for_settings(self):
        try:
            audio, _subs = get_media_streams(self.source)
            values = ["Standard-Audio", "Keine Audioausgabe"]
            for order, stream in enumerate(audio, start=1):
                label = f"Audio{order}  #{stream.index} {stream.language} {stream.codec_name}"
                if stream.title:
                    label += f" – {stream.title}"
                values.append(label)
            self._audio_values = values
        except Exception:
            self._audio_values = ["Standard-Audio", "Keine Audioausgabe"]

    def _format_seconds(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds - h * 3600 - m * 60
        if abs(s - round(s)) < 0.001:
            return f"{h:02d}:{m:02d}:{int(round(s)):02d}"
        return f"{h:02d}:{m:02d}:{s:06.3f}"

    def _parse_time(self, value: str) -> float:
        value = (value or "").strip().replace(",", ".")
        if not value:
            return 0.0
        if ":" not in value:
            return float(value)
        parts = [float(part) for part in value.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        raise RuntimeError("Ungültige Zeitangabe")

    def _position_for_frame(self, frame_no: int) -> str:
        frame_no = max(1, min(int(frame_no), self.total_frames))
        return INDEX_TO_POSITION[int(self.states[frame_no - 1])]

    def _step_frames(self) -> int:
        try:
            return max(1, int(float(self.step_frames_var.get())))
        except Exception:
            return 1

    def _frame_width(self) -> int:
        try:
            return max(1, min(50, int(float(self.frame_width_var.get()))))
        except Exception:
            return 5

    def _frame_alpha(self) -> float:
        try:
            return max(0.0, min(100.0, float(self.frame_alpha_var.get()))) / 100.0
        except Exception:
            return 1.0

    def _preview_width(self) -> int:
        try:
            return max(320, min(3840, int(float(self.preview_width_var.get()))))
        except Exception:
            return 1280

    # ------------------------------------------------------------------
    # playback/edit controls
    # ------------------------------------------------------------------
    def _frame_from_mpv(self) -> Optional[int]:
        """Ermittelt möglichst den wirklich angezeigten Frame aus mpv.

        estimated-frame-number ist 0-basiert. Falls der mpv-Build diese
        Property nicht liefert, nutzen wir time-pos als Fallback.
        """
        if not self._mpv_ready:
            return None
        value = self._mpv_get_property("estimated-frame-number", None)
        try:
            if value is not None:
                return max(1, min(int(value) + 1, self.total_frames))
        except Exception:
            pass
        value = self._mpv_get_property("time-pos", None)
        try:
            if value is not None:
                return max(1, min(int(round(float(value) * max(self.info.fps, 1))) + 1, self.total_frames))
        except Exception:
            pass
        return None

    def _sync_from_mpv(self, force: bool = False):
        if not self._mpv_ready:
            return
        frame = self._frame_from_mpv()
        if frame is not None and (force or frame != self.current_frame):
            self._set_frame_state(frame, seek=False)
        paused = self._mpv_get_property("pause", None)
        if paused is not None:
            new_playing = not bool(paused)
            if new_playing != self.playing:
                self.playing = new_playing
                self.play_button.configure(text="⏸" if self.playing else "▶")

    def _set_frame_state(self, frame_no: int, seek: bool = True):
        frame_no = max(1, min(int(frame_no), self.total_frames))
        self.current_frame = frame_no
        pos = self._position_for_frame(frame_no)
        self.position_var.set(pos)
        self.current_frame_var.set(str(frame_no))
        self.current_time_var.set(self._format_seconds((frame_no - 1) / max(self.info.fps, 1)))
        if not self._scrubbing:
            self._scrub_var.set(frame_no)
        self._update_mpv_overlay_if_needed(frame_no)
        if seek and self._mpv_ready:
            seconds = (frame_no - 1) / max(self.info.fps, 1)
            self._mpv_command(["seek", seconds, "absolute+exact"])
        self.status_var.set(f"Frame {frame_no} / {self.total_frames} | CSV-Position: {pos}")

    def apply_position_to_current_frame(self):
        # Die vom Benutzer gewählte Position zuerst merken; _sync_from_mpv()
        # würde sonst position_var auf die bisherige CSV-Position zurücksetzen.
        pos = self.position_var.get()
        self._sync_from_mpv(force=True)
        if pos in POSITION_TO_INDEX:
            self.position_var.set(pos)
            self.states[self.current_frame - 1] = POSITION_TO_INDEX[pos]
            self._last_overlay_position = None
            self._reload_ass_overlay()
            self._set_frame_state(self.current_frame, seek=False)

    def move_position(self, delta: int):
        pos = self.position_var.get()
        try:
            idx = list(POSITIONS).index(pos)
        except ValueError:
            idx = list(POSITIONS).index("center")
        idx = max(0, min(len(POSITIONS) - 1, idx + int(delta)))
        self.position_var.set(POSITIONS[idx])
        self.apply_position_to_current_frame()

    def step_frame(self, delta: int):
        self.playing = False
        self.play_button.configure(text="▶")
        self._mpv_set_pause(True)
        self._sync_from_mpv(force=True)
        target = max(1, min(self.current_frame + int(delta), self.total_frames))
        if abs(int(delta)) == 1 and self._mpv_ready:
            # mpv führt den eigentlichen Frame-Step aus; danach lesen wir den
            # echten Frame zurück, statt nur lokal zu raten.
            self._mpv_command(["frame-step"] if delta > 0 else ["frame-back-step"])
            self.after(35, lambda: self._sync_from_mpv(force=True))
        else:
            self._set_frame_state(target, seek=True)
            self.after(50, lambda: self._sync_from_mpv(force=True))

    def toggle_play(self):
        if not self._mpv_ready:
            return
        # Vor dem Umschalten erst auf den tatsächlich angezeigten mpv-Frame synchronisieren.
        self._sync_from_mpv(force=True)
        self.playing = not self.playing
        self.play_button.configure(text="⏸" if self.playing else "▶")
        self._mpv_set_pause(not self.playing)
        if not self.playing:
            # Nach dem Pausieren nochmals synchronisieren, damit der Frame, den man
            # danach als Start/Ende setzt, exakt der mpv-Position entspricht.
            self.after(40, lambda: self._sync_from_mpv(force=True))

    def _ui_loop(self):
        try:
            # v9: mpv ist die Quelle der Wahrheit. Dadurch stimmen Frame-Anzeige,
            # Leertaste, mpv-eigene Frame-Steps und CSV-Schreibposition zusammen.
            self._sync_from_mpv()
            self._update_visual_overlays()
            if self.current_frame >= self.total_frames and self.playing:
                self.playing = False
                self.play_button.configure(text="▶")
                self._mpv_set_pause(True)
        finally:
            self.after(40, self._ui_loop)

    def jump_to_frame_entry(self):
        try:
            self.playing = False
            self.play_button.configure(text="▶")
            self._mpv_set_pause(True)
            self._set_frame_state(int(self.current_frame_var.get()), seek=True)
        except Exception as exc:
            messagebox.showerror("Springen nicht möglich", str(exc))

    def jump_to_time_entry(self):
        try:
            seconds = self._parse_time(self.current_time_var.get())
            frame = int(round(seconds * max(self.info.fps, 1))) + 1
            self.playing = False
            self.play_button.configure(text="▶")
            self._mpv_set_pause(True)
            self._set_frame_state(frame, seek=True)
        except Exception as exc:
            messagebox.showerror("Springen nicht möglich", str(exc))

    def _start_scrub(self, _event=None):
        self._scrubbing = True
        self.playing = False
        self.play_button.configure(text="▶")
        self._mpv_set_pause(True)

    def _do_scrub(self, _event=None):
        try:
            self._set_frame_state(int(float(self._scrub_var.get())), seek=False)
        except Exception:
            pass

    def _end_scrub(self, _event=None):
        self._scrubbing = False
        try:
            self._set_frame_state(int(float(self._scrub_var.get())), seek=True)
        except Exception:
            pass

    def mark_or_apply_range(self):
        # Wichtig: direkt vor dem Schreiben die mpv-Position zurücklesen.
        # Sonst kann bei Wiedergabe/Pause ein um einige Frames verschobener
        # lokaler Zähler in die CSV geschrieben werden.
        self._sync_from_mpv(force=True)
        pos = self.position_var.get()
        if pos not in POSITION_TO_INDEX:
            return
        if self._pending_range_start is None:
            self._pending_range_start = self.current_frame
            self._pending_range_position = pos
            self.last_mark_var.set(f"Start gesetzt: Frame {self.current_frame} | {pos}")
            return
        start = int(self._pending_range_start)
        end = int(self.current_frame)
        if end < start:
            start, end = end, start
        position = self._pending_range_position or pos
        self.states[start - 1:end] = POSITION_TO_INDEX[position]
        self.last_mark_var.set(f"Gesetzt: Frame {start}–{end} | {position}")
        self._pending_range_start = None
        self._pending_range_position = None
        self._last_overlay_position = None
        self._reload_ass_overlay()
        self._set_frame_state(self.current_frame, seek=False)

    def save_csv(self):
        try:
            self._sync_from_mpv(force=True)
            write_csv(self.csv_path, self.states)
            self.status_var.set(f"CSV gespeichert: {self.csv_path}")
            messagebox.showinfo("Gespeichert", f"CSV gespeichert:\n{self.csv_path}")
        except Exception as exc:
            messagebox.showerror("Speichern fehlgeschlagen", str(exc))

    def open_settings(self):
        win = tk.Toplevel(self)
        win.title(f"CSV-Editor Einstellungen {CSV_EDITOR_VERSION}")
        win.transient(self)
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        ttk.Label(frm, text="Video-Fenster-Breite").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Spinbox(frm, from_=320, to=3840, increment=80, textvariable=self.preview_width_var, width=10).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(frm, text="Audio-Spur für Wiedergabe").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(frm, textvariable=self.audio_track_var, values=getattr(self, "_audio_values", ["Standard-Audio", "Keine Audioausgabe"]), state="readonly", width=38).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(frm, text="Rahmenbreite").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Spinbox(frm, from_=1, to=50, increment=1, textvariable=self.frame_width_var, width=10).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(frm, text="Rahmen-Deckkraft %").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Spinbox(frm, from_=0, to=100, increment=5, textvariable=self.frame_alpha_var, width=10).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(frm, text="Spultasten-Schrittweite (Frames)").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Spinbox(frm, from_=1, to=10000, increment=1, textvariable=self.step_frames_var, width=10).grid(row=4, column=1, sticky="ew", pady=4)
        ttk.Label(
            frm,
            text="v15 nutzt fenstergebundene Tastatursteuerung: HomeCinemaCrop reagiert nur, wenn es aktiv ist; der CSV-Editor nur, wenn er aktiv ist. Im Videobild uebernimmt mpv die Tasten.",
            wraplength=460,
            style="Subtitle.TLabel",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 4))

        def apply_settings():
            self._apply_audio_setting_live()
            self._last_overlay_position = None
            self._reload_ass_overlay()
            self._update_mpv_overlay_if_needed(self.current_frame)
            win.destroy()

        ttk.Button(frm, text="Übernehmen", command=apply_settings).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def close_editor(self):
        self.playing = False
        # Kein grab_set in v15: HomeCinemaCrop bleibt parallel bedienbar.
        try:
            self._mpv_command(["quit"])
        except Exception:
            pass
        if self._mpv_process is not None:
            try:
                self._mpv_process.terminate()
            except Exception:
                pass
        if hasattr(self, "_mpv_error_handle"):
            try:
                self._mpv_error_handle.close()
            except Exception:
                pass
        if self._ass_overlay_path is not None:
            try:
                self._ass_overlay_path.unlink(missing_ok=True)
            except Exception:
                pass
        if hasattr(self, "_mpv_input_conf_path"):
            try:
                self._mpv_input_conf_path.unlink(missing_ok=True)
            except Exception:
                pass
        if hasattr(self, "_mpv_lua_script_path"):
            try:
                self._mpv_lua_script_path.unlink(missing_ok=True)
            except Exception:
                pass
        if hasattr(self, "_ipc_path") and not platform.system().lower().startswith("win"):
            try:
                Path(self._ipc_path).unlink(missing_ok=True)
            except Exception:
                pass
        self.destroy()


def open_csv_editor(master, source: Path, csv_path: Path, precrop: PreCrop):
    if not Path(source).is_file():
        raise RuntimeError("Keine gültige Quelle geladen.")
    if not Path(csv_path).is_file():
        raise RuntimeError("Keine gültige CSV geladen.")
    win = CsvEditorWindow(master, Path(source), Path(csv_path), precrop)
    win.focus_force()
    return win
