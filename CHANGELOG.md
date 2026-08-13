# Changelog

## [1.7.3] - 2026-08-11

### Changed

- The output-verification report and the run-summary block now reach the log too. Found by reading a real 22-file log: the verification header and its re-scan were recorded, but not one of its per-file lines - so the log could show that the output had been checked without recording what the check found. Both blocks live in `processing.py`, which the 1.7.0 logging work had not covered.

## [1.7.2] - 2026-08-10

### Fixed

- `Size difference` in the run summary counted every input that produced no output - a failed file, a skip, a no-audio-match - as if all of its bytes had been saved. It compared the whole input tree against the whole output tree, so an untouched file appeared as a pure reduction. Measured on a 3-file run with one failure: `-63.07 KB` reported against a real `-36.80 KB`, the difference being the failed file byte for byte. The total is now the sum of the per-file changes, which are and always were correct.

## [1.7.1] - 2026-08-10

### Changed

- A finished row ends with what the file gained or lost again: `... | Done | Elapsed 00:00:04 | -31.24 MB`. It sits after `Elapsed` rather than beside the state word - in that earlier position it occupied the column a live row uses for its countdown and read as the transfer-speed field that was removed, which is why it was taken out. The bar reserves another twelve columns so the figure cannot be truncated away on a narrower terminal.

## [1.7.0] - 2026-08-10

### Fixed

- A stray `Elapsed .. | Total ..` line was drawn underneath the live progress block, and the block's top row appeared twice. One cause: `run_with_progress` builds a per-command timer that enabled itself on any terminal - including while the block was drawing. Its line scrolled the terminal by one, so the block's next repaint moved up one line short and stranded its top row. The block now owns the screen for the length of a run and the timer stays quiet while it does.

### Changed

- The log records what the console showed. It previously held eight lines for a five-minute session: the scan report, the stream inventory, every menu and every answer were on the terminal only, which made a log collected from another machine nearly useless. Startup now also records the resolved path and version of `ffmpeg`/`ffprobe`, the working directory, the console encoding and size, and the effective environment settings. Console text is formatted once and written twice - coloured to the terminal, stripped for the log - so the two cannot drift apart.

## [1.6.3] - 2026-08-10

### Changed

- The metadata-edit step moved out of `muxcls/selection.py` into `muxcls/metadata_edits.py`. The two answer different questions - `selection.py` decides which streams survive, `metadata_edits.py` decides what the survivors are called - and the split is along that line, not at a line count. `selection.py` is 529 lines instead of 679; nothing else changed.

## [1.6.2] - 2026-08-10

### Removed

- `Install-MuxClsCommand.ps1` no longer carries the user-PATH cleanup, or the `SendMessageTimeout` P/Invoke that existed to broadcast it. It only ever removed a folder entry added by the pre-1.4 installer, an approach that never provided a working command; nothing has created that entry for several releases. The script is 91 lines instead of 168.
- Three functions with no caller anywhere, not even in tests: `option_suffix` and `ask_choice` in `muxcls/prompts.py`, `has_unknown_language` in `muxcls/reporting.py`.

### Changed

- `matching_streams_for_media` and `terminal_separator` were single-caller wrappers that only delegated; both are inlined at their one call site.
- `unique_path` and `unique_directory_path` ran the same search with a different name shape. One function does both now - a folder numbers its whole name, a file numbers the stem so the extension stays last.
- The four test modules that drive interactive prompts shared one copy each of the same scripted-input helper. It is a single `answers` fixture in `tests/conftest.py` now.

Net: 244 lines removed, 95 added, across nine files. No behaviour change - all 251 tests, ruff and mypy pass unchanged.

## [1.6.1] - 2026-08-10

### Changed

- CI now lints (`ruff`), typechecks (`mypy`) and reports coverage. Both linters run once on the primary matrix combination rather than on all five, since they read the same source everywhere. Coverage is reported, never gated on a threshold.
- `muxcls/reporting.py` used one loop variable for two summaries keyed differently, which made the second loop read as though it indexed the first one's keys.
- `muxcls/app.py` guards the two places where the configured rules could not be proven non-empty. They are guards rather than assertions, so they survive `python -O`.

