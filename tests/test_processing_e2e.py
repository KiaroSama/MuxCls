"""Real end-to-end tests through muxcls.processing.process_files, using actual
ffmpeg-generated fixtures. These exercise the remux path, the extra-file copy
path, verify_output, and the robocopy copy-unchanged path.

Requires ffmpeg/ffprobe in PATH. Skipped automatically if unavailable.
Requires robocopy (Windows only) for the copy-unchanged scenario; that one test
is skipped on non-Windows platforms.
"""
import shutil
import subprocess
import sys

import pytest

from muxcls import media, output, processing
from muxcls.models import SelectionRules

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
ROBOCOPY_AVAILABLE = shutil.which("robocopy") is not None

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


def _make_mkv(dst, srt_path, with_default_audio=False):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=128x72:rate=5:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
        "-i", str(srt_path),
        "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map", "3:s",
        "-c:s", "srt",
        "-metadata:s:a:0", "language=jpn",
        "-metadata:s:a:1", "language=eng",
        "-metadata:s:s:0", "language=eng",
        "-shortest", str(dst),
    ]
    if with_default_audio:
        cmd[-2:-2] = ["-disposition:a:0", "default"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert r.returncode == 0, r.stderr[-800:]


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
    media_files = media.scan_files(sorted(two_track_series.glob("*.mkv")))
    assert len(media_files) == 2

    rules = _rules(audio_mode="1", audio_languages=["jpn"])
    out_root = output.resolve_output_root(two_track_series, tmp_path / "OutA", rules)
    processing.process_files(media_files, two_track_series, out_root, rules)

    outputs = sorted(out_root.rglob("*.mkv"))
    assert len(outputs) == 2
    for f in outputs:
        probed = media.probe_file(f)
        assert [s.language for s in probed.audio_streams] == ["jpn"]
        assert len(probed.subtitle_streams) == 1
    assert list(out_root.rglob("readme.txt")), "non-video file was not copied"

    # verify_output must run cleanly against real output.
    processing.verify_output(out_root, rules)


@pytest.mark.skipif(not ROBOCOPY_AVAILABLE, reason="robocopy not available (Windows only)")
def test_copy_unchanged_uses_robocopy_when_no_remux_needed(tmp_path):
    cdir = tmp_path / "Single"
    cdir.mkdir()
    srt = tmp_path / "sub2.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=128x72:rate=5:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-map", "0:v", "-map", "1:a",
        "-metadata:s:a:0", "language=jpn",
        "-disposition:a:0", "default",
        "-shortest", str(cdir / "solo.mkv"),
    ]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert r.returncode == 0, r.stderr[-800:]

    media_files = media.scan_files([cdir / "solo.mkv"])
    rules = _rules(copy_non_video_files=False)
    out_root = output.resolve_output_root(cdir, tmp_path / "OutC", rules)
    processing.process_files(media_files, cdir, out_root, rules)

    outputs = list(out_root.rglob("*.mkv"))
    assert len(outputs) == 1
    assert outputs[0].stat().st_size > 0
