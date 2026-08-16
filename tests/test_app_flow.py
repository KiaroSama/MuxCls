"""The top-level flow (muxcls.app), which had no coverage at all.

`main_menu` is where every refusal lives: missing tools, no video files, files
ffprobe could not read, the confirmation before anything is written, and the
exit codes each of those produces. None of it was exercised, so a change to any
of those branches was invisible to the suite.

Nothing here runs ffmpeg, ffprobe or robocopy - the seams at the edge of the
module are patched, and what is tested is the decision each answer leads to.
"""

import pytest

from muxcls import app
from muxcls.media import ScanResult
from muxcls.models import MediaFile, SelectionRules, StreamInfo
from muxcls.processing import ProcessSummary


def _rules() -> SelectionRules:
    return SelectionRules(
        audio_mode="4", audio_languages=[], audio_titles=[], audio_indexes=[],
        subtitle_mode="1", subtitle_languages=[], subtitle_titles=[], subtitle_indexes=[],
        keep_attachments=True, keep_metadata=True, keep_chapters=True,
        overwrite=False, copy_non_video_files=True,
    )


def _summary(succeeded: int = 1) -> ProcessSummary:
    return ProcessSummary(
        total=1, succeeded=succeeded, remuxed=succeeded, copied_unchanged=0, skipped=0,
        no_audio=0, failed=0, extra_copied=0, extra_skipped=0, extra_failed=0,
        size_delta=0, elapsed=0.1, results=[],
    )


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A folder with one scannable file, and every external tool stubbed out."""
    folder = tmp_path / "Series"
    folder.mkdir()
    video = folder / "E01.mkv"
    video.write_bytes(b"x")

    media = MediaFile(path=video, streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="jpn"),
    ])

    monkeypatch.setattr(app, "require_tool", lambda _name: True)
    monkeypatch.setattr(app, "setup_logging", lambda: None)
    monkeypatch.setattr(app, "enable_windows_ansi", lambda: None)
    monkeypatch.setattr(app, "find_video_files", lambda _root: [video])
    monkeypatch.setattr(app, "scan_files", lambda _files: ScanResult(files=[media], failures=[]))
    monkeypatch.setattr(app, "configure_rules", lambda _files, **_kwargs: _rules())
    monkeypatch.setattr(app.sys, "argv", ["MuxCls.py"])
    return folder


# --- refusals that must stop the run ---------------------------------------

def test_a_missing_ffmpeg_stops_before_anything_is_read(monkeypatch, capsys):
    monkeypatch.setattr(app, "setup_logging", lambda: None)
    monkeypatch.setattr(app, "enable_windows_ansi", lambda: None)
    monkeypatch.setattr(app, "require_tool", lambda name: name != "ffmpeg")

    with pytest.raises(SystemExit) as exit_info:
        app.main_menu()

    assert exit_info.value.code == 1
    assert "ffmpeg was not found" in capsys.readouterr().out


def test_a_missing_ffprobe_stops_too(monkeypatch, capsys):
    monkeypatch.setattr(app, "setup_logging", lambda: None)
    monkeypatch.setattr(app, "enable_windows_ansi", lambda: None)
    monkeypatch.setattr(app, "require_tool", lambda name: name != "ffprobe")

    with pytest.raises(SystemExit) as exit_info:
        app.main_menu()

    assert exit_info.value.code == 1
    assert "ffprobe was not found" in capsys.readouterr().out


def test_a_folder_with_no_video_files_stops_and_says_what_it_did_find(library, monkeypatch, answers, capsys):
    monkeypatch.setattr(app, "find_video_files", lambda _root: [])
    monkeypatch.setattr(app, "find_non_video_extensions", lambda _root: [".txt", ".7z"])
    answers(str(library))

    with pytest.raises(SystemExit) as exit_info:
        app.main_menu()

    out = capsys.readouterr().out
    assert exit_info.value.code == 1
    assert "No supported video files" in out
    assert ".7z" in out, "the extensions actually present are worth naming"


def test_nothing_scannable_stops_the_run(library, monkeypatch, answers, capsys):
    monkeypatch.setattr(app, "scan_files", lambda _f: ScanResult(files=[], failures=[library / "E01.mkv"]))
    answers(str(library))

    with pytest.raises(SystemExit) as exit_info:
        app.main_menu()

    assert exit_info.value.code == 1
    assert "No files could be scanned" in capsys.readouterr().out


def test_declining_after_a_probe_failure_stops_rather_than_dropping_the_file(
    library, monkeypatch, answers, capsys,
):
    """B-05: a file ffprobe cannot read must never vanish silently. The user is
    asked, and answering no ends the run instead of proceeding without it."""
    media = MediaFile(path=library / "E01.mkv", streams=[StreamInfo(index=0, codec_type="video")])
    monkeypatch.setattr(app, "scan_files",
                        lambda _f: ScanResult(files=[media], failures=[library / "broken.mkv"]))
    answers(str(library), "n")

    with pytest.raises(SystemExit) as exit_info:
        app.main_menu()

    out = capsys.readouterr().out
    assert exit_info.value.code == 1
    assert "could not be read by ffprobe" in out
    assert "broken.mkv" in out
    assert "Stopped" in out


# --- the confirmation gate --------------------------------------------------

def test_answering_no_at_the_confirmation_writes_nothing(library, monkeypatch, answers, capsys):
    called = []
    monkeypatch.setattr(app, "process_files", lambda *a, **k: called.append(a) or _summary())
    # path -> output base (default) -> start processing? no
    answers(str(library), "", "n")

    app.main_menu()

    assert called == [], "processing must not start after the user declined"
    assert "Cancelled" in capsys.readouterr().out


def test_the_confirmation_lists_the_settings_before_asking(library, answers, capsys):
    answers(str(library), "", "n")
    app.main_menu()

    out = capsys.readouterr().out
    for label in ("Input", "Output base", "Output root", "Audio mode", "Overwrite"):
        assert label in out, f"the confirmation must show {label}"


# --- verification after a run ----------------------------------------------

def test_a_successful_run_offers_to_verify_the_output(library, monkeypatch, answers):
    verified = []
    monkeypatch.setattr(app, "process_files", lambda *a, **k: _summary(succeeded=1))
    monkeypatch.setattr(app, "verify_output", lambda root, rules: verified.append(root))
    monkeypatch.setattr(app, "print_ready_for_next_task", lambda: None)
    # path -> output base -> start? yes -> verify? yes -> next input: quit
    answers(str(library), "", "", "y", "quit")

    with pytest.raises(app.MenuExit):   # main() is what maps this to exit 0
        app.main_menu()

    assert len(verified) == 1, "answering yes must run the verification"


def test_verification_is_skipped_by_default(library, monkeypatch, answers):
    verified = []
    monkeypatch.setattr(app, "process_files", lambda *a, **k: _summary(succeeded=1))
    monkeypatch.setattr(app, "verify_output", lambda root, rules: verified.append(root))
    monkeypatch.setattr(app, "print_ready_for_next_task", lambda: None)
    # Enter at the verify prompt takes the default, which is no.
    answers(str(library), "", "", "", "quit")

    with pytest.raises(app.MenuExit):
        app.main_menu()

    assert verified == [], "the default must not spend an ffprobe per output file"


def test_a_run_that_produced_nothing_is_not_offered_verification(library, monkeypatch, answers):
    verified = []
    monkeypatch.setattr(app, "process_files", lambda *a, **k: _summary(succeeded=0))
    monkeypatch.setattr(app, "verify_output", lambda root, rules: verified.append(root))
    monkeypatch.setattr(app, "print_ready_for_next_task", lambda: None)
    # No answer is scripted for a verify prompt: asking would raise.
    answers(str(library), "", "", "quit")

    with pytest.raises(app.MenuExit):
        app.main_menu()

    assert verified == []


# --- main(): how each exit is reported --------------------------------------

def test_quit_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(app, "main_menu", lambda: (_ for _ in ()).throw(app.MenuExit()))

    with pytest.raises(SystemExit) as exit_info:
        app.main()

    assert exit_info.value.code == 0
    assert "Exited" in capsys.readouterr().out


def test_back_at_the_very_first_menu_is_explained_rather_than_ignored(monkeypatch, capsys):
    monkeypatch.setattr(app, "main_menu", lambda: (_ for _ in ()).throw(app.MenuBack()))

    with pytest.raises(SystemExit) as exit_info:
        app.main()

    assert exit_info.value.code == 0
    assert "Back is not available here" in capsys.readouterr().out


def test_ctrl_c_reports_the_conventional_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(app, "main_menu", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))

    with pytest.raises(SystemExit) as exit_info:
        app.main()

    assert exit_info.value.code == 130, "130 is what a shell expects from SIGINT"
    assert "Cancelled by user" in capsys.readouterr().out


def test_an_unexpected_error_is_logged_and_not_swallowed(monkeypatch, capsys):
    monkeypatch.setattr(app, "main_menu", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(SystemExit) as exit_info:
        app.main()

    assert exit_info.value.code != 0
    assert "boom" in capsys.readouterr().out
