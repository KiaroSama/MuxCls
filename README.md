# MuxCls

Current version: **1.4.1**

MuxCls is a cross-platform FFmpeg helper for scanning video files, reviewing audio and subtitle streams, and remuxing files while keeping only the streams you choose.

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
- Preserves the default-track flags that the source already had, instead of forcing the first kept track to be default.
- Rejects an output folder that is the input folder or inside it, so a run's output can never become the next run's input.
- Reports files that `ffprobe` cannot read instead of dropping them, and asks before continuing without them.
- Fails files that have a video extension but no video stream, instead of counting them as successful output.
- Copies unchanged video files with `robocopy` on Windows, or the Python standard library on other platforms.
- Can preserve metadata, chapters, stream labels, language tags, and MKV font attachments when selected.
- Can edit kept output audio and subtitle stream language/title metadata without changing the source files.
- Reports remuxed, copied, skipped, failed, extra-file copy counts, elapsed time, and total output size difference.
- Shows each file's own size change as soon as that file finishes, next to the run total at the end.
- Shows a per-file elapsed timer that starts at zero for each file, alongside the elapsed time of the whole run.
- Writes detailed UTF-8 run logs to the local `Logs` folder, including per-file action summaries.
- Includes a PowerShell launcher (`run.ps1`) and an optional installer that registers a `MuxCls` command.

## Requirements

- Python 3 available as `py -3` or `python`.
- FFmpeg installed and available in `PATH` as both `ffmpeg` and `ffprobe`.
- No external Python packages are required.

Windows-only extras:

- Windows PowerShell or PowerShell 7 for the included launchers (`run.ps1`, `Install-MuxClsCommand.ps1`).
- Robocopy, which ships with Windows, is used for unchanged-video and non-video file copies.

On Linux and macOS MuxCls runs with `python MuxCls.py` and copies files with the Python
standard library instead of robocopy. Everything else behaves the same.

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

You can run MuxCls directly from the project folder with `.\run.ps1`, or register a
`MuxCls` command for your user:

```powershell
.\Install-MuxClsCommand.ps1
```

This adds a `MuxCls` function to your PowerShell profile. After installing, open a new
PowerShell terminal and run:

```powershell
MuxCls
```

The `MuxCls` command works in PowerShell only (it is a profile function). In `cmd.exe`,
run `.\run.ps1` from the project folder instead.

To remove the command later, delete the `# BEGIN MuxCls command` / `# END MuxCls command`
block from your PowerShell profile (`$PROFILE`).

## Usage

Run from the project folder:

