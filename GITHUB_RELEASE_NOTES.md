# MuxCls v1.1.0

Version tag suggestion: `v1.1.0`

MuxCls v1.1.0 focuses on safer remux output, stronger stream-selection validation, cleaner Windows launchers, and release-ready documentation.

MuxCls still uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video, audio, or subtitles.

## Added

- Added `Uninstall-MuxClsCommand.ps1` to remove the project folder from the current user's `PATH`.
- Added PowerShell 7 preference in `MuxCls.cmd`, with fallback to Windows PowerShell.
- Added periodic `still remuxing...` console updates during long FFmpeg runs.
- Added non-video extension hints when an input path contains files but no supported videos.
- Added explicit `q` support to menu navigation hints.

## Changed

- Updated runtime version to `1.1.0`.
- Advanced subtitle selection now defaults to keeping all subtitles.
- Output folder prompts now reject accidental yes/no answers and media-file-like paths such as `output.mkv`.
- Relative output folders now show their resolved absolute path and require confirmation.
- FFmpeg output is buffered to temporary files for logging while the console remains concise.
- Stream language coloring is now deterministic across languages instead of hard-coding one language.
- Unique stream summaries now preserve displayed title capitalization.
- Metadata guidance in the CLI now reads as an explanatory note instead of a fixed state.
- Verify mode now respects intentional no-audio output when audio removal was selected.

## Fixed

- Fixed a crash when `ffprobe` returns `{"streams": null}` or malformed stream entries.
- Fixed silent video-only output when an audio selection rule matches no audio stream; affected files are now skipped and counted as `No audio match`.
- Fixed multiple kept audio or subtitle streams retaining `default` disposition flags; only the first kept stream is marked default.
- Fixed folder-mode output path collision handling so file uniqueness and self-collision checks apply consistently.
- Fixed empty language, title, and index selections in advanced rules by re-prompting for at least one parsed value.
- Fixed misleading output suffixes for empty or invalid selection rules.
- Fixed invalid filename sanitization for names made only of invalid filename characters.
- Fixed ambiguous compact language suffix truncation by using `+...`.
- Fixed negative elapsed time handling by logging a warning.
- Fixed prompt formatting so labels and navigation hints render with a separator.
- Fixed ANSI color setup on Windows by using console mode APIs instead of a shell side effect.
- Fixed PATH installer robustness with a user PATH length check and environment-change broadcast.

## Removed

- Removed unused internal helper functions.

## Breaking Changes

- None.

## Requirements

- Windows with Windows PowerShell or PowerShell 7 for the included launchers.
- Python 3 available as `py -3` or `python`.
- FFmpeg installed and available in `PATH` as both `ffmpeg` and `ffprobe`.
- No external Python packages are required.

## Safety Notes

- MuxCls executes `ffprobe` and `ffmpeg` from your system `PATH`.
- MuxCls creates output files and folders based on your selections.
- Existing output files are not overwritten by default; MuxCls uses safe output names and FFmpeg is run with no-overwrite mode.
- If overwrite is enabled, FFmpeg may replace matching output files.
- If your selected audio rule matches no audio stream in a file, that file is skipped and counted as `No audio match`.
- `Install-MuxClsCommand.ps1` modifies the current user's `PATH` environment variable by adding the project folder.
- `Uninstall-MuxClsCommand.ps1` removes the project folder from the current user's `PATH`.
- Local logs may include file paths, command lines, system information, warnings, and FFmpeg output. Do not publish local `Logs` files.

## Upgrade Notes

- Existing users can pull the new version and keep using `.\run.ps1`, `MuxCls.cmd`, or the installed `MuxCls` command.
- If the command was installed previously, run `.\Install-MuxClsCommand.ps1` again only if the project folder changed.
- Use `.\Uninstall-MuxClsCommand.ps1` if you want to remove the command from the user `PATH`.

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
| `MuxCls.cmd` | Windows command shim that prefers PowerShell 7 and falls back to Windows PowerShell. |
| `Install-MuxClsCommand.ps1` | Adds the project folder to the current user's `PATH`. |
| `Uninstall-MuxClsCommand.ps1` | Removes the project folder from the current user's `PATH`. |
| `README.md` | Project documentation. |
| `.gitignore` | Excludes logs, caches, local notes, temporary files, secrets, and generated output. |
| `LICENSE` | MIT License. |
| `ATTRIBUTION.md` | Standalone attribution notice for reuse and redistribution. |
| `CHANGELOG.md` | Versioned project changelog. |

## License and Attribution

MIT License

Copyright (c) 2026 Kiaro Sama

MuxCls was created by Kiaro Sama.

Original author: Kiaro Sama  
GitHub: https://github.com/KiaroSama  
Original repository: https://github.com/KiaroSama/MuxCls  
License: MIT License

Anyone who copies, modifies, republishes, redistributes, or includes substantial parts of this project must preserve the original copyright and license notice.
