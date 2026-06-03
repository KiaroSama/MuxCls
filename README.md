# MuxCls

MuxCls is a Windows-friendly FFmpeg helper for scanning video files, reviewing audio and subtitle streams, and remuxing files while keeping only the streams you choose.

It uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video, audio, or subtitles. It is designed for interactive cleanup of media libraries where you want to keep selected audio tracks, subtitle tracks, metadata, chapters, and MKV attachments without changing media quality.

## Features

- Recursively scans folders for `.mkv`, `.mp4`, `.m4v`, `.webm`, `.mov`, and `.avi` files.
- Shows audio and subtitle stream indexes, languages, titles, codecs, channels, default flags, and available stream size estimates.
- Lets you keep audio and subtitle streams by exact index, language code, title text, all, or none.
- Lists detected audio and subtitle languages in advanced selection prompts.
- Supports drag-and-drop paths in the terminal prompt.
- Uses `ffprobe` for stream scanning and `ffmpeg -c copy` for remuxing.
- Preserves folder structure when processing folders.
- Can copy non-video files into the output folder with the same relative paths.
- Creates selection-based output names such as `SeriesName [JA Audio + EN Subs]`.
- Avoids overwriting existing output by default and uses numeric suffixes when needed.
- Skips files when the selected audio rule matches no audio stream, instead of creating silent video-only output.
- Copies unchanged video files with `robocopy` when the selected rules do not require remuxing.
- Can preserve metadata, chapters, stream labels, language tags, and MKV font attachments when selected.
- Can edit kept output audio and subtitle stream language/title metadata without changing the source files.
- Reports remuxed, copied, skipped, failed, extra-file copy counts, elapsed time, and total output size difference.
- Shows live elapsed progress while remuxing files or copying unchanged video files.
- Writes detailed UTF-8 run logs to the local `Logs` folder, including per-file action summaries.
- Includes Windows launchers, an optional installer, and an uninstaller for the `MuxCls` command.

## Requirements

- Windows with Windows PowerShell or PowerShell 7 for the included launchers.
- Python 3 available as `py -3` or `python`.
- FFmpeg installed and available in `PATH` as both `ffmpeg` and `ffprobe`.
- Robocopy available in `PATH` for unchanged-video and non-video file copy operations. Robocopy is included with Windows.
- No external Python packages are required.

## Installation

Clone the repository:

```powershell
git clone https://github.com/KiaroSama/MuxCls.git
cd MuxCls
```

Install FFmpeg if it is not already installed, then make sure these commands work from a new terminal:

```powershell
ffmpeg -version
ffprobe -version
```

You can run MuxCls directly from the project folder, or install the folder into your user `PATH`:

```powershell
.\Install-MuxClsCommand.ps1
```

After installing, open a new terminal and run:

```cmd
MuxCls
```

To remove the command from your user `PATH` later:

```powershell
.\Uninstall-MuxClsCommand.ps1
```

## Usage

Run from the project folder:

```powershell
.\run.ps1
```

Or run the command shim:

```cmd
MuxCls.cmd
```

You can also pass a file or folder path directly:

```powershell
.\run.ps1 "D:\Videos\Example.mkv"
```

Typical flow:

1. Enter or drag-and-drop one video file or folder into the input prompt.
2. Review the scan report for audio and subtitle stream indexes, languages, titles, codecs, default flags, and size estimates.
3. Select streams by exact index or with advanced rules by language, title text, or index.
4. Choose whether to keep MKV attachments, metadata, chapters, copy non-video files, edit kept output stream metadata, and overwrite existing output files.
5. Choose an output folder, or press Enter to use the input parent folder.
6. Confirm settings and start processing.

Numbered menus default to option `1`. The stream selection style menu defaults to advanced rules by language, title, or index, and advanced subtitle selection defaults to keeping all subtitles.

Scan reports use ANSI colors for stream fields, centered section headers, and full-width separators when more than one file is scanned. Stream summaries and menu prompts also use ANSI colors when the terminal supports them. Multi-choice menus use a compact numbered layout with the default shown beside the default option.

When advanced selection is used, MuxCls skips unnecessary questions if the scan finds only one audio language or no subtitle streams.

The first input prompt supports `q`, `quit`, or `exit`. Later menus also support `0` for Back.

## Output Behavior

When processing a folder, MuxCls creates a dedicated output root inside the chosen output folder. The output root is based on the original source folder name and a concise selection suffix:

```text
E:\Muxed\SeriesName [JA Audio + EN Subs]\Season 01\Episode 01.mkv
```

It does not dump child files directly into the chosen output base folder.

When processing a single file, pressing Enter at the output folder prompt creates the output next to the input file with a safe selection suffix in the file name, so the original file is not overwritten.

Example suffixes:

- `SeriesName [JA Audio]`
- `SeriesName [EN Audio]`
- `SeriesName [JA Audio + EN Subs]`
- `SeriesName [Audio 1+2 + Subs 3]`
- `SeriesName [Muxed]`

If a generated folder or file already exists, MuxCls adds a numeric suffix such as `(2)`.

If you enter a relative output folder, MuxCls shows the resolved absolute path and asks for confirmation. If an output path looks like a media file name, such as `output.mkv`, MuxCls rejects it and asks for a folder path.

If the selected rules do not require remuxing a video file, MuxCls copies that file unchanged with `robocopy` instead of running FFmpeg. Remux and unchanged-video copy operations show live elapsed progress while the current operation is running. When enabled, non-video files are copied to the output folder with the same relative paths as the source folder.

