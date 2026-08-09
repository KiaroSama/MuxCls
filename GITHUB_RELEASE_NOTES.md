# MuxCls v1.4.0

Version tag suggestion: `v1.4.0`

MuxCls v1.4.0 fixes a set of stream-handling and process-control bugs, adds per-file progress
reporting, and runs on Linux and macOS as well as Windows.

MuxCls still uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video,
audio, or subtitles.

## Fixed

- Default track flags are now preserved. MuxCls used to force the first kept audio and
  subtitle stream to be the default and clear the rest, which moved the default onto a track
  the source never marked, and triggered a full remux of files that needed none purely to
  apply that normalization.
- A file with no audio stream is no longer processed silently when audio was requested. Any
  audio mode other than "remove all audio" now records `No audio match` for such a file.
- "Remove all audio" is reachable again for sets with a single audio track. The audio menu is
  now skipped only when nothing in the scan has audio at all.
- In folder mode the output folder can no longer be the input folder or a folder inside it.
  Such output was rescanned as input on the next run.
- Files that `ffprobe` cannot read are no longer discarded silently. They are reported before
  rule selection, need an explicit confirmation to continue past, and are counted in the run
  totals, the log, and the final summary.
- A file with a supported video extension but no video stream is now a validation failure
  before any copy or remux, instead of a warning followed by a "successful" output.
- FFmpeg and copy operations can be interrupted. A timeout, `Ctrl+C`, or an unexpected error
  terminates the child process and kills it if it does not stop, and an incomplete output file
  is removed rather than reported as success.
- Overwrite is consistent in folder mode: it reuses the output folder you asked for instead of
  creating a numbered sibling, and it actually replaces a destination that would otherwise be
  skipped. Without overwrite the numeric-suffix behavior is unchanged.

## Added

- Each file prints its own size change as soon as it finishes, in addition to the run total.
- Each file has its own elapsed timer that starts at zero and stops when that file is done,
  shown next to the elapsed time of the whole run.
- Linux and macOS support. Robocopy is used only on Windows; other platforms copy with the
  Python standard library through a temporary file that is renamed into place, so an
  interrupted copy never leaves a partial file or damages the previous output.
- `MUXCLS_DEBUG=1` enables a verbose log with command lines and successful-command output.

## Changed

- Updated runtime version to `1.4.0`.
- Logs are much quieter by default: UTC timestamps, `INFO` level, captured command output only
  for failures, and per-file paths relative to the run roots.
- File copy backends moved into `muxcls/copying.py`, separating run orchestration from
  platform-specific copying.
- The test suite grew to 60 tests and CI runs it on `windows-latest` and `ubuntu-latest`.

## Requirements

- Python 3 available as `py -3` or `python`.
- FFmpeg installed and available in `PATH` as both `ffmpeg` and `ffprobe`.
- No external Python packages are required.

Windows-only extras:

- Windows PowerShell or PowerShell 7 for the included launcher.
- Robocopy, which ships with Windows, is used for unchanged-video and non-video file copies.

On Linux and macOS, run `python MuxCls.py`.

## Safety Notes

- MuxCls executes `ffprobe` and `ffmpeg` from your system `PATH`, plus `robocopy` on Windows.
- MuxCls creates output files and folders based on your selections.
- Existing output files are not overwritten by default; MuxCls uses safe output names and FFmpeg is run with no-overwrite mode.
- If overwrite is enabled, MuxCls reuses the output folder you asked for and replaces matching files.
- MuxCls refuses an output folder that is inside the input folder when processing a folder.
- If non-video copying is enabled, non-video files are copied into the output folder using the same relative paths.
- Optional metadata edits apply only to kept output streams. Source files are not modified.
- If your selected audio rule matches no audio stream in a file, that file is skipped and counted as `No audio match`.
- Local logs may include file paths, command lines, system information, warnings, captured command output, and file-processing results. Do not publish local `Logs` files.

## Upgrade Notes

- No changes to output behavior, file formats, or configuration are required.
- Output produced by earlier versions may have the default flag on the first kept track rather
  than the track the source marked. Re-running those files with v1.4.0 reproduces the source
  flags.
- On Windows, run `.\run.ps1` from the project folder, or run `.\Install-MuxClsCommand.ps1`
  once to register the PowerShell `MuxCls` command.

## License and Attribution

MIT License

Copyright (c) 2026 Kiaro Sama

MuxCls was created by Kiaro Sama.

Original author: Kiaro Sama  
GitHub: https://github.com/KiaroSama  
Original repository: https://github.com/KiaroSama/MuxCls  
License: MIT License

Anyone who copies, modifies, republishes, redistributes, or includes substantial parts of this project must preserve the original copyright and license notice.
