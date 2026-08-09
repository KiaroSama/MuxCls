from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence

from .constants import AUDIO_NONE
from .colors import ACTION_SEPARATOR_COLOR, C, PROCESS_DONE_COLOR, PROCESS_SEPARATOR_COLOR, color, dim, err, info, warn
from .logsetup import LOGGER
from .models import MediaFile, SelectionRules
from .textutil import center_for_terminal, format_elapsed_time, format_language_list, format_size_difference, format_stream_size, separator_line
from .media import find_video_files, run_with_progress, scan_files
from .muxlogic import build_ffmpeg_command, remux_needed_reasons, selected_audio_streams, selected_subtitle_streams
from .output import display_path, make_output_path, path_total_size
from .copying import copy_extra_files, copy_video_without_remux
from .reporting import print_header


class ProcessSummary(NamedTuple):
    """What a processing run did. Returned so callers (and tests) can check the
    outcome instead of parsing console output."""

    total: int
    succeeded: int
    remuxed: int
    copied_unchanged: int
    skipped: int
    no_audio: int
    failed: int
    extra_copied: int
    extra_skipped: int
    extra_failed: int
    size_delta: int
    elapsed: float
    results: List[Dict[str, str]]


def append_file_result(
    results: List[Dict[str, str]],
    index: int,
    total: int,
    action: str,
    status: str,
    input_file: Path,
    output_file: Optional[Path],
    detail: str,
    elapsed_seconds: float,
    returncode: Optional[int] = None,
    size_delta: Optional[int] = None,
    log_name: Optional[str] = None,
) -> None:
    result = {
        "index": f"{index}/{total}",
        "action": action,
        "status": status,
        "input": str(input_file),
        "output": str(output_file) if output_file else "-",
        "detail": detail or "-",
        "returncode": str(returncode) if returncode is not None else "-",
        "elapsed": format_elapsed_time(elapsed_seconds),
        "size_delta": format_size_difference(size_delta) if size_delta is not None else "-",
    }
    results.append(result)

    # The log records the path relative to the roots, which are logged once when
    # the run starts. Full paths on every line make a long run unreadable.
    message = (
        f"{result['index']} {status} {action} | {log_name or input_file} | "
        f"size={result['size_delta']} | elapsed={result['elapsed']} | "
        f"rc={result['returncode']} | {result['detail']}"
    )

    if status == "FAILED":
        LOGGER.error(message)
    elif status in {"SKIPPED", "NO_AUDIO_MATCH", "WARNING"}:
        LOGGER.warning(message)
    else:
        LOGGER.info(message)


def print_file_size_change(input_file: Path, output_file: Path) -> int:
    """Show what this one file gained or lost, right after it finishes."""
    before = path_total_size(input_file)
    after = path_total_size(output_file)
    delta = after - before
    print(color(
        f"          size {format_stream_size(before)} -> {format_stream_size(after)}"
        f" ({format_size_difference(delta)})",
        C.SUMMARY_SIZE_DIFF,
    ))
    return delta