```powershell
.\run.ps1
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

When advanced selection is used, MuxCls skips the audio questions only when no scanned file has more than one audio track, and skips the subtitle questions when there are no subtitle streams. If any file has multiple audio tracks, the audio questions are asked even when every track shares the same language (for example, a main track plus a commentary track).

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

If a generated folder already exists and overwrite is off, MuxCls adds a numeric suffix such as
`(2)`. With overwrite on it reuses the folder you asked for instead of numbering it.

In folder mode the output folder may not be the input folder or any folder inside it. MuxCls
rejects such a path, because that output would be picked up as input by the next run.

If you enter a relative output folder, MuxCls shows the resolved absolute path and asks for confirmation. If an output path looks like a media file name, such as `output.mkv`, MuxCls rejects it and asks for a folder path.

If the selected rules do not require remuxing a video file, MuxCls copies that file unchanged
instead of running FFmpeg: with `robocopy` on Windows, or the Python standard library on other
platforms. Remux and copy operations show a live per-file elapsed timer next to the elapsed time
of the whole run, and print that file's size change when it finishes. When enabled, non-video files are copied to the output folder with the same relative paths as the source folder.

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
- If overwrite is enabled, MuxCls reuses the output folder you asked for and replaces matching files.
- MuxCls refuses an output folder that is inside the input folder when processing a folder.
- If a file cannot be read by `ffprobe`, MuxCls reports it and asks before continuing without it.
- If your selected audio rule matches no audio stream in a file, that file is skipped and counted as `No audio match`.
- `Install-MuxClsCommand.ps1` adds a `MuxCls` function to your PowerShell profile(s) and removes any stale MuxCls folder entry left in your user `PATH` by older versions. It does not add anything to `PATH`.
- Logs can contain local file paths, command lines, system information, warnings, and FFmpeg output. Do not publish local `Logs` files.

## Repository Files

| Path | Purpose |
| --- | --- |
| `MuxCls.py` | Thin entry point that runs the `muxcls` package. |
| `muxcls/` | Application package, split by responsibility (see Project Structure below). |
| `run.ps1` | PowerShell launcher that finds Python and runs `MuxCls.py`. |
| `Install-MuxClsCommand.ps1` | Registers a `MuxCls` command via a PowerShell profile function. |
| `README.md` | Project documentation. |
| `.gitignore` | Excludes logs, caches, local notes, temporary files, secrets, and generated output. |
| `LICENSE` | MIT License. |
| `ATTRIBUTION.md` | Standalone attribution notice for reuse and redistribution. |
| `CONTRIBUTING.md` | Contribution and testing guidelines. |
| `SECURITY.md` | Security policy and vulnerability reporting. |
| `CHANGELOG.md` | Versioned project changelog. |
| `GITHUB_RELEASE_NOTES.md` | Draft release notes for the next GitHub release. |
| `tests/` | Pytest test suite (unit tests and real FFmpeg end-to-end tests). |
| `pytest.ini` | Pytest configuration. |
| `requirements-dev.txt` | Test-only dependencies (not required to run MuxCls). |
| `.github/workflows/tests.yml` | GitHub Actions workflow that runs the test suite on push/PR. |
| `.github/` | Issue/PR templates and Dependabot configuration. |

## Project Structure

The application logic lives in the `muxcls` package, split by responsibility. `MuxCls.py`
is a thin entry point that imports and runs `muxcls.app.main`.

| Module | Responsibility |
| --- | --- |
| `muxcls/constants.py` | Shared constants: video extensions, tool names, selection-mode codes. |
| `muxcls/colors.py` | ANSI color palette and text coloring helpers. |
| `muxcls/logsetup.py` | Logger setup and per-run log file creation. |
| `muxcls/models.py` | Data models (`StreamInfo`, `MediaFile`, `SelectionRules`) and ffprobe parsing helpers. |
| `muxcls/textutil.py` | Terminal/text formatting, language, and size helpers. |
| `muxcls/prompts.py` | Interactive input prompts and menu navigation. |
| `muxcls/media.py` | External process execution (`ffprobe`/`ffmpeg`), timeouts, cancellation, and file probing/scanning. |
| `muxcls/muxlogic.py` | Stream selection logic, remux-needed decisions, and FFmpeg command building. |
| `muxcls/output.py` | Output path resolution, naming, and filesystem helpers. |
| `muxcls/reporting.py` | Scan reports, unique-stream summaries, and selection previews. |
| `muxcls/selection.py` | Interactive rule configuration (advanced and exact modes). |
| `muxcls/copying.py` | File copy backends: robocopy on Windows, Python standard library elsewhere. |
| `muxcls/processing.py` | Per-file processing decisions, remuxing, run summary, and verification. |
| `muxcls/app.py` | Main menu, top-level flow, and program entry (`main`). |

## Logs

MuxCls creates a `Logs` folder next to `MuxCls.py` and writes one UTF-8 log file per run. The Python app prints the exact log file path after startup. Log filenames include the date and time, for example:

```text
Logs\muxcls_2026-05-15_22-30-15_UTC.log
```

Log timestamps are UTC. At the default level a log holds startup information, the resolved rules,
one line per file with its status, action, size change, elapsed time and return code, plus the run
summary. Failures also carry the captured command output.

Set the `MUXCLS_DEBUG` environment variable to `1` for a verbose log that also records every
command line and the captured output of successful commands:

```powershell
$env:MUXCLS_DEBUG = "1"; .\run.ps1
```

Logs are intended for local troubleshooting and are ignored by Git.

## Timeouts and safe replacement

Every remux and file copy runs under one wall-clock ceiling, so a wedged FFmpeg or copy cannot
stall a run forever. The default is 3 hours. Set `MUXCLS_OPERATION_TIMEOUT` to a number of
seconds to change it, or to `0` to disable the bound:

```powershell
$env:MUXCLS_OPERATION_TIMEOUT = "7200"; .\run.ps1
```

Output is written safely in every case. A remux goes to a sibling partial file, and an
unchanged-video copy goes to a private staging folder on Windows or a temporary file
elsewhere; either is renamed onto the real output only after the operation completes. A
failure, a timeout, or `Ctrl+C` therefore leaves no partial file behind and never damages an
output produced by an earlier run.

Local-only folders such as `Logs/`, `.Comments/`, `.kiro/`, and `.claude/` are ignored and are not part of the public release.

## Testing

MuxCls has a pytest test suite under `tests/`, covering stream-selection logic, output
path resolution, and real end-to-end remuxing through actual FFmpeg-generated files.

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests -v
```

The end-to-end tests in `tests/test_processing_e2e.py` require `ffmpeg`/`ffprobe` in
`PATH` and are skipped automatically if unavailable. The robocopy overwrite tests
additionally require Windows and are skipped on other platforms.

A GitHub Actions workflow (`.github/workflows/tests.yml`) runs the same suite on
`windows-latest` and `ubuntu-latest` for every push and pull request.

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

Run from a trusted local project folder. If script execution is blocked, start the
launcher explicitly with an execution-policy bypass for the current process:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\run.ps1
```

PowerShell 7 (`pwsh`) is preferred when available; Windows PowerShell (`powershell.exe`)
also works.

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
