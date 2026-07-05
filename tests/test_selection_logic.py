"""Unit tests for audio/subtitle track-selection skip logic (regression for the
1.3.1 fix: skip audio questions only when no file has more than one audio track,
not merely when all tracks share one language)."""
from pathlib import Path

from muxcls.models import MediaFile, StreamInfo
from muxcls.reporting import max_stream_count_for, stream_languages_for


def _audio(index: int, language: str, title: str = "") -> StreamInfo:
    return StreamInfo(index=index, codec_type="audio", language=language, title=title)


def _video(index: int = 0) -> StreamInfo:
    return StreamInfo(index=index, codec_type="video")


def test_multi_track_single_language_is_not_skippable():
    # Main track + commentary track, same language -> must NOT be skippable.
    media = MediaFile(path=Path("a.mkv"), streams=[
        _video(0), _audio(1, "jpn"), _audio(2, "jpn", title="Commentary"),
    ])
    assert max_stream_count_for([media], "audio") == 2
    assert stream_languages_for([media], "audio") == ["jpn"]


def test_single_track_is_skippable():
    media = MediaFile(path=Path("b.mkv"), streams=[_video(0), _audio(1, "jpn")])
    assert max_stream_count_for([media], "audio") <= 1


def test_mixed_files_where_one_has_multiple_tracks_is_not_skippable():
    single = MediaFile(path=Path("b.mkv"), streams=[_video(0), _audio(1, "jpn")])
    multi = MediaFile(path=Path("a.mkv"), streams=[
        _video(0), _audio(1, "jpn"), _audio(2, "jpn", title="Commentary"),
    ])
    assert max_stream_count_for([single, multi], "audio") == 2


def test_no_audio_streams_is_skippable():
    media = MediaFile(path=Path("c.mkv"), streams=[_video(0)])
    assert max_stream_count_for([media], "audio") == 0
