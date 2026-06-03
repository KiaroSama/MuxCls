# MuxCls v1.3.0

Version tag suggestion: `v1.3.0`

MuxCls v1.3.0 is a minor release focused on clearer long-copy progress and more complete processing logs for remuxed, copied, skipped, and failed files.

MuxCls still uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video, audio, or subtitles.

## Added

- Added live elapsed progress while unchanged video files are copied with `robocopy`.
- Added structured per-file `RESULT` log lines with action, status, input path, output path, detail, return code, and elapsed time.
- Added final `SUMMARY_RESULT` log lines so the end of each run contains a compact per-file outcome summary.

## Changed

- Updated runtime version to `1.3.0`.
- Unchanged-video copy operations now use `robocopy /J`.

## Fixed

- Fixed unchanged-video copy operations appearing idle during longer copy runs.
- Improved run logs so remuxed, copied unchanged, skipped, no-audio-match, and failed file outcomes are easier to audit.

## Removed

- No user-facing features were removed in this release.

## Breaking Changes

- No breaking changes.

## Requirements

- Windows with Windows PowerShell or PowerShell 7 for the included launchers.
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

- Existing users can pull the new version and keep using `.\run.ps1`, `MuxCls.cmd`, or the installed `MuxCls` command.
- Review the local log after a run if you need to audit which files were remuxed, copied unchanged, skipped, or failed.

## License and Attribution

MIT License

Copyright (c) 2026 Kiaro Sama

MuxCls was created by Kiaro Sama.

Original author: Kiaro Sama  
GitHub: https://github.com/KiaroSama  
Original repository: https://github.com/KiaroSama/MuxCls  
License: MIT License

Anyone who copies, modifies, republishes, redistributes, or includes substantial parts of this project must preserve the original copyright and license notice.
