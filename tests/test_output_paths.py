"""Unit tests for output path/name resolution in muxcls.output."""
from pathlib import Path

from muxcls.constants import AUDIO_ALL, AUDIO_BY_LANGUAGE, SUBTITLE_ALL, SUBTITLE_NONE
from muxcls.models import SelectionRules
from muxcls.output import (
    make_output_path,
    resolve_output_root,
    sanitize_filename_part,
    selection_suffix,
    unique_path,
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


def test_sanitize_filename_part_replaces_invalid_chars():
    assert sanitize_filename_part('a<b>c:d"e') == "a-b-c-d-e"


def test_sanitize_filename_part_falls_back_when_no_alnum():
    assert sanitize_filename_part("***", fallback="X") == "X"


def test_selection_suffix_language_mode():
    # "jpn" is mapped to the compact display label "JA" by muxcls.textutil.language_label.
    rules = _rules(audio_mode=AUDIO_BY_LANGUAGE, audio_languages=["jpn"])
    assert selection_suffix(rules) == "[JA Audio + All Subs]"


def test_selection_suffix_no_subs():
    rules = _rules(subtitle_mode=SUBTITLE_NONE)
    assert selection_suffix(rules) == "[All Audio + No Subs]"


def test_resolve_output_root_for_folder_creates_named_subfolder(tmp_path):
    input_root = tmp_path / "Series"
    input_root.mkdir()
    output_base = tmp_path / "Out"
    rules = _rules()
    result = resolve_output_root(input_root, output_base, rules)
    assert result.parent == output_base
    assert "Series" in result.name
    assert "All Audio" in result.name


def test_resolve_output_root_for_single_file_is_output_base(tmp_path):
    input_file = tmp_path / "episode.mkv"
    input_file.write_bytes(b"0")
    output_base = tmp_path / "Out"
    rules = _rules()
    result = resolve_output_root(input_file, output_base, rules)
    assert result == output_base


def test_make_output_path_avoids_self_collision(tmp_path):
    # Single-file mode with output_base == input file's own folder and a suffix
    # that would resolve to the same name as the input -> must not overwrite input.
    input_file = tmp_path / "clip.mkv"
    input_file.write_bytes(b"0")
    rules = _rules()
    output_root = tmp_path
    result = make_output_path(input_file, output_root, input_file, rules)
    assert result != input_file


def test_unique_path_adds_numeric_suffix(tmp_path):
    existing = tmp_path / "out.mkv"
    existing.write_bytes(b"0")
    result = unique_path(existing)
    assert result.name == "out (2).mkv"


def test_unique_path_returns_same_path_if_free(tmp_path):
    candidate = tmp_path / "free.mkv"
    assert unique_path(candidate) == candidate
