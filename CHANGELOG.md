# Changelog

## [1.3.1] - 2026-07-05

### Fixed

- Fixed audio stream selection being skipped when a file had a single audio language but multiple audio tracks (for example, a main track plus a commentary track). Selection is now skipped only when no file has more than one audio track; multi-track files always prompt for audio selection.

### Changed

- Split the single-file `MuxCls.py` into the `muxcls/` package, organized by responsibility (constants, colors, logging, models, text/UI helpers, prompts, media, mux logic, output, reporting, selection, processing, and app). `MuxCls.py` is now a thin entry point. Behavior is unchanged.
- Preserved the original single-file version under `archive/`.

### Removed

- Removed the `MuxCls.cmd` command shim. Use the `run.ps1` PowerShell launcher instead.

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
