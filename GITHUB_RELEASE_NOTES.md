# MuxCls v1.7.1

Version tag suggestion: `v1.7.1`

Everything since v1.5.1, in one release. It comes out of a full-codebase audit plus three
rounds of feedback from real runs on real libraries; every defect below was reproduced before
it was fixed.

MuxCls still uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not re-encode video, audio,
or subtitles.

## Fixed

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

## Added

- After a run, MuxCls offers to read the output back and report the streams each file ended up
  with. The check existed and was tested, but nothing in the menu reached it.
- A finished progress row ends with what the file gained or lost:
  `... | Done | Elapsed 00:00:04 | -31.24 MB`.

## Changed

- **The log records what the console showed.** It used to hold eight lines for a five-minute
  session - the scan report, the stream inventory and every menu were on the terminal only,
  which made a log collected from another machine nearly useless. It now also records the
  resolved path and version of `ffmpeg`/`ffprobe`, the working directory, the console encoding
  and the effective environment settings.
- End-of-run size accounting is roughly eight times faster on a large library (measured on
  3000 files: 2.97s to 0.37s).
- CI runs the suite on Python 3.11-3.13 across Windows and Linux, lints with `ruff`, typechecks
  with `mypy`, reports coverage, and runs CodeQL.
- The test suite grew from 106 tests to 269; coverage is 78%.

## Upgrading

Nothing to do. If you installed the `MuxCls` command with a version before 1.6.0, re-running
`Install-MuxClsCommand.ps1` is worthwhile - the old installer is the one that could rewrite your
profile with the wrong encoding.
