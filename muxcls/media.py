from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence

from .constants import (
    FFPROBE_BIN,
    PROBE_TIMEOUT_SECONDS,
    PROCESS_KILL_GRACE_SECONDS,
    PROGRESS_POLL_SECONDS,
    TIMEOUT_RETURNCODE,
    VIDEO_EXTENSIONS,
)
from .colors import err, info
from .logsetup import LOGGER, command_to_text, log_command_output
from .models import MediaFile, StreamInfo
from .textutil import ProgressPrinter


class ScanResult(NamedTuple):
    """Everything a scan found: the files that probed cleanly and the ones that
    did not. Failures are returned rather than dropped so the caller decides."""

    files: List[MediaFile]
    failures: List[Path]


def terminate_process(proc: subprocess.Popen, grace_seconds: float = PROCESS_KILL_GRACE_SECONDS) -> None:
    """Stop a child process we own: ask it to exit, then kill it if it will not.
    Safe to call on a process that has already finished."""
    if proc.poll() is not None:
        return

    try:
        proc.terminate()
        proc.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        LOGGER.warning("Process %s ignored terminate; killing it", proc.pid)
    except OSError as exc:
        LOGGER.warning("Could not terminate process %s: %s", proc.pid, exc)
        return

    try:
        proc.kill()
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        LOGGER.error("Process %s is still alive after kill", proc.pid)
    except OSError as exc:
        LOGGER.warning("Could not kill process %s: %s", proc.pid, exc)


def run_command(
    args: Sequence[str],
    timeout: Optional[float] = PROBE_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    """Run a short command to completion. A timeout is a controlled failure, not
    a hang: subprocess.run kills the child before raising."""
    LOGGER.debug("Command: %s", command_to_text(args))
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        LOGGER.error("Command timed out after %ss: %s", timeout, command_to_text(args))
        return subprocess.CompletedProcess(
            list(args),
            TIMEOUT_RETURNCODE,
            exc.stdout or "",
            f"Command timeout after {timeout} seconds",
        )

    log_command_output(Path(args[0]).name, proc.returncode, proc.stdout, proc.stderr)
    return proc


def run_with_progress(
    args: Sequence[str],
    total_started_at: Optional[float] = None,
    timeout: Optional[float] = None,
) -> subprocess.CompletedProcess:
    """Run a long command while showing its own elapsed timer.

    The child is always reaped: on timeout, on Ctrl+C and on any other error it
    is terminated (then killed) before this function returns or re-raises, so a
    result is never reported while the process is still writing output.
    """
    LOGGER.debug("Command: %s", command_to_text(args))
    progress = ProgressPrinter(total_started_at)
    label = Path(args[0]).name

    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stdout_file, \
                tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stderr_file:
            try:
                proc = subprocess.Popen(
                    args,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    stdin=subprocess.DEVNULL,
                    text=True,
                )
            except OSError as exc:
                LOGGER.error("Could not start %s: %s", label, exc)
                return subprocess.CompletedProcess(list(args), 1, "", str(exc))

            timed_out = False
            try:
                while proc.poll() is None:
                    progress.tick()
                    if timeout is not None and time.perf_counter() - progress.started_at > timeout:
                        timed_out = True
                        LOGGER.error("%s exceeded its %ss timeout; stopping it", label, timeout)
                        break
                    time.sleep(PROGRESS_POLL_SECONDS)
                else:
                    progress.tick(force=True)
            finally:
                terminate_process(proc)
                progress.close()

            returncode = proc.wait()
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read()
            stderr = stderr_file.read()
    except OSError as exc:
        LOGGER.exception("Failed to capture output of %s", label)
        return subprocess.CompletedProcess(list(args), 1, "", str(exc))

    if timed_out:
        return subprocess.CompletedProcess(
            list(args),
            TIMEOUT_RETURNCODE,
            stdout,
            f"{stderr}\nCommand timeout after {timeout} seconds".strip(),
        )

    log_command_output(label, returncode, stdout, stderr)
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


def require_tool(binary: str) -> bool:
    found = shutil.which(binary)
    if found:
        LOGGER.debug("Tool check: %s -> %s", binary, found)
    else:
        LOGGER.error("Required tool not found in PATH: %s", binary)
    return found is not None


def find_video_files(input_path: Path) -> List[Path]:
    files: List[Path] = []

    if input_path.is_file():
        if input_path.suffix.lower() in VIDEO_EXTENSIONS:
            return [input_path]
        return []

    for path in input_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            files.append(path)

    return sorted(files, key=lambda p: str(p).lower())


def find_non_video_extensions(input_path: Path) -> List[str]:
    extensions = set()

    if input_path.is_file():
        suffix = input_path.suffix.lower() or "[no extension]"
        if suffix not in VIDEO_EXTENSIONS:
            return [suffix]
        return []

    for path in input_path.rglob("*"):
        if path.is_file():
            suffix = path.suffix.lower() or "[no extension]"
            if suffix not in VIDEO_EXTENSIONS:
                extensions.add(suffix)

    return sorted(extensions)


def probe_file(path: Path) -> Optional[MediaFile]:
    args = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,codec_name,channels,duration,bit_rate:stream_tags:stream_disposition=default",
        "-of",
        "json",
        str(path),
    ]

    # Probing is a metadata read; if it has not answered in two minutes the file
    # or the drive is the problem, and waiting longer will not help.
    proc = run_command(args, timeout=PROBE_TIMEOUT_SECONDS)

    if proc.returncode != 0:
        LOGGER.error("Probe failed for %s", path)
        print(err(f"[PROBE FAILED] {path}"))
        if proc.stderr.strip():
            print(proc.stderr.strip())
        return None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        LOGGER.error("Probe returned invalid JSON for %s", path)
        print(err(f"[PROBE FAILED] Invalid JSON from ffprobe: {path}"))
        return None

    raw_streams = data.get("streams") or []
    if not isinstance(raw_streams, list):
        LOGGER.error("Probe returned invalid streams data for %s: %r", path, raw_streams)
        print(err(f"[PROBE FAILED] Invalid streams data from ffprobe: {path}"))
        return None

    streams = [StreamInfo.from_ffprobe(s) for s in raw_streams if isinstance(s, dict)]
    LOGGER.debug(
        "Probe OK: %s | video=%s audio=%s subtitle=%s attachment=%s",
        path,
        sum(1 for s in streams if s.codec_type == "video"),
        sum(1 for s in streams if s.codec_type == "audio"),
        sum(1 for s in streams if s.codec_type == "subtitle"),
        sum(1 for s in streams if s.codec_type == "attachment"),
    )
    return MediaFile(path=path, streams=streams)


def scan_files(files: List[Path]) -> ScanResult:
    scanned: List[MediaFile] = []
    failures: List[Path] = []
    LOGGER.info("Scanning %s file(s)", len(files))

    for i, file_path in enumerate(files, start=1):
        print(info(f"[{i}/{len(files)}] Scanning: {file_path.name}"))
        media = probe_file(file_path)
        if media:
            scanned.append(media)
        else:
            failures.append(file_path)

    LOGGER.info("Scan complete: probed=%s failed=%s of %s", len(scanned), len(failures), len(files))
    for path in failures:
        LOGGER.error("Probe failed: %s", path)
    return ScanResult(scanned, failures)
