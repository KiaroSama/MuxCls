# Changelog

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
