"""Unit tests for the input layer (muxcls.prompts).

Everything the user types arrives through here, so these are the tests that
decide whether a path, a language code or a menu choice is understood the way
the rest of the app assumes it was. Nothing here touches the filesystem beyond
tmp_path, and nothing spawns a process.
"""
import builtins

import pytest

from muxcls.prompts import (
    MenuBack, MenuExit,
    ask_csv_int_required, ask_csv_text_required, ask_path, ask_yes_no,
    input_path_from_args, normalize_path_text, read_menu_input,
)


def _answers(monkeypatch, *values):
    """Feed a scripted sequence of answers to input()."""
    queue = list(values)

    def fake_input(_prompt=""):
        if not queue:
            raise AssertionError("the code asked for more input than the test provided")
        return queue.pop(0)

    monkeypatch.setattr(builtins, "input", fake_input)


# --- path handling --------------------------------------------------------

def test_a_relative_path_becomes_absolute():
    """A relative path survives as a bare token in the argument lists built for
    ffprobe/ffmpeg. With `.` as the input, `Path('.') / '-name.mkv'` collapses
    to `-name.mkv`, which those tools read as an option rather than a file -
    a perfectly good file then fails as 'could not be read'."""
    assert normalize_path_text(".").is_absolute()
    assert normalize_path_text("Season 1").is_absolute()


def test_an_absolute_path_is_left_alone(tmp_path):
    assert normalize_path_text(str(tmp_path)) == tmp_path


def test_a_path_from_the_launcher_is_absolute_too(tmp_path):
    # Drag-and-drop usually gives an absolute path, but the launcher forwards
    # whatever it was given.
    assert input_path_from_args(["."]).is_absolute()
    assert input_path_from_args([str(tmp_path)]) == tmp_path
    assert input_path_from_args([]) is None
    assert input_path_from_args(["  "]) is None


def test_quotes_and_whitespace_are_stripped(tmp_path):
    assert normalize_path_text(f'  "{tmp_path}"  ') == tmp_path
    assert normalize_path_text(f"'{tmp_path}'") == tmp_path


def test_a_dash_named_file_keeps_its_name_and_gains_a_directory(tmp_path):
    # The name must not be mangled - only anchored, so the token handed to
    # ffprobe starts with the drive/root instead of a dash.
    target = tmp_path / "-dash episode.mkv"
    target.write_bytes(b"x")
    resolved = normalize_path_text(str(target))
    assert resolved.name == "-dash episode.mkv"
    assert not str(resolved).startswith("-")


def test_ask_path_rejects_a_missing_path_then_accepts_a_real_one(monkeypatch, tmp_path, capsys):
    _answers(monkeypatch, str(tmp_path / "nope"), str(tmp_path))
    assert ask_path("Input", must_exist=True, allow_back=False) == tmp_path
    assert "does not exist" in capsys.readouterr().out


# --- menu navigation ------------------------------------------------------

def test_quit_raises_menu_exit(monkeypatch):
    _answers(monkeypatch, "quit")
    with pytest.raises(MenuExit):
        read_menu_input("anything")


def test_zero_means_back_when_back_is_allowed(monkeypatch):
    _answers(monkeypatch, "0")
    with pytest.raises(MenuBack):
        read_menu_input("anything", allow_back=True)


def test_zero_is_never_ordinary_input(monkeypatch, capsys):
    """`0` is reserved for Back at every prompt. Where Back is not available it
    is refused and re-asked rather than accepted as a value - otherwise the
    meaning of `0` would depend on which prompt you were standing in."""
    _answers(monkeypatch, "0", "something")
    assert read_menu_input("anything", allow_back=False) == "something"
    assert "Back is not available" in capsys.readouterr().out


# --- yes/no ---------------------------------------------------------------

@pytest.mark.parametrize("typed,expected", [
    ("y", True), ("Y", True), ("yes", True), ("YES", True),
    ("n", False), ("no", False), ("  n  ", False),
])
def test_yes_no_understands_the_usual_spellings(monkeypatch, typed, expected):
    _answers(monkeypatch, typed)
    assert ask_yes_no("Continue?", True, allow_back=False) is expected


def test_empty_input_takes_the_default(monkeypatch):
    _answers(monkeypatch, "")
    assert ask_yes_no("Continue?", True, allow_back=False) is True
    _answers(monkeypatch, "")
    assert ask_yes_no("Continue?", False, allow_back=False) is False


def test_nonsense_is_rejected_and_asked_again(monkeypatch, capsys):
    _answers(monkeypatch, "maybe", "y")
    assert ask_yes_no("Continue?", False, allow_back=False) is True
    assert "y or n" in capsys.readouterr().out


# --- csv parsing ----------------------------------------------------------

def test_csv_text_splits_and_trims(monkeypatch):
    _answers(monkeypatch, " japanese , commentary ")
    assert ask_csv_text_required("Titles") == ["japanese", "commentary"]


def test_csv_text_asks_again_when_empty(monkeypatch, capsys):
    _answers(monkeypatch, "", "signs")
    assert ask_csv_text_required("Titles") == ["signs"]
    assert capsys.readouterr().out.strip() != ""


def test_csv_int_parses_a_list(monkeypatch):
    _answers(monkeypatch, "1, 3,5")
    assert ask_csv_int_required("Indexes") == [1, 3, 5]


def test_csv_int_drops_a_non_number_and_keeps_the_rest(monkeypatch, capsys):
    """Unparseable tokens are reported and skipped rather than rejecting the
    whole line. Note the parse goes through int() inside try/except, not an
    isdigit() guard - str.isdigit() is True for '²' while int('²') raises, so
    guarding with it would admit exactly the input that breaks it."""
    _answers(monkeypatch, "1,two,3")
    assert ask_csv_int_required("Indexes") == [1, 3]
    assert "Ignored invalid number: two" in capsys.readouterr().out


def test_csv_int_asks_again_when_nothing_parsed(monkeypatch, capsys):
    _answers(monkeypatch, "two", "2")
    assert ask_csv_int_required("Indexes") == [2]
    assert "at least one stream index" in capsys.readouterr().out


def test_csv_int_confirms_an_index_the_scan_did_not_find(monkeypatch, capsys):
    # Declining the confirmation returns to index entry rather than accepting it.
    _answers(monkeypatch, "9", "n", "2")
    assert ask_csv_int_required("Indexes", available_indexes=[1, 2, 3]) == [2]
    assert "were not found in the scan" in capsys.readouterr().out


def test_csv_int_keeps_an_unknown_index_when_confirmed(monkeypatch):
    _answers(monkeypatch, "9", "y")
    assert ask_csv_int_required("Indexes", available_indexes=[1, 2, 3]) == [9]
