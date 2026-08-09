"""Real end-to-end tests through muxcls.processing.process_files, using actual
ffmpeg-generated fixtures. These exercise the remux path, the extra-file copy
path, verify_output, and the copy-unchanged path.

Requires ffmpeg/ffprobe in PATH. Skipped automatically if unavailable.
Every subprocess call is bounded so a broken fixture fails instead of hanging.
"""
import os
import shutil
import subprocess

import pytest

from muxcls import copying, media, output, processing
from muxcls.models import SelectionRules

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
ROBOCOPY_AVAILABLE = os.name == "nt" and shutil.which("robocopy") is not None
FIXTURE_TIMEOUT = 120

pytestmark = pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg/ffprobe not found in PATH")


def _rules(**overrides) -> SelectionRules:
    base = dict(
        audio_mode="4", audio_languages=[], audio_titles=[], audio_indexes=[],
        subtitle_mode="1", subtitle_languages=[], subtitle_titles=[], subtitle_indexes=[],
        keep_attachments=True, keep_metadata=True, keep_chapters=True, overwrite=True,
        copy_non_video_files=True,
    )
    base.update(overrides)
    return SelectionRules(**base)


def _run_ffmpeg(cmd):
    r = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        stdin=subprocess.DEVNULL, timeout=FIXTURE_TIMEOUT,
    )
    assert r.returncode == 0, r.stderr[-800:]


def _make_mkv(dst, srt_path, default_audio_index=None, default_subtitle_index=None):
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-f", "lavfi", "-i", "testsrc=size=128x72:rate=5:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
        "-i", str(srt_path),
        "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map", "3:s",
        "-c:s", "srt",
        "-metadata:s:a:0", "language=jpn",
        "-metadata:s:a:1", "language=eng",
        "-metadata:s:s:0", "language=eng",
    ]
    if default_audio_index is not None:
        cmd += [f"-disposition:a:{default_audio_index}", "default"]
    if default_subtitle_index is not None:
        cmd += [f"-disposition:s:{default_subtitle_index}", "default"]
    cmd += ["-shortest", str(dst)]
    _run_ffmpeg(cmd)


@pytest.fixture
def two_track_series(tmp_path):
    indir = tmp_path / "Series"
    indir.mkdir()
    srt = tmp_path / "sub.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    _make_mkv(indir / "E01.mkv", srt)
    _make_mkv(indir / "E02.mkv", srt)
    (indir / "readme.txt").write_text("not a video", encoding="utf-8")
    return indir


def test_remux_keeps_only_selected_audio_language_and_subs(two_track_series, tmp_path):
    scan = media.scan_files(sorted(two_track_series.glob("*.mkv")))
    assert len(scan.files) == 2
    assert scan.failures == []

    rules = _rules(audio_mode="1", audio_languages=["jpn"])
    out_root = output.resolve_output_root(two_track_series, tmp_path / "OutA", rules)
    summary = processing.process_files(scan.files, two_track_series, out_root, rules)

    assert summary.succeeded == 2
    outputs = sorted(out_root.rglob("*.mkv"))
    assert len(outputs) == 2
    for f in outputs:
        probed = media.probe_file(f)
        assert [s.language for s in probed.audio_streams] == ["jpn"]
        assert len(probed.subtitle_streams) == 1
    assert list(out_root.rglob("readme.txt")), "non-video file was not copied"

    # verify_output must run cleanly against real output.
    processing.verify_output(out_root, rules)


def test_second_audio_track_stays_default_after_remux(tmp_path):
    """B-01 end to end: the source default sits on the second audio track and on
    the *only* subtitle track; keeping everything must not move it."""
    indir = tmp_path / "Defaults"
    indir.mkdir()
    srt = tmp_path / "d.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    _make_mkv(indir / "E01.mkv", srt, default_audio_index=1)

    scan = media.scan_files([indir / "E01.mkv"])
    source = scan.files[0]
    assert [s.disposition_default for s in source.audio_streams] == [0, 1]

    # Force the remux path by dropping the chapters so the copy shortcut is skipped.
    rules = _rules(keep_chapters=False, copy_non_video_files=False)
    out_root = output.resolve_output_root(indir, tmp_path / "OutD", rules)
    processing.process_files(scan.files, indir, out_root, rules)

    probed = media.probe_file(next(out_root.rglob("*.mkv")))
    assert [s.disposition_default for s in probed.audio_streams] == [0, 1]