def process_files(
    media_files: List[MediaFile],
    input_root: Path,
    output_root: Path,
    rules: SelectionRules,
    probe_failures: Sequence[Path] = (),
) -> ProcessSummary:
    print_header("Processing Files")
    print()
    run_started_at = time.perf_counter()
    probe_failures = list(probe_failures)
    total = len(media_files) + len(probe_failures)
    LOGGER.info(
        "Processing started: input=%s output=%s files=%s probe_failures=%s",
        input_root,
        output_root,
        len(media_files),
        len(probe_failures),
    )
    LOGGER.debug("Rules: %s", rules)

    succeeded = 0
    skipped = 0
    no_audio = 0
    failed = 0
    copied_unchanged = 0
    remuxed = 0
    output_files_for_size: List[Path] = []
    file_results: List[Dict[str, str]] = []
    index = 0

    # Files that could not be probed are part of this run's totals; they are
    # reported first so nothing discovered on disk silently disappears.
    for failure in probe_failures:
        index += 1
        print(err(f"[{index}/{total}] FAILED to scan: {display_path(input_root, failure)}"))
        failed += 1
        append_file_result(
            file_results, index, total, "probe", "FAILED", failure, None,
            "ffprobe could not read this file", 0.0,
        )

    for media in media_files:
        index += 1
        input_file = media.path
        rel = display_path(input_root, input_file)
        file_started_at = time.perf_counter()
        if index > 1:
            print(separator_line(PROCESS_SEPARATOR_COLOR))

        def finish(action: str, status: str, out: Optional[Path], detail: str,
                   returncode: Optional[int] = None, size_delta: Optional[int] = None) -> None:
            append_file_result(
                file_results, index, total, action, status, input_file, out, detail,
                time.perf_counter() - file_started_at, returncode, size_delta, str(rel),
            )

        # A file with a video extension but no video stream is invalid input, not
        # a rule mismatch: reject it before anything is copied or remuxed.
        if not media.video_streams:
            print(err(f"[{index}/{total}] FAILED: no video stream found: {rel}"))
            LOGGER.error("No video stream found: %s", input_file)
            failed += 1
            finish("validate", "FAILED", None, "no video stream found")
            continue

        try:
            output_file = make_output_path(input_root, output_root, input_file, rules)
        except RuntimeError as exc:
            print(err(f"[{index}/{total}] FAILED: {exc}"))
            LOGGER.exception("Could not resolve output path for %s", input_file)
            failed += 1
            finish("resolve-output", "FAILED", None, str(exc))
            continue

        audio_keep = selected_audio_streams(media, rules)
        if rules.audio_mode != AUDIO_NONE and not audio_keep:
            print(warn(f"[{index}/{total}] SKIP no matching audio selected: {rel}"))
            LOGGER.warning("No matching audio selected: %s", input_file)
            no_audio += 1
            finish("select-audio", "NO_AUDIO_MATCH", output_file,
                   "selected audio rule matched no audio streams")
            continue

        if output_file.exists() and not rules.overwrite:
            print(warn(f"[{index}/{total}] SKIP exists: {rel}"))
            LOGGER.warning("Skip existing output: %s", output_file)
            skipped += 1
            finish("skip-existing", "SKIPPED", output_file,
                   "output already exists and overwrite is disabled")
            continue

        subtitles_keep = selected_subtitle_streams(media, rules)
        reasons = remux_needed_reasons(media, rules, audio_keep, subtitles_keep)

        if not reasons:
            print(info(f"[{index}/{total}] Copying unchanged: {rel}"))
            print(dim("          no remux needed"))
            try:
                copy_returncode = copy_video_without_remux(
                    input_file, output_file, rules.overwrite, run_started_at
                )
            except OSError as exc:
                failed += 1
                LOGGER.exception("Could not copy unchanged video %s -> %s", input_file, output_file)
                print(err(f"          FAILED to copy unchanged file: {exc}"))
                finish("copy-unchanged", "FAILED", output_file, str(exc))
                continue

            succeeded += 1
            copied_unchanged += 1
            output_files_for_size.append(output_file)
            delta = print_file_size_change(input_file, output_file)
            finish("copy-unchanged", "OK", output_file, "no remux needed", copy_returncode, delta)
            print(color(center_for_terminal("Done"), PROCESS_DONE_COLOR))
            continue

        cmd, audio_keep, subtitles_keep = build_ffmpeg_command(input_file, output_file, media, rules)
        print(info(f"[{index}/{total}] Remuxing: {rel}"))
        print(dim(
            f"          audio kept: {len(audio_keep)} | subtitles kept: {len(subtitles_keep)}"
            f" | attachments: {'yes' if rules.keep_attachments else 'no'}"
        ))
        LOGGER.info(
            "%s/%s remux %s | audio=%s subtitles=%s attachments=%s",
            index, total, rel,
            [s.index for s in audio_keep], [s.index for s in subtitles_keep],
            rules.keep_attachments,
        )

        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            failed += 1
            LOGGER.exception("Could not create output folder for %s", output_file)
            print(err(f"          FAILED to create output folder: {exc}"))
            finish("prepare-output", "FAILED", output_file, str(exc))
            continue

        proc = run_with_progress(cmd, run_started_at)

        if proc.returncode == 0:
            succeeded += 1
            remuxed += 1
            output_files_for_size.append(output_file)
            delta = print_file_size_change(input_file, output_file)
            finish("remux", "OK", output_file, "; ".join(reasons), proc.returncode, delta)
            print(color(center_for_terminal("Done"), PROCESS_DONE_COLOR))
        else:
            failed += 1
            LOGGER.error("Remux failed: %s | returncode=%s", input_file, proc.returncode)
            print(err("          FAILED"))
            if proc.stderr.strip():
                print(proc.stderr.strip())
            finish("remux", "FAILED", output_file,
                   f"ffmpeg return code {proc.returncode}", proc.returncode)

    if rules.copy_non_video_files:
        extra_copied, extra_skipped, extra_failed = copy_extra_files(input_root, output_root, rules)
    else:
        extra_copied, extra_skipped, extra_failed = 0, 0, 0
        LOGGER.debug("Non-video file copy skipped by user setting")

    elapsed = time.perf_counter() - run_started_at
    if input_root.is_dir():
        original_total_size = path_total_size(input_root, exclude_paths=[output_root])
        output_total_size = path_total_size(output_root)
    else:
        original_total_size = path_total_size(input_root)
        output_total_size = sum(path_total_size(path) for path in output_files_for_size)
    size_delta = output_total_size - original_total_size

    summary = ProcessSummary(
        total=total,
        succeeded=succeeded,
        remuxed=remuxed,
        copied_unchanged=copied_unchanged,
        skipped=skipped,
        no_audio=no_audio,
        failed=failed,
        extra_copied=extra_copied,
        extra_skipped=extra_skipped,
        extra_failed=extra_failed,
        size_delta=size_delta,
        elapsed=elapsed,
        results=file_results,
    )
    print_run_summary(summary, output_root)
    return summary


