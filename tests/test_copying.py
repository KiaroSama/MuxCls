"""Data-safety tests for the stdlib copy backend (muxcls.copying).

This backend is the only one on Linux/macOS, and it also runs on Windows whenever
the output is renamed, so a failed copy here must never damage what is already on
disk.
"""
import os
import stat

import pytest

from muxcls import copying
from muxcls.constants import AUDIO_ALL, SUBTITLE_ALL
from muxcls.models import SelectionRules

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
