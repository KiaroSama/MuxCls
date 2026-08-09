# MuxCls v1.6.0

Version tag suggestion: `v1.6.0`

This release comes out of an audit of the whole codebase. Three of the fixes are
for defects that only appear on real material or on someone else's machine, and
each was reproduced before it was fixed.

MuxCls still uses FFmpeg stream copy (`ffmpeg -c copy`), so it does not
re-encode video, audio, or subtitles.

## Fixed

- **A file whose name starts with `-` could not be processed.** Typing a
  relative input path such as `.` produced a bare command-line token: pathlib
  drops a lone `.` on join, so `Path('.') / '-name.mkv'` is just `-name.mkv`,
  and FFprobe reads that as an option rather than a file. The file was then
  reported as one that could not be read, which is a misleading diagnosis for a
  perfectly good file. Paths supplied by the user are now anchored before they
  reach a command line.
- **The installer could destroy non-ASCII text in your PowerShell profile.**
  `Install-MuxClsCommand.ps1` rewrites the whole profile - including lines it
  did not write - and used `Get-Content`/`Set-Content`, whose default encodings
  differ between Windows PowerShell 5.1 and PowerShell 7. Measured: a UTF-8
  profile with no BOM lost its non-ASCII content under 5.1, and a
  legacy-encoded one gained replacement characters under 7. The installer now
  reads and writes bytes explicitly, preserves whether the file had a BOM, and
  leaves a non-UTF-8 profile untouched with instructions instead of guessing.
- **A scan could fail on an unreadable stream field.** FFprobe writes `N/A`
  where a container carries no value; one such field raised part-way through a
  scan instead of being treated as unknown.

## Added

- After a run, MuxCls offers to read the output back and report the streams each
  file ended up with. The check already existed and was tested, but nothing in
  the menu reached it. It defaults to no, since it costs one `ffprobe` per file.

## Changed

- End-of-run size accounting is roughly eight times faster on a large library.
  It was re-resolving the excluded output folder once per file; it now steps
  over that folder once. Measured on 3000 files: 2.97s before, 0.37s after.
- CI runs the suite on Python 3.11, 3.12 and 3.13 on Linux and on 3.11 and 3.13
  on Windows, instead of 3.11 alone.
- A CodeQL workflow now analyses the codebase on every push and weekly.
- The declared `pytest` floor matches the version the suite is actually run
  against.

## Upgrading

Nothing to do. If you installed the `MuxCls` command with an earlier version,
re-running `Install-MuxClsCommand.ps1` is worthwhile: the old installer is the
one that could rewrite your profile with the wrong encoding.
