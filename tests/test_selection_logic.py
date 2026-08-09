"""Unit tests for audio/subtitle track-selection skip logic (regression for the
1.3.1 fix: skip audio questions only when no file has more than one audio track,
not merely when all tracks share one language)."""
from pathlib import Path

from muxcls.constants import AUDIO_NONE
from muxcls.models import MediaFile, StreamInfo
from muxcls.reporting import max_stream_count_for, stream_languages_for
from muxcls.selection import configure_rules_advanced, should_skip_audio_selection


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


# --- B-03: the audio menu (and with it "remove all audio") stays reachable ---

def test_single_audio_track_still_shows_the_audio_menu():
    media = MediaFile(path=Path("b.mkv"), streams=[_video(0), _audio(1, "jpn")])
    assert should_skip_audio_selection([media]) is False


def test_audio_selection_is_skipped_only_when_nothing_has_audio():
    media = MediaFile(path=Path("c.mkv"), streams=[_video(0)])
    assert should_skip_audio_selection([media]) is True


def test_one_track_set_can_still_choose_remove_all_audio(monkeypatch, capsys):
    """Drive the real advanced wizard: one audio track, and the user picks
    'remove all audio'. Before the fix the menu was skipped entirely and
    AUDIO_NONE was unreachable for such a set."""
    media = MediaFile(path=Path("b.mkv"), streams=[
        _video(0),
        _audio(1, "jpn"),
        StreamInfo(index=2, codec_type="subtitle", language="eng"),
    ])
    # audio mode 5 (none), subtitle mode 5 (none), keep metadata (default),
    # no metadata edits, keep chapters, copy extras, no overwrite.
    answers = iter(["5", "5", "", "n", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    rules = configure_rules_advanced([media])

    assert rules.audio_mode == AUDIO_NONE


def test_set_without_audio_auto_selects_remove_all_audio(monkeypatch, capsys):
    media = MediaFile(path=Path("c.mkv"), streams=[
        _video(0),
        StreamInfo(index=1, codec_type="subtitle", language="eng"),
    ])
    # Audio menu is skipped, so the wizard starts at the subtitle question.
    answers = iter(["5", "", "n", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    rules = configure_rules_advanced([media])

    assert rules.audio_mode == AUDIO_NONE
