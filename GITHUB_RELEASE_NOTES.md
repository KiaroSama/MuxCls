# MuxCls v1.2.0

Version tag suggestion: `v1.2.0`

MuxCls v1.2.0 is a minor release focused on output metadata editing, smarter copy/remux decisions, non-video file copy support, richer scan details, and clearer processing summaries.

MuxCls still uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video, audio, or subtitles.

## Added

- Added optional output stream metadata editing for kept audio and subtitle streams.
- Added stream size display in scan reports when FFprobe provides enough data.
- Added optional copying of non-video files to the output folder with the same relative paths.
- Added unchanged-video copying with `robocopy` when selected stream, metadata, attachment, chapter, and overwrite rules do not require remuxing.
- Added processing summary counts for remuxed files, copied unchanged files, extra copied files, skipped files, failed files, elapsed time, and total size difference.
- Added FFmpeg and robocopy command logging for remux and copy actions.

## Changed

- Updated runtime version to `1.2.0`.
- Removed the initial action menu so the normal flow goes directly from scan review to stream selection and processing.
- Processing progress now shows a live global elapsed timer only for the file currently being remuxed.
- Scan reports and unique stream summaries now use ` | ` separators consistently.
- Unknown language tags are displayed as `*uknown` in the interactive UI.
- The PowerShell launcher now starts quietly while preserving ANSI-friendly console behavior.

## Fixed

- Fixed live elapsed progress so it uses total batch time instead of resetting per file.
- Fixed output summary logging so size difference is written to the run log.
- Fixed unnecessary remuxing for files that already match the selected stream and metadata rules.

## Removed

- Removed the interactive scan-only and verify-another-folder action menu from the main workflow.

## Breaking Changes

- The first action menu is no longer shown. MuxCls now proceeds directly from scan review to stream selection and processing.

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
- Local logs may include file paths, command lines, system information, warnings, and FFmpeg output. Do not publish local `Logs` files.

## Upgrade Notes

- Existing users can pull the new version and keep using `.\run.ps1`, `MuxCls.cmd`, or the installed `MuxCls` command.
- Review the new copy prompt if your source folders include non-video files.
- The scan-only and verify-another-folder action menu has been removed from the normal workflow.

## License and Attribution

MIT License

Copyright (c) 2026 Kiaro Sama

MuxCls was created by Kiaro Sama.

Original author: Kiaro Sama  
GitHub: https://github.com/KiaroSama  
Original repository: https://github.com/KiaroSama/MuxCls  
License: MIT License

Anyone who copies, modifies, republishes, redistributes, or includes substantial parts of this project must preserve the original copyright and license notice.
