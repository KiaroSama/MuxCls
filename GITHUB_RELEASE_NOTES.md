# MuxCls v1.8.0

Version tag suggestion: `v1.8.0`

Everything since v1.5.1, in one release. It comes out of a full-codebase audit plus several
rounds of feedback from real runs on real libraries; every defect below was reproduced before
it was fixed, and the stream-order feature was verified on real media rather than fixtures
alone.

MuxCls still uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video, audio,
or subtitles.

## Added

- **You can choose the order of the output streams.** On the output-stream screen, enter the
  source stream indexes in the order the output should carry them - `2,1` puts stream 2 ahead
  of stream 1. Anything you leave out keeps its place after the ones you named, so moving one
  track does not mean retyping the rest. Audio and subtitles are ordered independently, and
  each stream's default flag and title travel with it, so moving the track that carried the
  default does not leave the flag behind on whatever ends up first.
- After a run, MuxCls offers to read the output back and report the streams each file ended up
  with. The check existed and was tested, but nothing in the menu reached it.
- A finished progress row ends with what the file gained or lost:
  `... | Done | Elapsed 00:00:04 | -31.24 MB`.

## Fixed

- **The run summary overstated how much space was saved.** `Size difference` compared the whole
  input tree against the whole output tree, so every input that produced no output - a failed
  file, a skip, a no-audio-match - had its entire size counted as a reduction. It was wrong in
  exactly the runs where something had gone wrong. The total is now the sum of the per-file
  figures, which were always correct.
- **A file whose name starts with `-` could not be processed.** Entering a relative input path
  such as `.` produced a bare command-line token, which FFprobe read as an option rather than a
  file - and the file was then reported as one it could not read. Paths supplied by the user are
  anchored before they reach a command line.
- **The installer could destroy non-ASCII text in your PowerShell profile.** It rewrote the whole
  profile using `Get-Content`/`Set-Content`, whose default encodings differ between Windows
  PowerShell 5.1 and PowerShell 7. It now reads and writes bytes explicitly, keeps the file's
  existing BOM state, and leaves a profile it cannot decode untouched.
- **A scan could fail on an unreadable stream field.** FFprobe writes `N/A` where a container
  carries no value; one such field raised part-way through a scan instead of being treated as
  unknown.
- **A stray timer line under the progress block, with the block's top row drawn twice.** The
  per-command timer enabled itself on any terminal, including while the block was drawing; its
  line scrolled the terminal and the block's next repaint landed one line short. The block owns
  the screen for the length of a run now.

## Changed

- **The log records what the console showed.** It used to hold eight lines for a five-minute
  session - the scan report, the stream inventory and every menu were on the terminal only,
  which made a log collected from another machine nearly useless. It now also records the
  resolved path and version of `ffmpeg`/`ffprobe`, the working directory, the console encoding
  and the effective environment settings. A later pass caught the last two console-only report
  surfaces: the output-verification report and the end-of-run summary.
- A `[Enter=...]` hint is painted the same green as `[Y]` and `[n]`. It is a default value like
  any other, so reading it as part of the question was misleading.
- A run whose input is a single file is no longer asked whether to copy non-video files. There
  are none beside it, so the question had no answer that changed anything.
- When every stream survives but the order changed, the reason for remuxing reads
  `audio stream order changes` rather than `selection changes`, which would send you looking for
  a track that was never dropped.
- End-of-run size accounting is roughly eight times faster on a large library (measured on
  3000 files: 2.97s to 0.37s).
- CI runs the suite on Python 3.11-3.13 across Windows and Linux, lints with `ruff`, typechecks
  with `mypy` for both `win32` and `linux`, reports coverage, and runs CodeQL.
- The test suite grew from 106 tests to 293; coverage is 81%.

## Upgrading

Nothing to do. If you installed the `MuxCls` command with a version before 1.6.0, re-running
`Install-MuxClsCommand.ps1` is worthwhile - the old installer is the one that could rewrite your
profile with the wrong encoding.