### Added

- Tests for `muxcls/app.py`, which had none: the tool-missing refusals, the no-video-files and unscannable-file paths, the probe-failure prompt, the confirmation gate, the new verification prompt, and the exit code each of `quit`, Back, Ctrl+C and an unexpected error produces.
- Tests for the advanced selection flow's Back map, the metadata-edit prompt, the selection-style menu and the revisit entry point.
- Coverage went from 71% to 78% overall; `app.py` from 0% to 79% and `selection.py` from 59% to 70%. The suite is now 251 tests.

## [1.6.0] - 2026-08-10

### Added

- After a run finishes, MuxCls offers to read the output back and report what each file ended up with. The check existed and was tested but had no way to reach it from the menu. It defaults to no, since it costs one `ffprobe` per output file.

### Fixed

- A file whose name begins with `-` could not be processed at all when the input path was typed as a relative one such as `.`. Paths were expanded but never anchored, so `Path('.') / '-name.mkv'` collapsed to `-name.mkv`, and `ffprobe`/`ffmpeg` read that as an option rather than a file - the file was then reported as one that could not be read. Every path the user supplies is now made absolute before it reaches a command line.
- `Install-MuxClsCommand.ps1` could destroy non-ASCII text in the user's PowerShell profile. It rewrote the whole file - including lines it did not write - using `Get-Content`/`Set-Content`, whose default encodings differ between Windows PowerShell 5.1 and PowerShell 7. It now reads and writes bytes explicitly, keeps the file's existing BOM state, and refuses to touch a profile that is not UTF-8 rather than guessing.
- A stream record with an unreadable numeric field (`ffprobe` writes `N/A` where a container carries no value) raised part-way through a scan instead of being treated as unknown.

### Changed

- The end-of-run size accounting no longer re-resolves the excluded output folder once per file. Measured on a 3000-file library: 2.97s before, 0.37s after. Collecting the non-video files to copy uses the same pruning walk.
- CI runs the suite on Python 3.11, 3.12 and 3.13 instead of 3.11 alone, and a CodeQL workflow analyses the codebase weekly and on every push.
- The declared `pytest` floor is the version the suite is actually run against.

## [1.5.1] - 2026-08-09

### Fixed

- The progress bar did not actually move on real material. Running the app over full-size episodes showed both progress sources producing nothing: FFmpeg reports `out_time_us=N/A` for some material, so the remux row stayed at 0% until the file finished, and Robocopy's percentage was suppressed by `/NFL` - that percentage is printed as part of the file record, so `/NFL` silences it exactly as `/NP` does. A remux now falls back to the bytes FFmpeg reports written, and the Robocopy copy reports its percentage again.
- The size beside a bar stayed at `0 B` for the whole copy. Robocopy reports a percentage and no byte count, and the per-file row read the byte count directly instead of deriving it from the ratio, which is what the `Overall` line already did.

## [1.5.0] - 2026-08-09

### Added

- A live progress view. On a terminal, processing now draws a block that repaints in place: an `Overall` bar with a files-done count and the run's elapsed time, then one row per file showing a bar, percentage, how much of it is done out of its total, an ETA and that file's own elapsed time, with the rows still waiting marked `Queued` and the finished ones `Done`, `Failed` or `Skipped`. When the list is taller than the terminal it follows the file being worked on and says how many rows are hidden above and below. The layout is adapted from EVdlc's progress view.
- Real percentages rather than a spinner. A remux reports FFmpeg's own position (`-progress`, measured against the container duration ffprobe reports), the standard-library copy reports the bytes it has written, and the Robocopy copy reports Robocopy's own percentage.

### Changed

- With redirected output there is no cursor to move, so the run keeps printing the previous one-line-per-file format. A log or a CI transcript reads the same as before.
- FFmpeg's progress stream is no longer written to the log on failure; it is telemetry, and thousands of `key=value` lines would bury the stderr message that says what actually broke.

## [1.4.2] - 2026-08-09

### Added

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
