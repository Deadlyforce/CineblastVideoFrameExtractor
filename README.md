<div align="center">

# Cineblast VFE

**HDR-aware video frame extraction, contact-sheet browsing and stills
workflow — built for film critics, editors and archivists.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Qt](https://img.shields.io/badge/UI-PySide6-41CD52?logo=qt&logoColor=white)
![ffmpeg](https://img.shields.io/badge/engine-ffmpeg-007808)
![Support](https://img.shields.io/badge/Support-Tipeee-orange)

A darkroom-styled desktop tool that turns any video into a browsable,
markable contact sheet of evenly spaced stills — with a proper
HDR → SDR pipeline.

[Why this exists](#why-this-exists) · [Features](#features) ·
[Installation](#installation) · [Usage](#usage) ·
[Shortcuts](#keyboard-shortcuts) · [Support](#support-the-project)

</div>

---

## Why this exists

Cineblast VFE (“Video Frame Extractor”) is the in-house tool behind the
[Cineblast YouTube channel](https://www.youtube.com/@cineblast)’s film
critiques: it extracts clean, color-faithful stills from modern masters
(including HDR10/HLG sources) so frames can be studied, marked and
dropped into reviews.

## Features

- **Capture plans** — extract by *number of images* (5–1000) or by
  *time interval*, with a live plan summary (“500 images, one every ~13 s”).
- **HDR-aware pipeline** — automatic HDR10/HLG detection and HDR → SDR
  tone mapping (**Hable / Mobius / Reinhard**) via `zscale`, with a
  graceful fallback cascade when filters are unavailable.
- **Black-frame filtering** — adjustable luminance threshold; excluded
  frames are listed in an inspector with 150 px thumbnails and an
  800 px lightbox.
- **Fast parallel extraction** — 3 concurrent ffmpeg workers, ordered
  progress with ETA, cancel, and one-click retry of failed frames.
- **Virtualized thumbnail grid** — smooth with hundreds of frames;
  click / Ctrl / Shift / rubber-band selection, full keyboard navigation.
- **Marking workflow** — configurable mark key, marks persisted
  across sessions.
- **File management** — delete to recycle bin, empty extraction folder,
  move selection to a working folder with continuous generic renaming
  (`name_0001.jpg`, `name_0002.jpg`, …).
- **Persistent configuration** — `VFE_Config.json`, schema-compatible
  with the legacy Tkinter version (archived in this repo).
- **Darkroom UI** — warm charcoal surfaces, amber accent, Segoe UI +
  Consolas; inspired by DaVinci Resolve and Adobe Lightroom.

## Screenshots

<!-- TODO: add docs/screenshot_main.png (main window with HDR video loaded) -->

## Requirements

| Component | Version | Notes |
|---|---|---|
| OS | Windows 10 / 11 | tested platform |
| Python | 3.10+ | developed on 3.12 |
| ffmpeg | any recent build | a **full build with `zscale`** (e.g. gyan.dev or BtbN) is recommended for HDR tone mapping; the app degrades gracefully without it |

## Installation

1. **Install Python** from python.org (tick *“Add Python to PATH”*).

2. **Install ffmpeg** and add it to your `PATH`, e.g.:

   ```powershell
   winget install Gyan.FFmpeg
   # or: choco install ffmpeg
   ffmpeg -version   # sanity check
   ```

3. **Get the code**:

   ```powershell
   git clone https://github.com/<your-username>/cineblast-vfe.git
   cd cineblast-vfe
   ```

4. **Create a virtual environment** (recommended) and install dependencies:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. **Run**:

   ```powershell
   python vfe_qt/main.py
   ```

   or double-click `Lancer Cineblast VFE (Qt).bat`
   (use `Lancer Cineblast VFE (Qt) - debug.bat` for a console with logs).

`VFE_Config.json` is created with sane defaults on first launch if it
does not exist.

## Usage

- **Left panel** — load a video, choose extraction/working folders,
  capture mode, black-frame filter, tone mapping (HDR sources only).
- **Center** — the thumbnail grid; the top bar shows counts, filters
  and display options (thumbnail size, columns).
- **Right panel** — preview inspector (image, filename, timecode,
  resolution, position) and *Open in folder*.
- **Bottom** — status bar (progress messages, black-frame and failure
  reports).

Extract, then browse, mark (`S`), move or delete stills.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `←` `→` `↑` `↓` | move selection |
| `Ctrl+A` | select all |
| `Esc` | clear selection |
| `Del` / `Backspace` | delete selection (recycle bin) |
| `S` (configurable) | mark / unmark selection |

## Project layout

```
cineblast-vfe/
├── vfe_qt/             # Qt application
│   ├── main.py         #   main window & application logic
│   ├── theme.py        #   design tokens + QSS stylesheet
│   ├── grid_qt.py      #   virtualized thumbnail grid
│   ├── widgets.py      #   custom widgets (switch, path buttons…)
│   └── make_icon.py    #   generates app_icon.png
├── vfe_config.py       # configuration schema & persistence
├── vfe_ffmpeg.py       # ffmpeg command builders & HDR cascade
├── vfe_plan.py         # capture plan computation
├── vfe_utils.py        # timecodes, filenames, black-frame detection
├── archive_tkinter/    # legacy Tkinter application (archived)
├── VFE_Config.json     # user configuration (not committed)
└── VFE_Log.txt         # rotating log, Qt lines prefixed [Qt]
```

## Known limitations

- No OpenCV fallback when ffmpeg is missing (a clear error is shown).
- Windows is the only tested platform.

## Support the project

Cineblast VFE is developed alongside the
[Cineblast](https://www.youtube.com/@cineblast) YouTube channel, where
it powers the frame-by-frame film critiques. If you find it useful,
you can follow the channel and support development on
[Tipeee](https://fr.tipeee.com/cineblast).

## License

Personal project — © 2026 Cineblast. Released under the MIT License.

<!-- To make it open source, delete the line above and add an MIT
     LICENSE file instead. -->

---

*Not affiliated with ffmpeg or the Qt Project. Comes as-is, without
warranty of any kind.*