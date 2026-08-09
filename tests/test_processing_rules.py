"""Unit tests for the per-file decisions process_files makes before it ever
shells out to ffmpeg/robocopy: no-audio-match handling (B-02), probe failures
carried into the totals (B-05) and rejection of files without a video stream
(B-06). None of these paths run an external tool, so they need no fixtures.
"""
import subprocess
from pathlib import Path

import pytest

from muxcls import processing
from muxcls.constants import AUDIO_ALL, AUDIO_BY_LANGUAGE, AUDIO_NONE, SUBTITLE_ALL
from muxcls.models import MediaFile, SelectionRules, StreamInfo


def _rules(**overrides) -> SelectionRules:
    base = dict(
        audio_mode=AUDIO_ALL,
        audio_languages=[],
        audio_titles=[],
        audio_indexes=[],
        subtitle_mode=SUBTITLE_ALL,
        subtitle_languages=[],
        subtitle_titles=[],
        subtitle_indexes=[],
        keep_attachments=True,
        keep_metadata=True,
        keep_chapters=True,
        overwrite=False,
        copy_non_video_files=False,
    )
    base.update(overrides)
    return SelectionRules(**base)


@pytest.fixture
def series(tmp_path):
    folder = tmp_path / "Series"
    folder.mkdir()
    return folder


def _placeholder(folder: Path, name: str) -> Path:
    path = folder / name
    path.write_bytes(b"placeholder")
    return path


def test_video_only_file_is_skipped_as_no_audio_match(series, tmp_path):
    # B-02: a file with zero audio streams must not silently pass through when
    # the user asked for audio; only AUDIO_NONE may continue without audio.
    path = _placeholder(series, "video_only.mkv")
    media = MediaFile(path=path, streams=[StreamInfo(index=0, codec_type="video")])

    summary = processing.process_files([media], series, tmp_path / "Out", _rules())

    assert summary.no_audio == 1
    assert summary.succeeded == 0
    assert [r["status"] for r in summary.results] == ["NO_AUDIO_MATCH"]


def test_audio_none_still_processes_a_video_only_file(series, tmp_path):
    # B-02: explicit AUDIO_NONE is the one mode allowed to continue without audio.
    path = _placeholder(series, "video_only.mkv")
    media = MediaFile(path=path, streams=[StreamInfo(index=0, codec_type="video")])

    summary = processing.process_files(
        [media], series, tmp_path / "Out", _rules(audio_mode=AUDIO_NONE)
    )

    assert summary.no_audio == 0


def test_file_without_video_stream_is_a_validation_failure(series, tmp_path):
    # B-06: audio-only input is unsupported; it must fail before copy/remux and
    # must never be counted as a successful output.
    path = _placeholder(series, "audio_only.mkv")
    media = MediaFile(path=path, streams=[
        StreamInfo(index=0, codec_type="audio", language="jpn"),
    ])

    summary = processing.process_files([media], series, tmp_path / "Out", _rules())

    assert summary.failed == 1
    assert summary.succeeded == 0
    assert summary.results[0]["status"] == "FAILED"
    assert "video" in summary.results[0]["detail"].lower()


def test_streamless_file_is_a_validation_failure_not_a_no_audio_skip(series, tmp_path):
    # B-06 outranks B-02: a file with no streams at all is invalid input, not a
    # rule mismatch.
    path = _placeholder(series, "empty.mkv")
    media = MediaFile(path=path, streams=[])

    summary = processing.process_files([media], series, tmp_path / "Out", _rules())

    assert summary.failed == 1
    assert summary.no_audio == 0


# --- F-02 / F-03: a failed remux must leave no partial output and keep the old one ---

def _remuxable(path: Path) -> MediaFile:
    """Two audio languages so a jpn-only rule forces the remux path."""
    return MediaFile(path=path, streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="jpn"),
        StreamInfo(index=2, codec_type="audio", language="eng"),
    ])


def _failing_ffmpeg(monkeypatch, returncode=1, write_partial=True):
    """Stand in for FFmpeg: create the output file it was told to write, then fail."""
    seen = {}

    def fake(cmd, total_started_at=None, timeout=None, **_kw):
        seen["cmd"] = cmd
        seen["timeout"] = timeout
        target = Path(cmd[-1])
        if write_partial:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"HALF WRITTEN")
        return subprocess.CompletedProcess(cmd, returncode, "", "forced failure")

    monkeypatch.setattr(processing, "run_with_progress", fake)
    return seen


def test_failed_remux_leaves_no_partial_output(series, tmp_path, monkeypatch):
    media = _remuxable(_placeholder(series, "E01.mkv"))
    _failing_ffmpeg(monkeypatch)
    out_root = tmp_path / "Out"

    summary = processing.process_files(
        [media], series, out_root, _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"])
    )

    assert summary.failed == 1
    leftovers = [p.name for p in out_root.rglob("*") if p.is_file()]
    assert leftovers == [], f"a failed remux left files behind: {leftovers}"


def test_failed_remux_preserves_a_pre_existing_output(series, tmp_path, monkeypatch):
    media = _remuxable(_placeholder(series, "E01.mkv"))
    out_root = tmp_path / "Out"
    existing = out_root / "E01.mkv"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"PREVIOUS GOOD OUTPUT")
    _failing_ffmpeg(monkeypatch)

    summary = processing.process_files(
        [media], series, out_root,
        _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"], overwrite=True),
    )

    assert summary.failed == 1
    assert existing.read_bytes() == b"PREVIOUS GOOD OUTPUT"


def test_remux_runs_under_a_timeout(series, tmp_path, monkeypatch):
    # F-03: the real FFmpeg caller must pass a bound, not None.
    media = _remuxable(_placeholder(series, "E01.mkv"))
    seen = _failing_ffmpeg(monkeypatch)

    processing.process_files(
        [media], series, tmp_path / "Out",
        _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"]),
    )

    assert seen["timeout"] is not None and seen["timeout"] > 0


def test_probe_failures_are_counted_in_totals_and_results(series, tmp_path):
    # B-05: a file whose ffprobe failed must not vanish from the run totals.
    good = _placeholder(series, "good.mkv")
    broken = _placeholder(series, "broken.mkv")
    media = MediaFile(path=good, streams=[StreamInfo(index=0, codec_type="video")])

    summary = processing.process_files(
        [media], series, tmp_path / "Out", _rules(audio_mode=AUDIO_NONE),
        probe_failures=[broken],
    )

    assert summary.total == 2
    assert summary.failed == 1
    assert any(r["input"] == str(broken) for r in summary.results)
