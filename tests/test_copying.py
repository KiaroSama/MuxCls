"""Data-safety tests for the stdlib copy backend (muxcls.copying).

This backend is the only one on Linux/macOS, and it also runs on Windows whenever
the output is renamed, so a failed copy here must never damage what is already on
disk.
"""
import itertools
import os
import stat
import subprocess

import pytest

from muxcls import copying
from muxcls.constants import AUDIO_ALL, SUBTITLE_ALL
from muxcls.models import SelectionRules
from muxcls.output import partial_path

EXISTING = b"PREVIOUS GOOD OUTPUT"


@pytest.fixture
def readable_source(tmp_path):
    source = tmp_path / "src.mkv"
    source.write_bytes(b"real content" * 100)
    return source


def test_failed_copy_leaves_an_existing_destination_untouched(tmp_path):
    # The copy fails before a single byte is written; the previous run's output
    # must survive that.
    destination = tmp_path / "out.mkv"
    destination.write_bytes(EXISTING)

    with pytest.raises(OSError):
        copying.copy_file_with_progress(tmp_path / "does_not_exist.mkv", destination)

    assert destination.read_bytes() == EXISTING


def test_failed_copy_leaves_no_leftover_files_behind(tmp_path):
    destination = tmp_path / "out.mkv"
    destination.write_bytes(EXISTING)

    with pytest.raises(OSError):
        copying.copy_file_with_progress(tmp_path / "does_not_exist.mkv", destination)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.mkv"]


def test_copy_does_not_make_its_output_read_only(readable_source, tmp_path):
    # A read-only source must not produce a read-only output, or the next run
    # with overwrite on cannot replace it.
    destination = tmp_path / "out.mkv"
    readable_source.chmod(stat.S_IREAD)
    try:
        copying.copy_file_with_progress(readable_source, destination)
        assert os.access(destination, os.W_OK), "output inherited the read-only source mode"
    finally:
        readable_source.chmod(stat.S_IWRITE | stat.S_IREAD)


def test_overwrite_rerun_succeeds_for_a_read_only_source(readable_source, tmp_path):
    destination = tmp_path / "out.mkv"
    readable_source.chmod(stat.S_IREAD)
    try:
        copying.copy_file_with_progress(readable_source, destination)
        copying.copy_file_with_progress(readable_source, destination)
        assert destination.read_bytes() == readable_source.read_bytes()
    finally:
        readable_source.chmod(stat.S_IWRITE | stat.S_IREAD)


def test_copy_preserves_content_and_modification_time(readable_source, tmp_path):
    destination = tmp_path / "out.mkv"
    copying.copy_file_with_progress(readable_source, destination)

    assert destination.read_bytes() == readable_source.read_bytes()
    assert destination.stat().st_mtime_ns == readable_source.stat().st_mtime_ns


# --- F-01: a failed robocopy overwrite must not destroy the previous output ---

WINDOWS_ONLY = pytest.mark.skipif(not copying.robocopy_available(),
                                  reason="robocopy not available (Windows only)")


@pytest.fixture
def same_name_pair(tmp_path):
    """Source and destination sharing a file name, so the robocopy path is taken."""
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()
    source = src_dir / "clip.mkv"
    source.write_bytes(b"NEW SOURCE CONTENT" * 50)
    return source, dst_dir / "clip.mkv"


@WINDOWS_ONLY
def test_failed_robocopy_overwrite_keeps_the_existing_destination(same_name_pair, monkeypatch):
    source, destination = same_name_pair
    destination.write_bytes(EXISTING)

    # 16 is robocopy's fatal-error code.
    monkeypatch.setattr(copying, "run_with_progress",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 16, "", "forced"))

    with pytest.raises(OSError):
        copying.copy_video_without_remux(source, destination, overwrite=True)

    assert destination.read_bytes() == EXISTING


@WINDOWS_ONLY
def test_cancelled_robocopy_overwrite_keeps_the_existing_destination(same_name_pair, monkeypatch):
    source, destination = same_name_pair
    destination.write_bytes(EXISTING)

    def cancel(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(copying, "run_with_progress", cancel)

    with pytest.raises(KeyboardInterrupt):
        copying.copy_video_without_remux(source, destination, overwrite=True)

    assert destination.read_bytes() == EXISTING


@WINDOWS_ONLY
def test_failed_robocopy_overwrite_leaves_no_staging_residue(same_name_pair, monkeypatch):
    source, destination = same_name_pair
    destination.write_bytes(EXISTING)
    monkeypatch.setattr(copying, "run_with_progress",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 16, "", "forced"))

    with pytest.raises(OSError):
        copying.copy_video_without_remux(source, destination, overwrite=True)

    assert sorted(p.name for p in destination.parent.iterdir()) == ["clip.mkv"]


