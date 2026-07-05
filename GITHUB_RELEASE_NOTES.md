# MuxCls v1.3.1

Version tag suggestion: `v1.3.1`

MuxCls v1.3.1 fixes a stream-selection bug, splits the codebase into a maintainable
package, and removes the `MuxCls.cmd` shim and the PATH uninstaller in favor of the
PowerShell launcher and manual PATH removal.

MuxCls still uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video,
audio, or subtitles.

## Fixed

- Fixed audio stream selection being skipped when a file had a single audio language but
  multiple audio tracks (for example, a main track plus a commentary track). Selection is
  now skipped only when no file has more than one audio track; multi-track files always
  prompt for audio selection.

## Changed

- Updated runtime version to `1.3.1`.
- Split the single-file `MuxCls.py` into the `muxcls/` package, organized by responsibility
  (constants, colors, logging, models, text/UI helpers, prompts, media, mux logic, output,
  reporting, selection, processing, and app). `MuxCls.py` is now a thin entry point that
  imports and runs `muxcls.app.main`. Behavior is unchanged.

## Removed

- Removed the `MuxCls.cmd` command shim. Use the `run.ps1` PowerShell launcher instead.
- Removed `Uninstall-MuxClsCommand.ps1`. To remove MuxCls from `PATH`, delete the project
  folder from the user `PATH` in Windows Environment Variables.

## Breaking Changes

- The `MuxCls` command installed via `Install-MuxClsCommand.ps1` (which relied on
  `MuxCls.cmd`) no longer resolves after installing. Run `run.ps1` by name instead once the
  project folder is on `PATH`, or run `.\run.ps1` from the project folder directly.

## Requirements

- Windows with Windows PowerShell or PowerShell 7 for the included launcher.
- Python 3 available as `py -3` or `python`.
- FFmpeg installed and available in `PATH` as both `ffmpeg` and `ffprobe`.
- Robocopy available in `PATH` for unchanged-video and non-video file copy operations. Robocopy is included with Windows.
- No external Python packages are required.

## Safety Notes

- MuxCls executes `ffprobe`, `ffmpeg`, and `robocopy` from your system `PATH`.
- MuxCls creates output files and folders based on your selections.
- Existing output files are not overwritten by default; MuxCls uses safe output names and FFmpeg is run with no-overwrite mode.
- If overwrite is enabled, FFmpeg may replace matching output files.
- If non-video copying is enabled, non-video files are copied into the output folder using the same relative paths.
- Optional metadata edits apply only to kept output streams. Source files are not modified.
- If your selected audio rule matches no audio stream in a file, that file is skipped and counted as `No audio match`.
- Local logs may include file paths, command lines, system information, warnings, captured command output, and file-processing results. Do not publish local `Logs` files.

## Upgrade Notes

- Existing users should switch from `MuxCls.cmd` to `.\run.ps1` (or `run.ps1` if the
  project folder is on `PATH`).
- If you previously ran `Install-MuxClsCommand.ps1`, no action is needed; the folder is
  still on `PATH`, only the command name changed from `MuxCls` to `run.ps1`.
- No changes to output behavior, file formats, or configuration are required.

## License and Attribution

MIT License

Copyright (c) 2026 Kiaro Sama

MuxCls was created by Kiaro Sama.

Original author: Kiaro Sama  
GitHub: https://github.com/KiaroSama  
Original repository: https://github.com/KiaroSama/MuxCls  
License: MIT License

Anyone who copies, modifies, republishes, redistributes, or includes substantial parts of this project must preserve the original copyright and license notice.
