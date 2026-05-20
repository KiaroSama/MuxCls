# MuxCls v1.0.0

MuxCls v1.0.0 is the first public release of a Windows-friendly FFmpeg helper for scanning video files, reviewing audio and subtitle streams, and remuxing files while keeping only the streams you choose.

MuxCls uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video, audio, or subtitles.

## Features

- Recursively scans folders for `.mkv`, `.mp4`, `.m4v`, `.webm`, `.mov`, and `.avi` files.
- Displays audio and subtitle stream indexes, languages, titles, codecs, channels, and default flags.
- Keeps streams by exact index, language code, title text, all, or none.
- Provides advanced selection prompts with detected audio and subtitle languages.
- Supports drag-and-drop paths in the terminal prompt.
- Preserves folder structure for folder-mode processing.
- Creates selection-based output names such as `SeriesName [JA Audio + EN Subs]`.
- Avoids overwriting existing output by default and adds numeric suffixes when needed.
- Can keep metadata, chapters, stream labels, language tags, and MKV font attachments when selected.
- Writes detailed UTF-8 logs to a local `Logs` folder.
- Includes Windows launchers and an optional user `PATH` installer for the `MuxCls` command.

## Requirements

- Windows with Windows PowerShell or PowerShell 7 for the included launchers.
- Python 3 available as `py -3` or `python`.
- FFmpeg installed and available in `PATH` as both `ffmpeg` and `ffprobe`.
- No external Python packages are required.

## Safety Notes

- MuxCls executes `ffprobe` and `ffmpeg` from your system `PATH`.
- MuxCls creates output files and folders based on your selections.
- Existing output files are skipped by default unless overwrite is enabled.
- If overwrite is enabled, FFmpeg may replace matching output files.
- `Install-MuxClsCommand.ps1` modifies the current user's `PATH` environment variable by adding the project folder.
- Local logs may include file paths, command lines, system information, warnings, and FFmpeg output. Do not publish local `Logs` files.

## Installation / Quick Start

```powershell
git clone https://github.com/KiaroSama/MuxCls.git
cd MuxCls
.\run.ps1
```

Optional command installation:

```powershell
.\Install-MuxClsCommand.ps1
```

Then open a new terminal and run:

```cmd
MuxCls
```

## Included Files

| Path | Purpose |
| --- | --- |
| `MuxCls.py` | Main Python application. |
| `run.ps1` | PowerShell launcher that finds Python and runs `MuxCls.py`. |
| `MuxCls.cmd` | Windows command shim for running the PowerShell launcher. |
| `Install-MuxClsCommand.ps1` | Adds the project folder to the current user's `PATH`. |
| `README.md` | Project documentation. |
| `.gitignore` | Excludes logs, caches, local notes, temporary files, secrets, and generated output. |
| `LICENSE` | MIT License. |
| `ATTRIBUTION.md` | Standalone attribution notice for reuse and redistribution. |

## License

MIT License

Copyright (c) 2026 Kiaro Sama

## Attribution

MuxCls was created by Kiaro Sama.

Original author: Kiaro Sama  
GitHub: https://github.com/KiaroSama  
Original repository: https://github.com/KiaroSama/MuxCls  
License: MIT License

Anyone who copies, modifies, republishes, redistributes, or includes substantial parts of this project must preserve the original copyright and license notice.