@WINDOWS_ONLY
def test_successful_robocopy_overwrite_replaces_the_destination(same_name_pair):
    source, destination = same_name_pair
    destination.write_bytes(EXISTING)

    copying.copy_video_without_remux(source, destination, overwrite=True)

    assert destination.read_bytes() == source.read_bytes()
    assert sorted(p.name for p in destination.parent.iterdir()) == ["clip.mkv"]


# --- F-04: non-video overwrite must replace a newer destination ---

def _extra_rules(overwrite):
    return SelectionRules(
        audio_mode=AUDIO_ALL, audio_languages=[], audio_titles=[], audio_indexes=[],
        subtitle_mode=SUBTITLE_ALL, subtitle_languages=[], subtitle_titles=[],
        subtitle_indexes=[], keep_attachments=True, keep_metadata=True,
        keep_chapters=True, overwrite=overwrite,
    )


@pytest.fixture
def stale_extra(tmp_path):
    """A destination robocopy would skip: same size, newer timestamp, other bytes."""
    source_root = tmp_path / "in"
    source_root.mkdir()
    extra = source_root / "notes.txt"
    extra.write_text("REAL SOURCE TEXT", encoding="utf-8")

    output_root = tmp_path / "out"
    output_root.mkdir()
    destination = output_root / "notes.txt"
    destination.write_text("X" * len("REAL SOURCE TEXT"), encoding="utf-8")
    info = extra.stat()
    os.utime(destination, ns=(info.st_atime_ns + 600_000_000_000,
                              info.st_mtime_ns + 600_000_000_000))
    return extra, source_root, output_root, destination


def test_extra_overwrite_replaces_a_newer_destination(stale_extra):
    extra, source_root, output_root, destination = stale_extra
    assert destination.read_text(encoding="utf-8") != extra.read_text(encoding="utf-8")

    copied, skipped, failed = copying.copy_extra_files(source_root, output_root, _extra_rules(True))

    assert (copied, failed) == (1, 0)
    assert destination.read_text(encoding="utf-8") == "REAL SOURCE TEXT"


def test_extra_overwrite_replaces_a_same_size_same_time_destination(stale_extra):
    # Robocopy calls this destination "the same" and skips it; overwrite must not.
    extra, source_root, output_root, destination = stale_extra
    info = extra.stat()
    os.utime(destination, ns=(info.st_atime_ns, info.st_mtime_ns))
    assert destination.stat().st_size == extra.stat().st_size
    assert destination.stat().st_mtime_ns == extra.stat().st_mtime_ns

    copied, skipped, failed = copying.copy_extra_files(source_root, output_root, _extra_rules(True))

    assert failed == 0
    assert destination.read_text(encoding="utf-8") == "REAL SOURCE TEXT"


def test_extra_without_overwrite_keeps_the_existing_destination(stale_extra):
    extra, source_root, output_root, destination = stale_extra

    copied, skipped, failed = copying.copy_extra_files(source_root, output_root, _extra_rules(False))

    assert (copied, skipped, failed) == (0, 1, 0)
    assert destination.read_text(encoding="utf-8") != "REAL SOURCE TEXT"


# --- F-03: the stdlib copy is bounded too ---