def print_run_summary(summary: ProcessSummary, output_root: Path) -> None:
    formatted_size_delta = format_size_difference(summary.size_delta)

    print()
    print(separator_line(C.BOLD + C.DONE_HEADER))
    print(color(center_for_terminal("All Done"), C.BOLD + C.DONE_HEADER))
    print(separator_line(C.BOLD + C.DONE_HEADER))

    print(color(f"Total:   {summary.total}", C.BOLD + C.LAVENDER))
    print(color(f"OK:      {summary.succeeded}", C.BOLD + C.GREEN))
    print(color(f"Remuxed: {summary.remuxed}", C.BOLD + C.AZURE))
    print(color(f"Copied unchanged: {summary.copied_unchanged}", C.BOLD + C.MINT))
    print(color(f"Skipped: {summary.skipped}", C.BOLD + C.AMBER))
    print(color(f"No audio match: {summary.no_audio}", C.BOLD + C.YELLOW))
    print(color(f"Failed:  {summary.failed}", C.BOLD + C.SUMMARY_FAILED))
    print(color(f"Extra files copied:  {summary.extra_copied}", C.BOLD + C.AQUA))
    print(color(f"Extra files skipped: {summary.extra_skipped}", C.BOLD + C.GOLD))
    print(color(f"Extra files failed:  {summary.extra_failed}", C.BOLD + C.SUMMARY_EXTRA_FAILED))
    print(color(f"Output:  {output_root}", C.BOLD + C.SKY))
    print(color(f"Size difference: {formatted_size_delta}", C.BOLD + C.SUMMARY_SIZE_DIFF))
    print(color(f"Elapsed {format_elapsed_time(summary.elapsed)}", C.BOLD + C.SUMMARY_ELAPSED))

    LOGGER.info(
        "Processing done: total=%s ok=%s remuxed=%s copied_unchanged=%s skipped=%s "
        "no_audio_match=%s failed=%s extra_copied=%s extra_skipped=%s extra_failed=%s "
        "size_difference=%s size_delta_bytes=%s elapsed=%s output=%s",
        summary.total,
        summary.succeeded,
        summary.remuxed,
        summary.copied_unchanged,
        summary.skipped,
        summary.no_audio,
        summary.failed,
        summary.extra_copied,
        summary.extra_skipped,
        summary.extra_failed,
        formatted_size_delta,
        summary.size_delta,
        format_elapsed_time(summary.elapsed),
        output_root,
    )


def print_ready_for_next_task(message: str = "Task complete. Ready for next task.") -> None:
    print()
    print(separator_line(ACTION_SEPARATOR_COLOR))
    print(color(center_for_terminal(message), PROCESS_DONE_COLOR))
    print(separator_line(ACTION_SEPARATOR_COLOR))
    print()


def verify_output(root: Path, rules: Optional[SelectionRules] = None) -> None:
    print_header("Verify Output Folder")

    files = find_video_files(root)
    if not files:
        print(warn("No video files found."))
        return

    scan = scan_files(files)
    if scan.failures:
        print(err(f"{len(scan.failures)} output file(s) could not be read back:"))
        for path in scan.failures:
            print(err(f"  {display_path(root, path)}"))

    for media in scan.files:
        rel = display_path(root, media.path)

        video_count = len(media.video_streams)
        audio_count = len(media.audio_streams)
        subtitle_count = len(media.subtitle_streams)
        attachment_count = len(media.attachment_streams)

        audio_expected = rules is None or rules.audio_mode != AUDIO_NONE
        status_color = C.GREEN if video_count >= 1 and (audio_count >= 1 or not audio_expected) else C.YELLOW
        audio_langs = format_language_list((s.language for s in media.audio_streams), status_color) if audio_count else "-"
        subtitle_langs = format_language_list((s.language for s in media.subtitle_streams), status_color) if subtitle_count else "-"
        print(
            color(f"{rel} | video={video_count} | audio={audio_count} [", status_color)
            + audio_langs
            + color(f"] | subs={subtitle_count} [", status_color)
            + subtitle_langs
            + color(f"] | attachments={attachment_count}", status_color)
        )
