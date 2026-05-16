# HomeCinemaCrop

HomeCinemaCrop is a Python GUI tool designed to convert IMAX / 4:3 video sources into dynamic 16:9 home cinema versions.

The project was originally created for Zack Snyder's Justice League to create a more controlled and cinematic 16:9 presentation from the original IMAX format.

Instead of applying a static crop, the tool allows scene-by-scene crop positioning (`up`, `center`, `down`) using a CSV-based workflow. This makes it possible to preserve important image content during conversion.

---

# Features

- Convert IMAX / 4:3 videos into 16:9
- Dynamic crop positioning per frame or scene
- GUI-based workflow
- Optional manual pre-crop (similar to HandBrake)
- Preview rendering before final export
- Final render with FFmpeg
- HDR / 10-Bit aware encoding support
- Audio, subtitles, chapters and metadata passthrough
- Upscaling support (including UHD 3840×2160)
- Adjustable encoder settings
- Pause / resume rendering
- CSV import/export system

---

# Workflow

1. Load source video
2. Optional: apply manual pre-crop
3. Create or load CSV crop data
4. Preview the result
5. Render final 16:9 output

---

# Requirements

## Required Software

- Python 3.10+
- FFmpeg
- FFprobe

FFmpeg and FFprobe must be available in your system PATH.

---

# Required Python Libraries

Install with:

```bash
pip install opencv-python numpy pillow
```

---

# Start the Program

## Windows

```bash
python HomeCinemaCrop_v19.py
```

or use:

```bash
start_HomeCinemaCrop_v19.bat
```

---

## macOS / Linux

```bash
python3 HomeCinemaCrop_v19.py
```

or use:

```bash
chmod +x start_HomeCinemaCrop_v19_mac.sh
./start_HomeCinemaCrop_v19_mac.sh
```

---

# CSV System

The CSV controls the vertical crop position for every frame.

Example:

```csv
frame;position
1;center
2;center
3;up
4;down
```

Allowed positions:

- `up`
- `center`
- `down`

---

# Recommended Settings

## High Quality HDR/UHD

- Codec: `libx265`
- Preset: `slower` or `veryslow`
- CRF: `10–12`
- Pixel Format: `10 Bit`
- Scaler: `lanczos`

---

# Purpose of the Project

Many IMAX releases are presented in 4:3 or open matte formats that do not always fit typical home cinema setups.

This tool was created to generate a more cinematic and controlled 16:9 presentation while keeping important image composition intact.

---

# Technologies Used

- Python
- Tkinter
- FFmpeg
- OpenCV
- NumPy
- Pillow

---

# Disclaimer

This project is intended for personal home cinema use and preservation workflows.

Please respect copyright laws and only use video material you legally own.