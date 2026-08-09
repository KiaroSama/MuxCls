"""Unit tests for the ffprobe parsing layer (muxcls.models).

This is the boundary where arbitrary external JSON becomes the app's domain
objects: every field here comes from whatever ffprobe made of a file someone
else produced. The rest of the suite builds `StreamInfo` by hand, so until now
nothing exercised the parsers themselves - including `parse_duration_seconds`,
whose result is the denominator of the remux progress percentage.
"""
import pytest

from muxcls.models import (
    MediaFile, StreamInfo,
    parse_duration_seconds, parse_float_value, parse_int_value,
    stream_size_bytes_from_ffprobe, tag_value_by_prefix,
)


# --- number parsing -------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (5, 5), ("5", 5), (" 7 ", 7), (0, 0), ("0", 0), (-3, -3),
])
def test_int_values_that_parse(raw, expected):
    assert parse_int_value(raw) == expected


@pytest.mark.parametrize("raw", [
    None, "", "  ", "N/A", "abc", "1.5", [], {},
    "²",       # '²' - str.isdigit() says True, int() raises
    "٣",       # '٣' Arabic-Indic three: a real digit int() does accept...
])
def test_int_values_that_must_not_crash(raw):
    # Whatever the verdict, it is never an exception: one odd tag must not end
    # a scan of a thousand files.
    result = parse_int_value(raw)
    assert result is None or isinstance(result, int)


def test_int_parsing_accepts_non_ascii_digits_python_accepts():
    # int('٣') == 3 in Python, so narrowing to ASCII would lose real values.
    assert parse_int_value("٣") == 3


@pytest.mark.parametrize("raw,expected", [
    (1.5, 1.5), ("1.5", 1.5), ("0", 0.0), (2, 2.0),
])
def test_float_values_that_parse(raw, expected):
    assert parse_float_value(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, "", "N/A", "abc", "nan-ish", [], {}])
def test_float_values_that_must_not_crash(raw):
    result = parse_float_value(raw)
    assert result is None or isinstance(result, float)


# --- duration -------------------------------------------------------------

def test_duration_is_read_from_the_container():
    # A real value, from a real release: 1422.601 s of Sword Art Online S01E01.
    assert parse_duration_seconds("1422.601000") == pytest.approx(1422.601)


@pytest.mark.parametrize("raw", [None, "", "N/A", "abc"])
def test_an_unreadable_duration_is_none_not_zero(raw):
    """None and 0 are different answers downstream: `read_ffmpeg_percent`
    divides by this, and 0 would be a division by zero rather than 'unknown'."""
    assert parse_duration_seconds(raw) is None


@pytest.mark.parametrize("raw", ["0", "0.0", "-1"])
def test_a_nonsensical_duration_does_not_become_a_divisor(raw):
    value = parse_duration_seconds(raw)
    assert value is None or value <= 0, "callers guard on <= 0, so either is safe"


# --- tags -----------------------------------------------------------------

def test_tag_lookup_is_case_insensitive_on_the_prefix():
    tags = {"NUMBER_OF_BYTES": "123", "language": "jpn"}
    assert tag_value_by_prefix(tags, "number_of_bytes") == "123"


def test_tag_lookup_returns_none_when_absent():
    assert tag_value_by_prefix({"language": "jpn"}, "number_of_bytes") is None


def test_stream_size_comes_from_the_byte_tag():
    raw = {}
    tags = {"NUMBER_OF_BYTES": "33301236"}
    assert stream_size_bytes_from_ffprobe(raw, tags) == 33301236


def test_stream_size_is_none_when_the_file_carries_no_such_tag():
    # MP4/AVI generally do not; the scan report shows a blank size, not a zero.
    assert stream_size_bytes_from_ffprobe({}, {}) is None


# --- StreamInfo.from_ffprobe ----------------------------------------------

def _raw(**overrides):
    base = {
        "index": 1,
        "codec_type": "audio",
        "codec_name": "opus",
        "channels": 2,
        "disposition": {"default": 1},
        "tags": {"language": "jpn", "title": "Japanese", "NUMBER_OF_BYTES": "33537697"},
    }
    base.update(overrides)
    return base


def test_a_normal_audio_stream_parses():
    stream = StreamInfo.from_ffprobe(_raw())

    assert (stream.index, stream.codec_type, stream.codec_name) == (1, "audio", "opus")
    assert stream.language == "jpn"
    assert stream.title == "Japanese"
    assert stream.channels == 2
    assert stream.disposition_default
    assert stream.size_bytes == 33537697


def test_a_stream_with_no_tags_at_all_still_parses():
    stream = StreamInfo.from_ffprobe({"index": 0, "codec_type": "video"})

    assert stream.index == 0
    assert stream.codec_type == "video"
    # An absent language tag reads as "und" - the scan report shows a stream
    # with no language as unknown rather than as a blank column.
    assert stream.language == "und"
    assert not stream.disposition_default


def test_a_stream_with_junk_in_every_numeric_field_still_parses():
    """ffprobe reports N/A for fields a container does not carry. A scan must
    survive it - one unreadable field is not a reason to fail the file."""
    stream = StreamInfo.from_ffprobe(_raw(
        index="N/A", channels="N/A", tags={"NUMBER_OF_BYTES": "N/A"},
    ))

    assert stream.channels is None
    assert stream.size_bytes is None


def test_disposition_default_is_falsy_when_the_source_did_not_set_it():
    # Stored as the int ffprobe reports and used for truthiness, to rebuild the
    # -disposition flags the source already had.
    assert not StreamInfo.from_ffprobe(_raw(disposition={"default": 0})).disposition_default
    assert not StreamInfo.from_ffprobe(_raw(disposition={})).disposition_default
    assert StreamInfo.from_ffprobe(_raw(disposition={"default": 1})).disposition_default


# --- MediaFile stream views ------------------------------------------------

def test_media_file_groups_streams_by_kind(tmp_path):
    media = MediaFile(path=tmp_path / "a.mkv", streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="jpn"),
        StreamInfo(index=2, codec_type="subtitle", language="eng"),
        StreamInfo(index=3, codec_type="attachment"),
    ])

    assert [s.index for s in media.video_streams] == [0]
    assert [s.index for s in media.audio_streams] == [1]
    assert [s.index for s in media.subtitle_streams] == [2]
    assert [s.index for s in media.attachment_streams] == [3]
