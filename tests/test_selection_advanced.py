"""The advanced selection flow's remaining uncovered parts (muxcls.selection).

`previous_advanced_step` is the Back map for the advanced style: it has to skip
the steps a given set of answers never showed, and getting it wrong sends the
user to a prompt they have not seen (or past one they need). It is pure, and it
is the one piece of the selection module that is genuinely tricky to reason
about, so it is worth pinning case by case.

Also here: the metadata-edit prompt, the style menu that chooses between the two
selection flows, and the revisit entry point used when Back is pressed at the
output-folder step.
"""

import pytest

from muxcls.constants import (
    AUDIO_ALL, AUDIO_BY_INDEX, AUDIO_BY_LANGUAGE, AUDIO_BY_TITLE, AUDIO_NONE,
    SUBTITLE_ALL, SUBTITLE_BY_LANGUAGE, SUBTITLE_NONE,
)
from muxcls.models import MediaFile, OutputStreamEdits, SelectionRules, StreamInfo, StreamMetadataEdit
from muxcls.metadata_edits import ask_metadata_edits, kept_languages_for_metadata
from muxcls.selection import (
    audio_mode_needs_detail, configure_rules, configure_rules_advanced,
    previous_advanced_step, previous_exact_step, revisit_last_rule_step,
    subtitle_mode_needs_detail,
)


@pytest.fixture
def dual_audio(tmp_path):
    return [MediaFile(path=tmp_path / "E01.mkv", streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="eng"),
        StreamInfo(index=2, codec_type="audio", language="jpn"),
        StreamInfo(index=3, codec_type="subtitle", language="eng"),
    ])]


def _rules(**overrides) -> SelectionRules:
    base = dict(
        audio_mode=AUDIO_ALL, audio_languages=[], audio_titles=[], audio_indexes=[],
        subtitle_mode=SUBTITLE_ALL, subtitle_languages=[], subtitle_titles=[], subtitle_indexes=[],
        keep_attachments=True, keep_metadata=True, keep_chapters=True,
        overwrite=False, copy_non_video_files=True,
    )
    base.update(overrides)
    return SelectionRules(**base)


# --- which modes have a follow-up prompt ----------------------------------

@pytest.mark.parametrize("mode,needs", [
    (AUDIO_BY_LANGUAGE, True), (AUDIO_BY_TITLE, True), (AUDIO_BY_INDEX, True),
    (AUDIO_ALL, False), (AUDIO_NONE, False),
])
def test_audio_modes_that_ask_a_follow_up_question(mode, needs):
    assert audio_mode_needs_detail(mode) is needs


@pytest.mark.parametrize("mode,needs", [
    (SUBTITLE_BY_LANGUAGE, True), (SUBTITLE_ALL, False), (SUBTITLE_NONE, False),
])
def test_subtitle_modes_that_ask_a_follow_up_question(mode, needs):
    assert subtitle_mode_needs_detail(mode) is needs


# --- Back through the advanced flow ---------------------------------------

def test_back_skips_the_audio_detail_step_when_the_mode_has_none():
    """From the subtitle mode step, Back lands on the audio detail prompt only
    if that mode actually asked for detail. With "keep all audio" there was no
    such prompt, so Back must reach the audio mode step instead."""
    assert previous_advanced_step(2, AUDIO_BY_LANGUAGE, SUBTITLE_ALL) == 1
    assert previous_advanced_step(2, AUDIO_ALL, SUBTITLE_ALL) == 0


def test_back_skips_the_whole_audio_section_when_no_file_has_audio():
    # -1 means "there is nothing before this"; the caller returns to the input
    # path rather than to a step that was never shown.
    assert previous_advanced_step(2, AUDIO_ALL, SUBTITLE_ALL, skip_audio_selection=True) == -1


def test_back_from_the_first_extra_step_depends_on_the_subtitle_mode():
    assert previous_advanced_step(4, AUDIO_ALL, SUBTITLE_BY_LANGUAGE) == 3
    assert previous_advanced_step(4, AUDIO_ALL, SUBTITLE_ALL) == 2


def test_back_over_a_skipped_subtitle_section_falls_through_to_audio():
    assert previous_advanced_step(4, AUDIO_BY_LANGUAGE, SUBTITLE_ALL,
                                  skip_subtitle_selection=True) == 1
    assert previous_advanced_step(4, AUDIO_ALL, SUBTITLE_ALL,
                                  skip_subtitle_selection=True) == 0
    assert previous_advanced_step(4, AUDIO_ALL, SUBTITLE_ALL,
                                  skip_audio_selection=True, skip_subtitle_selection=True) == -1


def test_removing_all_subtitles_still_leaves_a_step_to_go_back_to():
    assert previous_advanced_step(5, AUDIO_ALL, SUBTITLE_NONE) == 2
    assert previous_advanced_step(5, AUDIO_ALL, SUBTITLE_BY_LANGUAGE) == 4


def test_the_later_steps_walk_back_one_at_a_time():
    for step in (6, 7, 8, 9):
        assert previous_advanced_step(step, AUDIO_ALL, SUBTITLE_ALL) == step - 1


def test_back_from_the_first_step_stays_put():
    assert previous_advanced_step(0, AUDIO_ALL, SUBTITLE_ALL) == 0


