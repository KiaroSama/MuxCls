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


# --- progress source: real material can report out_time_us=N/A -------------

# Copied verbatim from `ffmpeg -progress pipe:1` on a real HEVC/Opus release
# (Sword Art Online S01E01). Every block reported N/A for the timestamp while
# total_size counted up normally.
FFMPEG_BLOCK_WITHOUT_TIMESTAMP = (
    "frame=17944\nfps=0.00\nstream_0_0_q=-1.0\nbitrate=N/A\ntotal_size=244318208\n"
    "out_time_us=N/A\nout_time_ms=N/A\nout_time=N/A\ndup_frames=0\ndrop_frames=0\n"
    "speed=N/A\nprogress=continue\n"
)


def test_a_remux_that_reports_no_timestamp_still_advances(series, tmp_path, monkeypatch):
    """Without the byte fallback the bar sits at 0% for the whole file and then
    jumps to 100%, which reads as a stuck job on a multi-GB remux."""
    source = _placeholder(series, "E01.mkv")
    media = _remuxable(source)
    rows = []

    def fake(cmd, total_started_at=None, timeout=None, on_output=None, **_kw):
        if on_output is not None:
            on_output(FFMPEG_BLOCK_WITHOUT_TIMESTAMP)
        target = Path(cmd[-1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"remuxed")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    real_view = processing.ProgressView

    class Recording(real_view):
        def update(self, index, percent=None, completed=None):
            rows.append((percent, completed))
            super().update(index, percent=percent, completed=completed)

    monkeypatch.setattr(processing, "run_with_progress", fake)
    monkeypatch.setattr(processing, "ProgressView", Recording)

    processing.process_files(
        [media], series, tmp_path / "Out",
        _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"]),
    )

    assert rows == [(None, 244318208)], "the byte count is the only figure that moves here"


def test_a_remux_that_reports_a_timestamp_still_prefers_it(series, tmp_path, monkeypatch):
    # The fallback must not take over when FFmpeg does report a position:
    # a timeline percentage is accurate, a byte ratio only approximates it.
    source = _placeholder(series, "E01.mkv")
    media = _remuxable(source)
    media.duration_seconds = 100.0          # 25 s of it is 25%
    seen = []

    def fake(cmd, total_started_at=None, timeout=None, on_output=None, **_kw):
        if on_output is not None:
            on_output("total_size=1000\nout_time_us=25000000\nprogress=continue\n")
        target = Path(cmd[-1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"remuxed")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    class Recording(processing.ProgressView):
        def update(self, index, percent=None, completed=None):
            seen.append((percent, completed))
            super().update(index, percent=percent, completed=completed)

    monkeypatch.setattr(processing, "run_with_progress", fake)
    monkeypatch.setattr(processing, "ProgressView", Recording)

    processing.process_files(
        [media], series, tmp_path / "Out",
        _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"]),
    )

    assert seen == [(25.0, None)]
