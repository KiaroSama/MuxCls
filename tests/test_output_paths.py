"""Unit tests for output path/name resolution in muxcls.output."""
import os
from pathlib import Path

import pytest

from muxcls.constants import AUDIO_ALL, AUDIO_BY_LANGUAGE, SUBTITLE_ALL, SUBTITLE_NONE
from muxcls.models import SelectionRules
from muxcls.output import (
    extra_file_sources,
    make_output_path,
    output_base_conflict,
    path_total_size,
    resolve_output_root,
    sanitize_filename_part,
    selection_suffix,
    unique_path,
    walk_files,
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


# --- B-04: a folder run must never be able to write inside its own input ---

def test_output_base_inside_input_folder_is_rejected(tmp_path):
    input_root = tmp_path / "Series"
    (input_root / "nested").mkdir(parents=True)
    assert output_base_conflict(input_root, input_root / "nested") is not None


def test_output_base_equal_to_input_folder_is_rejected(tmp_path):
    input_root = tmp_path / "Series"
    input_root.mkdir()
    assert output_base_conflict(input_root, input_root) is not None


def test_output_base_rejection_ignores_windows_path_case(tmp_path):
    input_root = tmp_path / "Series"
    input_root.mkdir()
    shouted = Path(str(input_root).upper())
    conflict = output_base_conflict(input_root, shouted)
    if os.name == "nt":
        assert conflict is not None
    else:  # POSIX paths are genuinely case-sensitive; a different case is a different folder.
        assert conflict is None


def test_output_base_outside_input_folder_is_allowed(tmp_path):
    input_root = tmp_path / "Series"
    input_root.mkdir()
    assert output_base_conflict(input_root, tmp_path / "Out") is None


def test_output_base_beside_a_single_input_file_is_allowed(tmp_path):
    input_file = tmp_path / "clip.mkv"
    input_file.write_bytes(b"0")
    assert output_base_conflict(input_file, tmp_path) is None


def test_resolve_output_root_refuses_an_output_base_inside_the_input(tmp_path):
    input_root = tmp_path / "Series"
    input_root.mkdir()
    with pytest.raises(RuntimeError):
        resolve_output_root(input_root, input_root / "Out", _rules())


# --- B-08: overwrite reuses the intended output root instead of numbering it ---

def test_resolve_output_root_reuses_existing_root_when_overwriting(tmp_path):
    input_root = tmp_path / "Series"
    input_root.mkdir()
    output_base = tmp_path / "Out"
    rules = _rules(overwrite=True)
    first = resolve_output_root(input_root, output_base, rules)
    first.mkdir(parents=True)
    assert resolve_output_root(input_root, output_base, rules) == first


def test_resolve_output_root_numbers_existing_root_when_not_overwriting(tmp_path):
    input_root = tmp_path / "Series"
    input_root.mkdir()
    output_base = tmp_path / "Out"
    rules = _rules(overwrite=False)
    first = resolve_output_root(input_root, output_base, rules)
    first.mkdir(parents=True)
    second = resolve_output_root(input_root, output_base, rules)
    assert second != first
    assert second.name.endswith("(2)")


# --- tree walking: the output tree must be stepped over, not filtered ------

def _library(root: Path) -> Path:
    """An input tree with the output folder nested inside it, which is what a
    default run produces: output base = the input's parent."""
    (root / "Season 1").mkdir(parents=True)
    (root / "Season 1" / "E01.mkv").write_bytes(b"a" * 10)
    (root / "Season 1" / "notes.txt").write_bytes(b"b" * 5)
    out = root / "Out"
    (out / "Season 1").mkdir(parents=True)
    (out / "Season 1" / "E01.mkv").write_bytes(b"c" * 100)
    return out


def test_size_accounting_skips_the_excluded_tree(tmp_path):
    out = _library(tmp_path)
    assert path_total_size(tmp_path) == 115          # everything
    assert path_total_size(tmp_path, exclude_paths=[out]) == 15   # input only


def test_the_excluded_tree_is_never_descended_into(tmp_path):
    """Pruning at the directory boundary, not testing each file, is what makes
    this cheap: resolving the excluded root once per file cost 2.97s on a
    3000-file library versus 0.37s for the pruning walk."""
    out = _library(tmp_path)
    walked = list(walk_files(tmp_path, [out.resolve()]))

    assert all(out not in path.parents for path in walked)
    assert (tmp_path / "Season 1" / "E01.mkv") in walked


def test_walking_without_exclusions_returns_every_file(tmp_path):
    _library(tmp_path)
    assert len(list(walk_files(tmp_path, []))) == 3


def test_extra_files_exclude_videos_and_the_output_tree(tmp_path):
    out = _library(tmp_path)
    extras = extra_file_sources(tmp_path, out)

    assert extras == [tmp_path / "Season 1" / "notes.txt"]


def test_extra_files_come_back_in_a_stable_order(tmp_path):
    out = _library(tmp_path)
    (tmp_path / "Season 1" / "a.srt").write_bytes(b"x")
    (tmp_path / "Season 1" / "Z.ass").write_bytes(b"x")

    names = [path.name for path in extra_file_sources(tmp_path, out)]
    assert names == sorted(names, key=str.lower)
