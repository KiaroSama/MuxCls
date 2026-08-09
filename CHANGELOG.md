# Changelog

## [1.4.2] - 2026-08-09

### Added

- `.test/Run-Demo.ps1`, a display-only UI demo. It walks through everything MuxCls prints — scan report, stream summary, menus, confirmation, per-file processing and the final summary — without reading, writing or converting a single file, and without invoking FFmpeg. The screens are drawn by the application's own rendering functions fed invented data, so the demo cannot drift from the real UI. Each file is given a configurable span (5 seconds by default) so the per-file `Elapsed` timer is actually readable next to the run `Total`; a real stream copy finishes in milliseconds, which is why that line normally flashes past. Three scenarios: a remux run, a copy-unchanged run, and a mixed run that also shows a scan failure, a file with no video stream and a no-audio-match skip.
- A regression guard for the demo (`tests/test_demo_ui.py`). The demo draws with the application's own rendering functions, so renaming one would break it silently; the guard runs the whole walkthrough with no waiting, drives the launcher's real menu, and fails if a screen stops rendering, the launcher swallows the output, or the demo writes a file.
- `docs/MANUAL_QA.html`, a manual QA checklist built from the real strings and constants in `muxcls/`. One standalone file with a Persian/English switch that also flips direction; results persist in the browser.

### Fixed

- The demo launcher printed nothing when a run was chosen. Assigning the call that ran the demo made the child's whole output part of the PowerShell function's return value, so the screen stayed blank and the per-file timer stopped drawing; and filtering the argument array dropped `--seconds 0`, because PowerShell treats `0` as falsy.
- Non-video file copying is now bounded and cancellable like everything else. The standard-library backend receives the operation timeout, and the Robocopy backend runs through the same cancellable runner as the rest instead of an unbounded call, so a timeout or `Ctrl+C` stops and reaps it.
- A failed or cancelled non-video copy no longer leaves a truncated file in the output. Destinations this run created but did not finish writing are removed, and reported as failed rather than copied; a destination that already existed is never touched.

### Changed

- The copy timeout regression test no longer races the machine. It drives a fake clock, so it proves the timeout path on any runner speed instead of assuming a slow one.

## [1.4.1] - 2026-08-09

### Fixed

- A failed or cancelled copy can no longer destroy the output it was replacing. The unchanged-video copy now stages into a private folder (Windows) or a temporary file (elsewhere) and renames it into place only after a complete copy; the previous destination is untouched if Robocopy fails, times out, or you press Ctrl+C.
- A failed remux no longer leaves a partial file behind. FFmpeg writes to a sibling partial file that is renamed onto the real output only on success, so a failure, timeout or Ctrl+C leaves the output folder exactly as it was.
- Overwrite now really replaces non-video files. A destination matching the source on name, size and write time lands in Robocopy's "modified" class, which its documentation says is not copied without `/IM` — `/IS` and `/IT` do not cover it. Rather than depend on that classification, non-video copying with overwrite enabled goes through the unconditional copy path instead.
- Every remux and copy now runs under one timeout policy instead of only FFmpeg supporting one and nobody passing it. Set `MUXCLS_OPERATION_TIMEOUT` (seconds, `0` disables) to change it; the default is 3 hours.

## [1.4.0] - 2026-08-09

### Fixed

- Default track flags are now preserved. MuxCls used to force the first kept audio and subtitle stream to be the default and clear the rest, which moved the default onto a track the source never marked. It also triggered a full remux of files that needed none, purely to apply that normalization. Selected streams now keep exactly the default flags they had.
- A file with no audio stream is no longer processed silently when audio was requested. Any audio mode other than "remove all audio" now records `NO_AUDIO_MATCH` for such a file, instead of only doing so when the file had audio that failed to match.
- "Remove all audio" is reachable again for sets with a single audio track. The audio menu was skipped whenever no file had more than one track, which also removed the only way to ask for no audio. It is now skipped only when nothing in the scan has audio at all.
- In folder mode the output folder can no longer be the input folder or a folder inside it. Such output was rescanned as input on the next run.
- Files that `ffprobe` cannot read are no longer discarded silently. They are reported before rule selection, need an explicit confirmation to continue past, and are counted in the run totals, the log, and the final summary.
- A file with a supported video extension but no video stream is now a validation failure before any copy or remux, instead of a warning followed by a "successful" output.
- FFmpeg and copy operations can be interrupted. FFmpeg runs with `-nostdin`, every child process is started with no stdin, and a timeout, `Ctrl+C`, or an unexpected error terminates the child and kills it if it does not stop. A partial output file is removed rather than reported as success.
- Overwrite is consistent in folder mode: it now reuses the output folder you asked for instead of creating a numbered sibling, and an unchanged-video copy replaces a destination Robocopy would otherwise skip. Without overwrite the numeric-suffix behavior is unchanged.