def test_probe_failure_is_reported_next_to_the_healthy_file(tmp_path):
    """B-05: a broken file must be returned as a failure, not silently dropped."""
    indir = tmp_path / "Mixed"
    indir.mkdir()
    srt = tmp_path / "m.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    _make_mkv(indir / "good.mkv", srt)
    broken = indir / "broken.mkv"
    broken.write_bytes(b"this is not a matroska file" * 32)

    scan = media.scan_files(sorted(indir.glob("*.mkv")))

    assert [m.path.name for m in scan.files] == ["good.mkv"]
    assert scan.failures == [broken]


def test_copy_unchanged_when_no_remux_needed(tmp_path):
    """The no-remux shortcut: robocopy on Windows, stdlib copy elsewhere."""
    cdir = tmp_path / "Single"
    cdir.mkdir()
    srt = tmp_path / "sub2.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    _run_ffmpeg([
        "ffmpeg", "-y", "-nostdin",
        "-f", "lavfi", "-i", "testsrc=size=128x72:rate=5:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-map", "0:v", "-map", "1:a",
        "-metadata:s:a:0", "language=jpn",
        "-disposition:a:0", "default",
        "-shortest", str(cdir / "solo.mkv"),
    ])

    scan = media.scan_files([cdir / "solo.mkv"])
    rules = _rules(copy_non_video_files=False)
    out_root = output.resolve_output_root(cdir, tmp_path / "OutC", rules)
    summary = processing.process_files(scan.files, cdir, out_root, rules)

    assert summary.copied_unchanged == 1
    outputs = list(out_root.rglob("*.mkv"))
    assert len(outputs) == 1
    assert outputs[0].stat().st_size == (cdir / "solo.mkv").stat().st_size


def test_process_files_reports_a_size_delta_per_file(two_track_series, tmp_path):
    """Item 5: every finished file carries its own size delta, not just the run total."""
    scan = media.scan_files(sorted(two_track_series.glob("*.mkv")))
    rules = _rules(audio_mode="1", audio_languages=["jpn"], copy_non_video_files=False)
    out_root = output.resolve_output_root(two_track_series, tmp_path / "OutS", rules)

    summary = processing.process_files(scan.files, two_track_series, out_root, rules)

    for result in summary.results:
        assert result["status"] == "OK"
        assert result["size_delta"] != "-"
        assert result["elapsed"] != "-"


@pytest.mark.skipif(not ROBOCOPY_AVAILABLE, reason="robocopy not available (Windows only)")
@pytest.mark.parametrize("destination_state", ["same-size-and-time", "newer"])
def test_overwrite_replaces_an_existing_unchanged_copy(tmp_path, destination_state):
    """B-08: with overwrite on, robocopy must not skip a destination that looks
    identical (or newer) than the source."""
    cdir = tmp_path / "Src"
    cdir.mkdir()
    _run_ffmpeg([
        "ffmpeg", "-y", "-nostdin",
        "-f", "lavfi", "-i", "testsrc=size=128x72:rate=5:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-map", "0:v", "-map", "1:a",
        "-metadata:s:a:0", "language=jpn",
        "-disposition:a:0", "default",
        "-shortest", str(cdir / "solo.mkv"),
    ])
    source = cdir / "solo.mkv"

    out_root = tmp_path / "Dst"
    out_root.mkdir()
    destination = out_root / "solo.mkv"
    # Stale content that robocopy would consider "the same file": identical size,
    # identical timestamp, different bytes. Comparing sizes afterwards would pass
    # even without the fix, so the assertion has to compare content.
    expected = source.read_bytes()
    destination.write_bytes(b"\0" * len(expected))
    source_stat = source.stat()
    os.utime(destination, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
    if destination_state == "newer":
        os.utime(destination, ns=(source_stat.st_atime_ns + 600_000_000_000,
                                  source_stat.st_mtime_ns + 600_000_000_000))
    assert destination.read_bytes() != expected

    copying.copy_video_without_remux(source, destination, overwrite=True)

    assert destination.read_bytes() == expected, "overwrite did not replace the stale destination"