def test_copy_file_with_progress_honours_a_timeout(tmp_path, monkeypatch):
    source = tmp_path / "big.mkv"
    source.write_bytes(b"x" * 4096)
    destination = tmp_path / "out.mkv"
    destination.write_bytes(EXISTING)
    # A fake clock instead of a race against the machine: every reading jumps
    # 100 seconds, so the deadline is passed on the first chunk no matter how
    # fast the runner is, and no matter how many readings precede it.
    ticks = itertools.count(0.0, 100.0)
    monkeypatch.setattr(copying.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(copying, "COPY_CHUNK_BYTES", 1)

    with pytest.raises(OSError):
        copying.copy_file_with_progress(source, destination, timeout=1.0)

    assert destination.read_bytes() == EXISTING
    assert not partial_path(destination).exists()


def test_copy_file_with_progress_completes_when_the_timeout_is_generous(tmp_path):
    # Guards the mirror image: the deadline must not fire on a normal copy.
    source = tmp_path / "small.mkv"
    source.write_bytes(b"payload" * 100)
    destination = tmp_path / "out.mkv"

    copying.copy_file_with_progress(source, destination, timeout=3600)

    assert destination.read_bytes() == source.read_bytes()
    assert not partial_path(destination).exists()


# --- F-03: extra-file copies are bounded and cancellable too ---

def test_extra_stdlib_copy_passes_the_operation_timeout(tmp_path, monkeypatch):
    source_root = tmp_path / "in"
    source_root.mkdir()
    (source_root / "notes.txt").write_text("hi", encoding="utf-8")
    seen = {}

    def fake(src, dst, total_started_at=None, timeout=None):
        seen["timeout"] = timeout
        dst.write_bytes(src.read_bytes())

    monkeypatch.setattr(copying, "copy_file_with_progress", fake)
    copying.copy_extra_files_with_stdlib(
        [source_root / "notes.txt"], source_root, tmp_path / "out", _extra_rules(True)
    )

    assert seen["timeout"] is not None and seen["timeout"] > 0


@WINDOWS_ONLY
def test_extra_robocopy_runs_under_a_cancellable_bounded_runner(tmp_path, monkeypatch):
    source_root = tmp_path / "in"
    source_root.mkdir()
    extra = source_root / "notes.txt"
    extra.write_text("hi", encoding="utf-8")
    output_root = tmp_path / "out"
    seen = {}

    def fake_progress(args, total_started_at=None, timeout=None):
        seen["args"] = args
        seen["timeout"] = timeout
        destination = output_root / "notes.txt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(extra.read_bytes())
        return subprocess.CompletedProcess(args, 1, "", "")

    monkeypatch.setattr(copying, "run_with_progress", fake_progress)

    copying.copy_extra_files_with_robocopy(
        [extra], source_root, output_root, _extra_rules(False)
    )

    assert seen["timeout"] is not None and seen["timeout"] > 0
    # run_command offers no progress loop and no interruption point for a long
    # tree copy, so this module must not reach for it at all.
    assert not hasattr(copying, "run_command")


@WINDOWS_ONLY
def test_failed_robocopy_extra_copy_removes_incomplete_files(tmp_path, monkeypatch):
    source_root = tmp_path / "in"
    source_root.mkdir()
    extra = source_root / "notes.txt"
    extra.write_text("COMPLETE SOURCE TEXT", encoding="utf-8")
    output_root = tmp_path / "out"

    def truncated_then_fail(args, total_started_at=None, timeout=None):
        destination = output_root / "notes.txt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("COMPLETE", encoding="utf-8")  # short = incomplete
        return subprocess.CompletedProcess(args, 8, "", "robocopy failure")

    monkeypatch.setattr(copying, "run_with_progress", truncated_then_fail)

    copied, skipped, failed = copying.copy_extra_files_with_robocopy(
        [extra], source_root, output_root, _extra_rules(False)
    )

    assert failed >= 1
    assert not (output_root / "notes.txt").exists(), "an incomplete copy was left behind"


@WINDOWS_ONLY
def test_cancelled_robocopy_extra_copy_removes_incomplete_files(tmp_path, monkeypatch):
    source_root = tmp_path / "in"
    source_root.mkdir()
    extra = source_root / "notes.txt"
    extra.write_text("COMPLETE SOURCE TEXT", encoding="utf-8")
    output_root = tmp_path / "out"

    def cancel(args, total_started_at=None, timeout=None):
        destination = output_root / "notes.txt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("COMP", encoding="utf-8")
        raise KeyboardInterrupt

    monkeypatch.setattr(copying, "run_with_progress", cancel)

    with pytest.raises(KeyboardInterrupt):
        copying.copy_extra_files_with_robocopy(
            [extra], source_root, output_root, _extra_rules(False)
        )

    assert not (output_root / "notes.txt").exists(), "cancellation left an incomplete copy"


def test_extra_file_copy_does_not_make_its_output_read_only(tmp_path):
    source_root = tmp_path / "in"
    source_root.mkdir()
    extra = source_root / "notes.txt"
    extra.write_text("hello", encoding="utf-8")
    extra.chmod(stat.S_IREAD)
    output_root = tmp_path / "out"
    rules = SelectionRules(
        audio_mode=AUDIO_ALL, audio_languages=[], audio_titles=[], audio_indexes=[],
        subtitle_mode=SUBTITLE_ALL, subtitle_languages=[], subtitle_titles=[],
        subtitle_indexes=[], keep_attachments=True, keep_metadata=True,
        keep_chapters=True, overwrite=True,
    )
    try:
        copied, _, failed = copying.copy_extra_files_with_stdlib(
            [extra], source_root, output_root, rules
        )
        assert (copied, failed) == (1, 0)
        assert os.access(output_root / "notes.txt", os.W_OK)
    finally:
        extra.chmod(stat.S_IWRITE | stat.S_IREAD)