### Added

- Each file prints its own size change as soon as it finishes, in addition to the run total.
- Each file has its own elapsed timer that starts at zero and stops when that file is done, shown next to the elapsed time of the whole run.
- Linux and macOS support: robocopy is used only on Windows, and every other platform copies with the Python standard library. CI now runs the suite on `ubuntu-latest` as well as `windows-latest`.
- `MUXCLS_DEBUG=1` enables a verbose log with command lines and successful-command output.
- Regression tests for every fix above, including real-file end-to-end coverage.

### Changed

- Logs are much quieter by default: UTC timestamps, `INFO` level instead of `DEBUG`, captured command output only for failures, per-file paths relative to the run roots, and no duplicated per-file summary block at the end.
- File copy backends moved from `processing.py` into a new `muxcls/copying.py`, so process orchestration and platform-specific copying are separate.

## [Unreleased]

### Changed

- Internal cleanup: removed unused color constants and stale generated-module headers, removed a redundant audio-mode branch, and deduplicated selection-rules construction in the interactive wizards. No behavior change.

### Added

- Added a pytest test suite (`tests/`) covering stream-selection logic, output path resolution, and real FFmpeg end-to-end remuxing/copy-unchanged scenarios.
- Added a GitHub Actions workflow (`.github/workflows/tests.yml`) that runs the test suite on `windows-latest` for every push and pull request.
- Added GitHub community files: `CONTRIBUTING.md`, `SECURITY.md`, issue templates, a pull request template, and Dependabot configuration.

## [1.3.1] - 2026-07-05

### Fixed

- Fixed audio stream selection being skipped when a file had a single audio language but multiple audio tracks (for example, a main track plus a commentary track). Selection is now skipped only when no file has more than one audio track; multi-track files always prompt for audio selection.

### Changed

- Split the single-file `MuxCls.py` into the `muxcls/` package, organized by responsibility (constants, colors, logging, models, text/UI helpers, prompts, media, mux logic, output, reporting, selection, processing, and app). `MuxCls.py` is now a thin entry point. Behavior is unchanged.
- Preserved the original single-file version under `archive/` at the time of the split (later removed; still recoverable from Git history, commit `7a2306d`).
- `Install-MuxClsCommand.ps1` now registers a `MuxCls` command by adding a function to the user's PowerShell profile(s), instead of adding the project folder to `PATH`. Typing `MuxCls` in PowerShell now launches the app (previously the PATH entry never provided a working `MuxCls` command). The installer also removes any stale MuxCls folder entry left in the user `PATH` by older versions.

### Removed

- Removed the `MuxCls.cmd` command shim. Use the `run.ps1` PowerShell launcher instead.
- Removed `Uninstall-MuxClsCommand.ps1`. To remove MuxCls from `PATH`, delete the project folder from the user `PATH` in Windows Environment Variables.

## [1.3.0] - 2026-06-03

### Added

- Added live elapsed progress while unchanged video files are copied with `robocopy`.
- Added structured per-file `RESULT` log lines and final `SUMMARY_RESULT` log lines with action, status, input path, output path, detail, return code, and elapsed time.

### Changed

- Updated runtime version to `1.3.0`.
- Unchanged-video copy operations now use `robocopy /J`.

### Fixed

- Fixed unchanged-video copy operations appearing idle during longer copy runs.
- Improved processing logs so remuxed, copied, skipped, no-audio-match, and failed file outcomes are recorded clearly.

## [1.2.0] - 2026-05-26

### Added

- Added optional output stream metadata editing for kept audio and subtitle streams.
- Added stream size display in scan reports when FFprobe provides enough data.
- Added optional non-video file copying into the output folder with preserved relative paths.
- Added unchanged-video copying with `robocopy` when selected rules do not require remuxing.
- Added processing summary counts for remuxed files, copied unchanged files, non-video copy results, elapsed time, and total output size difference.
- Added FFmpeg and robocopy command logging for remux and copy actions.