# --- metadata edits --------------------------------------------------------

def test_declining_metadata_edits_returns_nothing(answers, dual_audio):
    answers("n")
    assert ask_metadata_edits(dual_audio) == OutputStreamEdits()


def test_declining_clears_edits_that_were_already_set(answers, dual_audio):
    """Answering no is a decision, not "leave it as it was" - otherwise Back
    into this prompt could never remove an edit that had been made."""
    existing = [StreamMetadataEdit(codec_type="audio", match_languages=["jpn"],
                                   language="jpn", title="Japanese")]
    answers("n")

    assert ask_metadata_edits(dual_audio, initial_edits=existing) == OutputStreamEdits()


def test_declining_also_clears_an_output_order_that_was_already_set(answers, dual_audio):
    """Same rule as the edits above: the order is part of this screen, so
    answering no has to drop it too or Back could never undo a reorder."""
    answers("n")

    result = ask_metadata_edits(dual_audio, current_rules=_rules(audio_order=[2, 1]))

    assert result.audio_order == []


def test_the_languages_offered_come_from_the_streams_that_will_be_kept(dual_audio):
    keep_japanese = _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"])

    everything = kept_languages_for_metadata(dual_audio, "audio", None)
    narrowed = kept_languages_for_metadata(dual_audio, "audio", keep_japanese)

    assert set(everything) >= {"eng", "jpn"}
    assert narrowed == ["jpn"], "offering a language that is being dropped is a dead end"


# --- the style menu --------------------------------------------------------

def test_a_single_audio_language_skips_the_style_menu(answers, tmp_path):
    """With one audio language there is nothing for exact-index mode to
    disambiguate, so the advanced flow is entered directly - no style prompt is
    scripted here, and asking would raise."""
    files = [MediaFile(path=tmp_path / "a.mkv", streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="jpn"),
    ])]
    answers("4", "1", "", "", "", "", "", "", "")

    rules = configure_rules(files)

    assert rules.selection_style != "exact"


def test_two_audio_languages_offer_the_choice_of_style(answers, dual_audio):
    # "2" picks exact-index mode; then audio 2, subtitles 3, then the defaults.
    answers("2", "2", "3", "", "", "", "", "", "")

    rules = configure_rules(dual_audio)

    assert rules.selection_style == "exact"
    assert rules.audio_indexes == [2]


# --- revisiting the last rule step -----------------------------------------

def test_revisit_returns_to_the_exact_flow_for_exact_rules(answers, dual_audio):
    """Back at the output-folder prompt must re-enter the flow the user was
    actually in, not the other one."""
    exact = _rules(audio_mode=AUDIO_BY_INDEX, audio_indexes=[2], selection_style="exact")
    answers("", "", "", "", "")

    revisited = revisit_last_rule_step(dual_audio, exact)

    assert revisited.selection_style == "exact"


# --- output stream order in the metadata screen ----------------------------

def test_choosing_reorder_records_the_indexes_in_the_order_typed(answers, dual_audio):
    # yes -> action 7 (reorder audio) -> the order -> done
    answers("y", "7", "2,1", "10")

    result = ask_metadata_edits(dual_audio, current_rules=_rules())

    assert result.audio_order == [2, 1]
    assert result.subtitle_order == []
    assert result.metadata_edits == []


def test_an_existing_order_is_carried_into_the_screen_and_kept(answers, dual_audio):
    """Reaching this screen again through Back must show the order already set
    rather than silently starting from none."""
    answers("y", "10")

    result = ask_metadata_edits(dual_audio, current_rules=_rules(audio_order=[2, 1]))

    assert result.audio_order == [2, 1]


# --- a single dropped file has no siblings to copy -------------------------

def test_a_single_file_input_is_never_asked_about_copying_other_files(answers, dual_audio):
    """Seven answers cover every step except the non-video copy question. If it
    were still asked the scripted input would run out, which the fixture raises
    on - so this fails loudly rather than quietly."""
    answers("4", "1", "", "", "", "", "")

    rules = configure_rules_advanced(dual_audio, single_file_input=True)

    assert rules.copy_non_video_files is False


def test_a_folder_input_is_still_asked_about_copying_other_files(answers, dual_audio):
    # The seventh answer is the copy question; without it the eighth ("") would
    # answer overwrite and the copy flag would keep its True default.
    answers("4", "1", "", "", "", "", "n", "")

    rules = configure_rules_advanced(dual_audio, single_file_input=False)

    assert rules.copy_non_video_files is False


@pytest.mark.parametrize("previous_step,skip,expected", [
    (9, True, 7), (9, False, 8),
])
def test_back_from_overwrite_skips_the_question_a_single_file_never_saw(previous_step, skip, expected):
    assert previous_advanced_step(
        previous_step, AUDIO_ALL, SUBTITLE_ALL, skip_copy_non_video=skip,
    ) == expected


@pytest.mark.parametrize("previous_step,skip,expected", [
    (7, True, 5), (7, False, 6),
])
def test_exact_back_from_overwrite_skips_the_same_question(previous_step, skip, expected):
    assert previous_exact_step(previous_step, SUBTITLE_ALL, skip_copy_non_video=skip) == expected