After processing, the summary shows how many video files were remuxed, copied unchanged, skipped, or failed. It also reports copied non-video file counts, elapsed time, and the total size difference between the source and output.

## Metadata

`Keep metadata: True` means MuxCls asks FFmpeg to preserve supported metadata from the source where possible. This can include container metadata, stream titles, language tags, chapters, stream labels, and other supported metadata fields.

This does not change video, audio, or subtitle content. Metadata preservation depends on the output container and FFmpeg support, so unsupported metadata may be dropped. Keeping metadata is usually useful for anime and series files because language tags, track titles, chapters, and release information may be preserved. Turning it off can produce cleaner output when the source contains messy or unwanted tags.

Optional output metadata edits apply only to kept output audio and subtitle streams. They can set language codes or titles by current language or exact stream index. Source files are not modified.

## Safety Notes

- MuxCls executes `ffprobe` and `ffmpeg` from your system `PATH`.
- MuxCls executes `robocopy` from your system `PATH` when copying unchanged videos or non-video files.
- MuxCls creates output files and folders based on your selections.
- MuxCls may copy non-video files into the output folder when that option is enabled.
- Existing output files are not overwritten by default; MuxCls uses safe output names and FFmpeg is run with no-overwrite mode.
- If overwrite is enabled, FFmpeg may replace matching output files.
- If your selected audio rule matches no audio stream in a file, that file is skipped and counted as `No audio match`.
- `MuxCls.cmd` tries PowerShell 7 (`pwsh.exe`) first when available, then falls back to Windows PowerShell.
- `Install-MuxClsCommand.ps1` modifies the current user's `PATH` environment variable by adding the project folder. It checks PATH length before writing and broadcasts an environment-change notification when possible.
- `Uninstall-MuxClsCommand.ps1` removes the project folder from the current user's `PATH`.
- Logs can contain local file paths, command lines, system information, warnings, and FFmpeg output. Do not publish local `Logs` files.

## Repository Files

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
| `GITHUB_RELEASE_NOTES.md` | Draft release notes for the next GitHub release. |

## Logs

MuxCls creates a `Logs` folder next to `MuxCls.py` and writes one UTF-8 log file per run. The Python app prints the exact log file path after startup. Log filenames include the date and time, for example:

```text
Logs\muxcls_2026-05-15_22-30-15.log
```

Logs include startup information, FFmpeg and robocopy command lines, command return codes, warnings, captured command output, output size difference, and structured per-file `RESULT` / `SUMMARY_RESULT` lines with the action, status, input path, output path, detail, return code, and elapsed time.

Logs are intended for local troubleshooting and are ignored by Git.

Local-only folders such as `Logs/`, `.Comments/`, and `.claude/` are ignored and are not part of the public release.

## Troubleshooting

### `ffmpeg was not found in PATH`

Install FFmpeg and open a new terminal. Confirm both tools are available:

```powershell
ffmpeg -version
ffprobe -version
```

### `Python was not found`

Install Python 3 or add Python to `PATH`. The launcher first tries `py -3`, then `python`.

### PowerShell blocks the launcher

Run from a trusted local project folder. The command shim uses:

```cmd
pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
```

If PowerShell 7 is not installed, `MuxCls.cmd` falls back to `powershell.exe`.

### Output already exists

MuxCls avoids overwriting existing output unless overwrite is enabled. Choose a different output folder, delete old generated output yourself, or enable overwrite only when you are sure replacing files is safe.

### No audio match

If your audio language, title, or index rule matches no audio streams in a file, MuxCls skips that file instead of creating a silent video-only output. Review the scan report and choose an existing language, title, or stream index.

## License and Attribution

This project is released under the MIT License.

You are free to use, copy, modify, publish, distribute, sublicense, and use this project in your own projects, including free or commercial projects.

However, if you copy, modify, publish, distribute, or include substantial parts of this project in another project, you must keep the original copyright and license notice.

Please preserve this attribution:

MuxCls - Copyright (c) 2026 Kiaro Sama  
Original author: Kiaro Sama  
GitHub: https://github.com/KiaroSama  
Original repository: https://github.com/KiaroSama/MuxCls  
Licensed under the MIT License.

## Donate

If this project helps you, donations are appreciated.

| Currency | Network | Address |
| --- | --- | --- |
| Bitcoin (BTC) | Bitcoin | `bc1qmth5m03pu5hujw5xw5jmywam3jj3sqwqupesdt` |
| USDT, BNB, USDC, etc. | BEP20 | `0x0Bd0BA443a8B9cf15922bf7f0Bb0a4b495fD06Ef` |
| USDT, TRX, USDC, etc. | TRC20 | `TWBA3xFTqgZAeAYMxqo85xWnzvty3DcAhw` |
| Ethereum (ETH) | ERC20 | `0x0Bd0BA443a8B9cf15922bf7f0Bb0a4b495fD06Ef` |
| TON | TON | `UQCN8Umo_OfOWqImZetQsrNStPcmLkMAKajFyiCOhso23NDb` |
| Litecoin (LTC) | LTC | `ltc1qntqnnrunadurnw4cshv3qgspywrueyyeyngwuy` |
| Solana (SOL) | Solana | `7B2wkczUjmkDhETwQuknBL8sUsbuV7nErxc317TmQuwR` |
| Polygon (POL) | Polygon | `0x0Bd0BA443a8B9cf15922bf7f0Bb0a4b495fD06Ef` |
