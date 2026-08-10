"""What the log has to contain.

A log collected from another machine is the only evidence available when a run
there behaved unexpectedly. For a long time it held eight lines for a five-minute
session: the console showed the scan report, the stream inventory and every menu,
and none of it was recorded. These tests pin the parts that were missing, so the
log cannot quietly go back to being a summary of itself.
"""
import logging

import pytest

from muxcls import prompts, reporting
from muxcls.colors import plain
from muxcls.models import MediaFile, StreamInfo


@pytest.fixture
def logged(monkeypatch):
    """Capture what the package writes to its logger, uncoloured."""
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("MuxCls")
    handler = Capture()
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield records
    logger.removeHandler(handler)
    logger.setLevel(previous_level)


@pytest.fixture
def two_files(tmp_path):
    return [
        MediaFile(path=tmp_path / "E01.mkv", streams=[
            StreamInfo(index=0, codec_type="video", codec_name="hevc"),
            StreamInfo(index=1, codec_type="audio", language="eng", codec_name="opus"),
            StreamInfo(index=2, codec_type="audio", language="jpn", title="Judas Stereo",
                       codec_name="opus", channels=2),
            StreamInfo(index=3, codec_type="subtitle", language="eng", codec_name="ass"),
        ]),
        MediaFile(path=tmp_path / "E02.mkv", streams=[
            StreamInfo(index=0, codec_type="video", codec_name="hevc"),
            StreamInfo(index=1, codec_type="audio", language="jpn", codec_name="opus"),
        ]),
    ]


# --- the scan report ------------------------------------------------------

def test_the_scan_report_reaches_the_log(logged, two_files, tmp_path, capsys):
    """The per-file stream inventory is the single most useful thing a run
    records: it is what answers "what was actually in those files?" later."""
    reporting.print_scan_report(two_files, tmp_path)
    body = "\n".join(logged)

    assert "File: E01.mkv" in body
    assert "File: E02.mkv" in body
    assert "lang=jpn" in body and "title=Judas Stereo" in body
    assert "codec=opus" in body and "channels=2" in body


def test_the_log_says_the_same_thing_as_the_console(logged, two_files, tmp_path, capsys):
    reporting.print_scan_report(two_files, tmp_path)
    console = plain(capsys.readouterr().out)

    for line in logged:
        assert line.strip() in console, f"the log invented a line the console never showed: {line!r}"


def test_the_unique_summary_reaches_the_log(logged, two_files, capsys):
    reporting.print_unique_summary(two_files)
    body = "\n".join(logged)

    assert "Audio streams found" in body
    assert "count=" in body and "lang=jpn" in body
    assert "Subtitle streams found" in body


def test_no_escape_sequence_ever_reaches_the_log(logged, two_files, tmp_path, capsys):
    reporting.print_scan_report(two_files, tmp_path)
    reporting.print_unique_summary(two_files)

    assert not any("\x1b" in line for line in logged), "a log full of colour codes is unreadable"


def test_separator_rules_are_not_logged(logged, two_files, tmp_path, capsys):
    reporting.print_scan_report(two_files, tmp_path)

    assert not any(set(line.strip()) <= {"=", "-", " "} and line.strip() for line in logged), \
        "an 80-character rule is console furniture, not a log entry"


# --- prompts and menus ----------------------------------------------------

def test_every_prompt_and_answer_is_recorded(logged, answers, capsys):
    answers("jpn")
    prompts.ask_text("Audio language codes to Keep")

    assert any("Audio language codes to Keep" in line and "'jpn'" in line for line in logged)


def test_taking_a_default_is_recorded_as_such(logged, answers, capsys):
    answers("")
    prompts.ask_yes_no("Keep chapters?", True, allow_back=False)

    assert any("empty, default" in line or "Keep chapters" in line for line in logged)


def test_quitting_is_recorded_before_it_unwinds(logged, answers, capsys):
    answers("quit")
    with pytest.raises(prompts.MenuExit):
        prompts.read_menu_input("Input file or folder path")

    assert any("-> quit" in line for line in logged)


def test_back_is_recorded(logged, answers, capsys):
    answers("0")
    with pytest.raises(prompts.MenuBack):
        prompts.read_menu_input("Choose audio mode", allow_back=True)

    assert any("-> back" in line for line in logged)


def test_a_menu_is_logged_with_its_options(logged, answers, capsys):
    """The user sees five numbered choices; a log that records only the answer
    cannot tell you what "1" meant in that version of the menu."""
    answers("1")
    prompts.ask_numbered_menu(
        "Audio selection modes",
        (("1", "keep audio by language codes"), ("2", "keep audio by title text"),
         ("3", "keep audio by exact stream indexes"), ("4", "keep all audio"),
         ("5", "remove all audio")),
        "1", "Choose audio mode", allow_back=False,
    )
    body = "\n".join(logged)

    assert "Menu: Audio selection modes" in body
    assert "keep audio by language codes" in body
    assert "remove all audio" in body, "every option the user could have picked belongs in the log"
    assert "(default)" in body


# --- startup --------------------------------------------------------------

def test_startup_records_the_environment(tmp_path, monkeypatch, capsys):
    """Which FFmpeg ran, in which directory, with which settings - none of it is
    reconstructable after the fact, and all of it explains machine-specific
    behaviour.

    Read back from the file rather than through a capture handler:
    `setup_logging` replaces the logger's handlers, so anything attached
    beforehand is gone by the time it writes its first line.
    """
    from muxcls import logsetup

    (tmp_path / "muxcls").mkdir()
    monkeypatch.setattr(logsetup, "__file__", str(tmp_path / "muxcls" / "logsetup.py"))
    try:
        written = logsetup.setup_logging()
        assert written is not None and written.exists()
        body = written.read_text(encoding="utf-8")
    finally:
        logging.getLogger("MuxCls").handlers.clear()

    assert "MuxCls" in body and "python=" in body and "os=" in body
    assert "Working directory:" in body
    assert "Console:" in body
    assert "Settings:" in body and "MUXCLS_OPERATION_TIMEOUT" in body
    assert "\x1b" not in body


def test_the_tool_check_records_which_binary_and_which_version(logged, monkeypatch):
    from muxcls import media

    monkeypatch.setattr(media.shutil, "which", lambda _b: "/usr/bin/ffmpeg")
    monkeypatch.setattr(media, "tool_version", lambda _b: "ffmpeg version 8.1.1")

    assert media.require_tool("ffmpeg") is True
    assert any("ffmpeg" in line and "8.1.1" in line for line in logged)


def test_a_missing_tool_is_an_error_not_a_note(logged, monkeypatch):
    from muxcls import media

    monkeypatch.setattr(media.shutil, "which", lambda _b: None)
    assert media.require_tool("ffmpeg") is False
    assert any("not found" in line for line in logged)
