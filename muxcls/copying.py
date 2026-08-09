"""File-copy backends used when a video needs no remux and for non-video files.

Windows keeps using robocopy (unbuffered `/J` copies are noticeably faster for
large media files); every other platform uses the stdlib. Both backends report
the same copied/skipped/failed counts, so the caller does not care which ran.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .constants import COPY_CHUNK_BYTES, IS_WINDOWS, ROBOCOPY_BIN, VIDEO_EXTENSIONS
from .colors import err
from .logsetup import LOGGER
from .models import SelectionRules
from .textutil import ProgressPrinter
from .media import run_command, run_with_progress
from .output import destination_snapshot, extra_file_sources, path_is_under, robocopy_success


# Name of the in-progress copy, renamed onto the destination when complete.
PARTIAL_SUFFIX = ".muxcls-partial"


def robocopy_available() -> bool:
    return IS_WINDOWS and shutil.which(ROBOCOPY_BIN) is not None


def robocopy_overwrite_flags(overwrite: bool) -> List[str]:
    """Robocopy skips destinations it considers same, newer or older. Overwrite
    means "make the destination match the source", so those skips are switched
    off; without overwrite they become explicit excludes."""
    if overwrite:
        return ["/IS", "/IT"]
    return ["/XC", "/XN", "/XO"]


def copy_file_with_progress(
    source: Path,
    destination: Path,
    total_started_at: Optional[float] = None,
) -> None:
    """Chunked stdlib copy with a live elapsed line.

    The bytes go to a temporary file beside the destination and are renamed into
    place only once the copy is complete. A failure or a Ctrl+C therefore leaves
    neither a partial file nor a damaged previous output: whatever was already at
    the destination is still there, untouched.
    """
    progress = ProgressPrinter(total_started_at)
    partial = destination.with_name(destination.name + PARTIAL_SUFFIX)
    try:
        with source.open("rb") as reader, partial.open("wb") as writer:
            while True:
                chunk = reader.read(COPY_CHUNK_BYTES)
                if not chunk:
                    break
                writer.write(chunk)
                progress.tick()
        copy_timestamps(source, partial)
        partial.replace(destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        progress.close()


def copy_timestamps(source: Path, destination: Path) -> None:
    """Carry over the modification time but not the permission bits. Copying the
    mode would turn a read-only source into a read-only output, which the next
    overwrite run could not replace."""
    try:
        info = source.stat()
        os.utime(destination, ns=(info.st_atime_ns, info.st_mtime_ns))
    except OSError as exc:
        LOGGER.warning("Could not copy timestamps to %s: %s", destination, exc)


def copy_video_without_remux(
    input_file: Path,
    output_file: Path,
    overwrite: bool = False,
    total_started_at: Optional[float] = None,
) -> int:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Robocopy copies a file into a folder under its own name and cannot rename
    # on the way, so a renamed output (single-file mode adds a rule suffix) has
    # to go through the stdlib copy even on Windows.
    if robocopy_available() and input_file.name == output_file.name:
        return copy_video_with_robocopy(input_file, output_file, overwrite, total_started_at)

    copy_file_with_progress(input_file, output_file, total_started_at)
    if not output_file.exists():
        raise OSError("the copied file is missing after the copy finished")
    return 0


def copy_video_with_robocopy(
    input_file: Path,
    output_file: Path,
    overwrite: bool,
    total_started_at: Optional[float] = None,
) -> int:
    before = destination_snapshot([output_file])

    if overwrite and output_file.exists():
        # Robocopy decides for itself whether a destination is "the same" from
        # size and timestamp, and skips it even with /IS /IT (measured). Clearing
        # the destination first is the only way to make overwrite mean overwrite.
        output_file.unlink()

    args = [
        ROBOCOPY_BIN,
        str(input_file.parent),
        str(output_file.parent),
        input_file.name,
        "/R:1",
        "/W:1",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
        "/J",
    ]
    args.extend(robocopy_overwrite_flags(overwrite))

    proc = run_with_progress(args, total_started_at)

    after = destination_snapshot([output_file])
    if not robocopy_success(proc.returncode):
        raise OSError(f"robocopy failed with exit code {proc.returncode}")
    if output_file not in after:
        raise OSError("robocopy did not create the output file")
    if before and before.get(output_file) == after.get(output_file):
        LOGGER.info("Destination was already identical: %s", output_file)

    return proc.returncode


def copy_extra_files(input_root: Path, output_root: Path, rules: SelectionRules) -> Tuple[int, int, int]:
    if input_root.is_file():
        return 0, 0, 0

    sources = extra_file_sources(input_root, output_root)
    if not sources:
        return 0, 0, 0

    if robocopy_available():
        return copy_extra_files_with_robocopy(sources, input_root, output_root, rules)
    return copy_extra_files_with_stdlib(sources, input_root, output_root, rules)


def copy_extra_files_with_stdlib(
    sources: Sequence[Path],
    input_root: Path,
    output_root: Path,
    rules: SelectionRules,
) -> Tuple[int, int, int]:
    copied = 0
    skipped = 0
    failed = 0

    for source in sources:
        try:
            destination = output_root / source.relative_to(input_root)
        except ValueError:
            continue

        if destination.exists() and not rules.overwrite:
            skipped += 1
            continue

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy_file_with_progress(source, destination)
            copied += 1
        except OSError as exc:
            LOGGER.error("Could not copy %s -> %s: %s", source, destination, exc)
            failed += 1

    LOGGER.info("Extra files copied with stdlib: copied=%s skipped=%s failed=%s", copied, skipped, failed)
    if failed:
        print(err(f"{failed} non-video file(s) could not be copied."))
    return copied, skipped, failed


def copy_extra_files_with_robocopy(
    sources: Sequence[Path],
    input_root: Path,
    output_root: Path,
    rules: SelectionRules,
) -> Tuple[int, int, int]:
    destinations: List[Path] = []
    for source in sources:
        try:
            destinations.append(output_root / source.relative_to(input_root))
        except ValueError:
            pass

    before = destination_snapshot(destinations)

    args = [
        ROBOCOPY_BIN,
        str(input_root),
        str(output_root),
        "/E",
        "/R:1",
        "/W:1",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
        "/XF",
    ]
    args.extend(f"*{suffix}" for suffix in sorted(VIDEO_EXTENSIONS))

    if path_is_under(output_root, input_root):
        args.extend(["/XD", str(output_root)])

    args.extend(robocopy_overwrite_flags(rules.overwrite))

    proc = run_command(args, timeout=None)

    after = destination_snapshot(destinations)
    copied = 0
    skipped = 0
    failed = 0

    for destination in destinations:
        before_stat = before.get(destination)
        after_stat = after.get(destination)
        if after_stat is None:
            failed += 1
        elif before_stat is None or after_stat != before_stat:
            copied += 1
        else:
            skipped += 1

    if not robocopy_success(proc.returncode):
        failed = max(failed, 1)
        LOGGER.error("robocopy failed with exit code %s", proc.returncode)
        print(err(f"robocopy failed while copying non-video files. Exit code: {proc.returncode}"))
    else:
        LOGGER.info(
            "Extra files copied with robocopy: copied=%s skipped=%s failed=%s rc=%s",
            copied,
            skipped,
            failed,
            proc.returncode,
        )

    return copied, skipped, failed
