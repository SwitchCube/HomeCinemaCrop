from pathlib import Path

content = r"""# HomeCinemaCrop

HomeCinemaCrop is a Python-based GUI application designed to convert IMAX, Open Matte and 4:3 video sources into dynamic 16:9 home cinema presentations.

Unlike traditional static cropping, HomeCinemaCrop uses a CSV-based workflow that allows the crop position to change throughout the movie. This makes it possible to preserve important image content while creating a constant 16:9 presentation.

The project was originally developed for Zack Snyder's Justice League, but can be used with any IMAX, Open Matte or 4:3 source.

---

# Main Features

## Dynamic 16:9 Reframing

Instead of using a fixed crop, HomeCinemaCrop supports dynamic vertical positioning:

- up
- half-up
- center
- half-down
- down

This allows different scenes to use different crop positions while maintaining a constant 16:9 output.

---

## Manual Pre-Crop

Optional manual cropping similar to HandBrake.

Useful for:

- Removing black bars
- Converting letterboxed sources into true Open Matte sources
- Preparing non-standard sources

---

## Preview System

Built-in preview tools allow verification before the final render.

Features:

- Frame-based preview
- Percentage-based preview
- Frame stepping
- Keyboard navigation
- Time ↔ Frame conversion
- Jump to specific frame
- Jump to start/end markers
- Preview video generation
- Visual crop-frame preview

---

## CSV Editor

HomeCinemaCrop includes a dedicated CSV Editor.

The editor automatically receives:

- Source video
- Loaded CSV file
- Pre-crop settings

Features:

- Video playback
- Frame-accurate navigation
- Direct CSV editing
- Scene-based crop adjustments
- Crop-frame overlay
- Start/end scene workflow
- Keyboard shortcuts

Supported crop positions:

- up
- half-up
- center
- half-down
- down

---

## Audio & Subtitle Selection

Choose exactly which tracks should be copied into the final output.

Features:

- Select audio tracks
- Select subtitle tracks
- Copy or remove chapters
- Copy or remove metadata

No re-encoding is performed for audio or subtitles.

---

## HDR10 & UHD Support

Supports HDR workflows including:

- HDR10
- BT.2020
- PQ transfer characteristics
- Display P3 mastering metadata
- MaxCLL
- MaxFALL
- 10-bit video

---

## Encoder Support

### CPU Encoding

- H.265 / x265
- Adjustable presets
- Adjustable CRF values

### GPU Encoding

- NVIDIA NVENC
- HDR10 support
- Faster rendering

---

## Rendering Features

- Preview rendering
- Final rendering
- Pause / Resume
- Cancel rendering
- Progress information
- ETA calculation
- Automatic shutdown after render

---

# Workflow

## Basic Workflow

1. Load source video
2. Apply optional pre-crop
3. Create or load CSV data
4. Adjust crop positions
5. Verify using Preview
6. Fine-tune with CSV Editor (optional)
7. Select audio and subtitle tracks
8. Render final output

---

# CSV Format

Example:

```csv
frame;position
1;center
2;center
3;half-up
4;up
5;center