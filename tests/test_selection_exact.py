"""The exact-index selection mode (muxcls.selection), which had no coverage.

`configure_rules_exact` is one of the two selection styles a user can pick, and
`ask_keep_indexes` is the prompt it is built from - it accepts index lists,
`all` and `none`, and has to cope with indexes the scan never reported. These
tests drive the real prompts with scripted input; nothing here touches a file
or spawns a process.
"""
import builtins

import pytest

from muxcls.constants import (
    AUDIO_ALL, AUDIO_BY_INDEX, AUDIO_NONE,
    SUBTITLE_ALL, SUBTITLE_BY_INDEX, SUBTITLE_NONE,
)
from muxcls.models import MediaFile, StreamInfo
from muxcls.selection import (
    ask_keep_indexes, configure_rules_exact, previous_exact_step,
)


def _answers(monkeypatch, *values):
    queue = list(values)

    def fake_input(_prompt=""):
        if not queue:
            raise AssertionError("the code asked for more input than the test provided")
        return queue.pop(0)

    monkeypatch.setattr(builtins, "input", fake_input)


@pytest.fixture
def two_audio_two_subs(tmp_path):
    """One file with the stream shape of a typical dual-audio release."""
    return [MediaFile(path=tmp_path / "E01.mkv", streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="eng"),
        StreamInfo(index=2, codec_type="audio", language="jpn"),
        StreamInfo(index=3, codec_type="subtitle", language="eng"),
        StreamInfo(index=4, codec_type="subtitle", language="eng", title="Signs"),
    ])]


# --- ask_keep_indexes -----------------------------------------------------

def test_an_index_list_is_kept_verbatim(monkeypatch):
    _answers(monkeypatch, "1,3")
    mode, indexes = ask_keep_indexes(
        "Audio", [1, 2, 3], exact_mode=AUDIO_BY_INDEX, all_mode=AUDIO_ALL, none_mode=AUDIO_NONE)

    assert mode == AUDIO_BY_INDEX
    assert indexes == [1, 3]


@pytest.mark.parametrize("typed", ["all", "a", "*", "ALL"])
def test_the_all_shorthands(monkeypatch, typed):
    _answers(monkeypatch, typed)
    mode, indexes = ask_keep_indexes(
        "Audio", [1, 2], exact_mode=AUDIO_BY_INDEX, all_mode=AUDIO_ALL, none_mode=AUDIO_NONE)

    assert (mode, indexes) == (AUDIO_ALL, [])


@pytest.mark.parametrize("typed", ["none", "n", "no", "remove", "-", "NONE"])
def test_the_none_shorthands(monkeypatch, typed):
    _answers(monkeypatch, typed)
    mode, indexes = ask_keep_indexes(
        "Subtitle", [3, 4], exact_mode=SUBTITLE_BY_INDEX, all_mode=SUBTITLE_ALL, none_mode=SUBTITLE_NONE)

    assert (mode, indexes) == (SUBTITLE_NONE, [])


def test_no_streams_of_that_kind_selects_none_without_asking(monkeypatch):
    # No input is scripted: asking would raise from the fake input.
    _answers(monkeypatch)
    mode, indexes = ask_keep_indexes(
        "Subtitle", [], exact_mode=SUBTITLE_BY_INDEX, all_mode=SUBTITLE_ALL, none_mode=SUBTITLE_NONE)

    assert (mode, indexes) == (SUBTITLE_NONE, [])


def test_empty_input_asks_again(monkeypatch, capsys):
    _answers(monkeypatch, "", "2")
    _, indexes = ask_keep_indexes(
        "Audio", [1, 2], exact_mode=AUDIO_BY_INDEX, all_mode=AUDIO_ALL, none_mode=AUDIO_NONE)

    assert indexes == [2]
    # ask_text rejects the blank line before ask_keep_indexes ever sees it.
    assert "cannot be empty" in capsys.readouterr().out


def test_an_index_the_scan_never_reported_needs_confirming(monkeypatch, capsys):
    """Declining returns to index entry. Silently accepting an index that is not
    in the file would produce an ffmpeg -map for a stream that does not exist."""
    _answers(monkeypatch, "9", "n", "1")
    _, indexes = ask_keep_indexes(
        "Audio", [1, 2], exact_mode=AUDIO_BY_INDEX, all_mode=AUDIO_ALL, none_mode=AUDIO_NONE)

    assert indexes == [1]
    assert "not found in the scan" in capsys.readouterr().out


def test_an_unknown_index_can_be_forced(monkeypatch):
    # Mixed sets differ file to file, so an index missing from one file may be
    # perfectly valid in another.
    _answers(monkeypatch, "9", "y")
    _, indexes = ask_keep_indexes(
        "Audio", [1, 2], exact_mode=AUDIO_BY_INDEX, all_mode=AUDIO_ALL, none_mode=AUDIO_NONE)

    assert indexes == [9]


# --- configure_rules_exact ------------------------------------------------

def test_a_full_pass_through_the_exact_flow(monkeypatch, two_audio_two_subs):
    # audio 2 -> subtitles 3 -> metadata edit? n -> attachments/metadata/
    # chapters/extras/overwrite defaults.
    _answers(monkeypatch, "2", "3", "", "", "", "", "", "")
    rules = configure_rules_exact(two_audio_two_subs)

    assert rules.selection_style == "exact"
    assert rules.audio_mode == AUDIO_BY_INDEX and rules.audio_indexes == [2]
    assert rules.subtitle_mode == SUBTITLE_BY_INDEX and rules.subtitle_indexes == [3]
    # Exact mode never sets the language/title rules - they belong to advanced.
    assert rules.audio_languages == [] and rules.audio_titles == []
    assert rules.subtitle_languages == [] and rules.subtitle_titles == []


def test_choosing_no_subtitles_skips_straight_past_them(monkeypatch, two_audio_two_subs):
    _answers(monkeypatch, "2", "none", "", "", "", "", "", "")
    rules = configure_rules_exact(two_audio_two_subs)

    assert rules.subtitle_mode == SUBTITLE_NONE
    assert rules.subtitle_indexes == []


def test_keeping_all_of_both_kinds(monkeypatch, two_audio_two_subs):
    _answers(monkeypatch, "all", "all", "", "", "", "", "", "")
    rules = configure_rules_exact(two_audio_two_subs)

    assert rules.audio_mode == AUDIO_ALL
    assert rules.subtitle_mode == SUBTITLE_ALL


def test_the_defaults_the_flow_lands_on(monkeypatch, two_audio_two_subs):
    _answers(monkeypatch, "2", "3", "", "", "", "", "", "")
    rules = configure_rules_exact(two_audio_two_subs)

    assert rules.keep_attachments is True
    assert rules.keep_metadata is True
    assert rules.keep_chapters is True
    assert rules.copy_non_video_files is True
    assert rules.overwrite is False, "overwrite must never be the default"


# --- back navigation ------------------------------------------------------

def test_back_walks_the_steps_in_order():
    for step in range(1, 8):
        assert previous_exact_step(step, SUBTITLE_BY_INDEX) == step - 1


def test_back_past_the_subtitle_step_skips_it_when_none_was_chosen():
    """With SUBTITLE_NONE the index prompt was never shown, so Back must not
    return to a step the user never saw."""
    assert previous_exact_step(3, SUBTITLE_NONE) == 1
    assert previous_exact_step(3, SUBTITLE_BY_INDEX) == 2


def test_back_from_the_first_step_stays_at_the_first_step():
    assert previous_exact_step(0, SUBTITLE_BY_INDEX) == 0