### Changed

- Updated runtime version to `1.2.0`.
- Removed the first action menu so the workflow goes directly from scan review to stream selection and processing.
- Processing progress now shows a live global elapsed timer only for the file currently being remuxed.
- Scan reports and unique stream summaries now use ` | ` separators consistently.
- Unknown language tags are displayed as `*uknown` in the interactive UI.
- The PowerShell launcher now starts quietly while preserving ANSI-friendly console behavior.

### Fixed

- Fixed live elapsed progress so it uses total batch time instead of resetting per file.
- Fixed output summary logging so size difference is written to the run log.
- Fixed unnecessary remuxing for files that already match the selected stream and metadata rules.

## [1.1.1] - 2026-05-23

### Changed

- Numbered menus now default to option `1`.
- The stream selection style menu now defaults to advanced rules by language, title, or index.
- Advanced subtitle selection now uses option `1` for keeping all subtitles and option `5` for removing subtitles.
- Scan reports now print a full-width colored separator between file sections.
- Stream reports now use a larger 20-color ANSI palette for clearer field highlighting.
- Stream summary rows and menu prompts now use ANSI colors for the displayed fields and navigation hints.
- Multi-choice menus now use a cleaner multi-line layout with green option numbers, green `(default)` markers, colored `Found:` values, and yellow example hints.
- Yes/no prompts now keep the question text plain while coloring only the default answer letter and navigation hints.
- Header labels are now centered, and header separators use the current terminal width while omitting the previous top separator line.
- Stream scan rows now use ` | ` separators between fields for easier reading.
- Processing output now prints a colored separator before each file and uses centered `Done` status lines.
- Scan and verify headers now use title case, and verify completion prints a ready-for-next-task message before returning to the input prompt.
- The PowerShell launcher no longer prints its startup banner, working folder, script path, or running notice.
- PowerShell launcher now sets ANSI-friendly console environment values before starting Python.

### Fixed

- Fixed `0=Back` navigation so nested prompts no longer jump back multiple major steps.
- Verification now returns to the main input prompt instead of ending the terminal session.
- Advanced selection now skips audio questions when only one audio language exists, and skips subtitle questions when no subtitle streams exist.
- The stream selection style prompt is also skipped when only one audio language exists.
- Improved Windows ANSI color initialization for both stdout and stderr, with a fallback for older consoles.

## [1.1.0] - 2026-05-23

### Added

- Added `Uninstall-MuxClsCommand.ps1` to remove MuxCls from the current user's `PATH`.
- Added PowerShell 7 preference in `MuxCls.cmd`, with fallback to Windows PowerShell.
- Added periodic `still remuxing...` console updates during long FFmpeg runs.
- Added non-video extension hints when an input path contains files but no supported videos.
- Added explicit `q` support to menu navigation hints.

### Changed

- Updated runtime version to `1.1.0`.
- Advanced subtitle selection now defaults to keeping all subtitles.
- Output folder prompts now reject accidental yes/no answers and media-file-like paths.
- Relative output folders now show their resolved absolute path and require confirmation.
- FFmpeg output is buffered to temporary files for logging while normal console output stays concise.
- Stream language coloring is now deterministic across languages.
- Unique stream summaries now preserve displayed title capitalization.
- Metadata guidance in the CLI now reads as an explanatory note instead of a fixed state.
- Verify mode now respects intentional no-audio output when audio removal was selected.

### Fixed

- Fixed a crash when `ffprobe` returns `{"streams": null}` or malformed stream entries.
- Fixed silent video-only output when an audio selection rule matches no audio stream.
- Fixed multiple kept audio or subtitle streams retaining `default` disposition flags.
- Fixed folder-mode output path collision handling.
- Fixed empty language, title, and index selections in advanced rules by re-prompting for at least one parsed value.
- Fixed misleading output suffixes for empty or invalid selection rules.
- Fixed invalid filename sanitization for names made only of invalid filename characters.
- Fixed ambiguous compact language suffix truncation.
- Fixed negative elapsed time handling by logging a warning.
- Fixed prompt formatting so labels and navigation hints render with a separator.
- Fixed ANSI color setup on Windows by using console mode APIs.
- Fixed PATH installer robustness with a user PATH length check and environment-change broadcast.

### Removed

- Removed unused internal helper functions.

### Security

- Ignored local `.claude/` settings so private workspace configuration is not prepared for public commits.
