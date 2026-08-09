"""Unit tests for stream-selection and remux-decision logic in muxcls.muxlogic."""
from pathlib import Path

from muxcls.constants import (
    AUDIO_ALL,
    AUDIO_BY_INDEX,
    AUDIO_BY_LANGUAGE,
    AUDIO_NONE,
    SUBTITLE_ALL,
    SUBTITLE_NONE,
)
from muxcls.models import MediaFile, SelectionRules, StreamInfo
from muxcls.muxlogic import (
    build_ffmpeg_command,
    remux_needed_reasons,
    selected_audio_streams,
    selected_subtitle_streams,
)


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
    )
    base.update(overrides)
    return SelectionRules(**base)


def _media() -> MediaFile:
    return MediaFile(path=Path("in.mkv"), streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="jpn", disposition_default=1),
        StreamInfo(index=2, codec_type="audio", language="eng"),
        StreamInfo(index=3, codec_type="subtitle", language="eng", disposition_default=1),
    ])


def test_selected_audio_streams_by_language():
    media = _media()
    rules = _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"])
    kept = selected_audio_streams(media, rules)
    assert [s.index for s in kept] == [1]


def test_selected_audio_streams_by_index():
    media = _media()
    rules = _rules(audio_mode=AUDIO_BY_INDEX, audio_indexes=[2])
    kept = selected_audio_streams(media, rules)
    assert [s.index for s in kept] == [2]


def test_selected_audio_streams_none():
    media = _media()
    rules = _rules(audio_mode=AUDIO_NONE)
    assert selected_audio_streams(media, rules) == []


def test_selected_subtitle_streams_none_mode():
    media = _media()
    rules = _rules(subtitle_mode=SUBTITLE_NONE)
    assert selected_subtitle_streams(media, rules) == []


def test_remux_not_needed_when_keeping_everything_with_correct_defaults():
    media = _media()
    rules = _rules()
    audio_keep = selected_audio_streams(media, rules)
    subs_keep = selected_subtitle_streams(media, rules)
    # Both kept audio streams: index 1 has default=1 (first, correct), index 2
    # has default=0 (correct for non-first) -> no normalization needed.
    reasons = remux_needed_reasons(media, rules, audio_keep, subs_keep)
    assert reasons == []


def test_remux_needed_when_dropping_a_stream():
    media = _media()
    rules = _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"])
    audio_keep = selected_audio_streams(media, rules)
    subs_keep = selected_subtitle_streams(media, rules)
    reasons = remux_needed_reasons(media, rules, audio_keep, subs_keep)
    assert "audio stream selection changes" in reasons


def test_build_ffmpeg_command_maps_selected_streams():
    media = _media()
    rules = _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"], overwrite=True)
    cmd, audio_keep, subs_keep = build_ffmpeg_command(Path("in.mkv"), Path("out.mkv"), media, rules)
    assert [s.index for s in audio_keep] == [1]
    assert "-map" in cmd and "0:1" in cmd
    assert "0:2" not in cmd  # eng audio dropped
    assert "-y" in cmd  # overwrite=True
    assert "-c" in cmd and "copy" in cmd


# --- B-01: the source default disposition is preserved, never forced to the first stream ---

def _media_with_late_defaults() -> MediaFile:
    # The *second* audio track and the *second* subtitle track carry default=1,
    # which is what real dual-audio releases usually look like.
    return MediaFile(path=Path("in.mkv"), streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="eng"),
        StreamInfo(index=2, codec_type="audio", language="jpn", disposition_default=1),
        StreamInfo(index=3, codec_type="subtitle", language="eng"),
        StreamInfo(index=4, codec_type="subtitle", language="fas", disposition_default=1),
    ])


def _disposition_value(cmd, spec):
    return cmd[cmd.index(f"-disposition:{spec}") + 1]


def test_default_disposition_of_a_non_first_audio_stream_is_preserved():
    media = _media_with_late_defaults()
    cmd, _, _ = build_ffmpeg_command(Path("in.mkv"), Path("out.mkv"), media, _rules())
    assert _disposition_value(cmd, "a:0") == "-default"
    assert _disposition_value(cmd, "a:1") == "+default"


def test_default_disposition_of_a_non_first_subtitle_stream_is_preserved():
    media = _media_with_late_defaults()
    cmd, _, _ = build_ffmpeg_command(Path("in.mkv"), Path("out.mkv"), media, _rules())
    assert _disposition_value(cmd, "s:0") == "-default"
    assert _disposition_value(cmd, "s:1") == "+default"


def test_first_selected_stream_is_not_forced_to_default_when_source_had_none():
    media = MediaFile(path=Path("in.mkv"), streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="jpn"),
    ])
    cmd, _, _ = build_ffmpeg_command(Path("in.mkv"), Path("out.mkv"), media, _rules())
    assert _disposition_value(cmd, "a:0") == "-default"


def test_remux_is_not_required_only_to_normalize_default_disposition():
    # Keeping every stream of a file whose default sits on a later track must
    # stay a plain copy: nothing about the output actually changes.
    media = _media_with_late_defaults()
    rules = _rules()
    reasons = remux_needed_reasons(
        media, rules,
        selected_audio_streams(media, rules),
        selected_subtitle_streams(media, rules),
    )
    assert reasons == []


def test_dropping_the_default_stream_still_preserves_remaining_dispositions():
    media = _media_with_late_defaults()
    rules = _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["eng"])
    cmd, audio_keep, _ = build_ffmpeg_command(Path("in.mkv"), Path("out.mkv"), media, rules)
    assert [s.index for s in audio_keep] == [1]
    # The only surviving audio track was not default in the source, so it must
    # not silently become default in the output.
    assert _disposition_value(cmd, "a:0") == "-default"
