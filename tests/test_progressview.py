"""Unit tests for the multi-row progress block (muxcls.progressview).

The block is the only part of the UI that does arithmetic rather than just
printing, so the parts worth pinning are the ones a wrong number would make
lie: how a row decides its ratio, what Overall counts, what happens when the
block is taller than the terminal, and that colour codes never count as
printable width.
"""
import io
import time

import pytest

from muxcls.progressview import (
    ACTIVE, DONE, FAILED, QUEUED, SKIPPED,
    ProgressRow, ProgressView, bar, truncate_visible, visible_length,
)
from muxcls.colors import C, color


class FakeConsole(io.StringIO):
    def isatty(self):
        return True


def _rows(count, total=1000):
    return [ProgressRow(name=f"file{n}.mkv", total=total) for n in range(count)]


# --- width accounting -----------------------------------------------------

def test_visible_length_ignores_colour_codes():
    plain = "Done | 466.7 MB"
    assert visible_length(color(plain, C.SKY)) == len(plain)


def test_truncate_visible_cuts_by_printable_width_not_bytes():
    line = color("A" * 40, C.SKY)
    cut = truncate_visible(line, 10)
    assert visible_length(cut) == 10
    # The colour it was wearing must still be opened and closed.
    assert cut.startswith("\x1b[")
    assert cut.endswith(C.RESET)


def test_truncate_visible_leaves_a_short_line_alone():
    line = color("short", C.SKY)
    assert truncate_visible(line, 40) == line


def test_a_finished_row_keeps_the_time_it_took():
    """finish() froze the elapsed time after flipping the state, and
    live_elapsed() only measures while a row is ACTIVE - so every finished row
    reported 00:00:00 no matter how long it had run."""
    row = _rows(1)[0]
    view = ProgressView([row], enabled=False)
    view.start(0)
    row.started_at = time.perf_counter() - 12.0     # pretend it ran for 12s
    view.finish(0, DONE)

    assert row.elapsed == pytest.approx(12.0, abs=0.5)
    assert "00:00:12" in "\n".join(view.compose(99, 24))


def test_a_finished_row_shows_no_extra_column_after_its_state():
    # A leftover detail here reads as the speed column that was removed.
    row = _rows(1)[0]
    view = ProgressView([row], enabled=False)
    view.start(0)
    view.finish(0, DONE, "-65.12 MB")
    line = view.compose(99, 24)[-1]

    assert "Done" in line
    assert "-65.12 MB" not in line


def test_the_bar_uses_the_shared_progress_palette():
    # EVdlc draws the unfilled track in crimson, not grey; that contrast is
    # what makes the filled portion readable.
    drawn = bar(0.5, 10, ACTIVE)
    assert C.BAR_FILL in drawn
    assert C.BAR_TRACK in drawn
    assert C.GRAY not in drawn


def test_no_row_shows_a_transfer_speed():
    row = ProgressRow(name="a.mkv", total=489_401_205, completed=200_000_000,
                      state=ACTIVE, started_at=1.0)
    body = "\n".join(ProgressView([row], enabled=False).compose(99, 24))
    assert "/s" not in body, "the speed column was removed on purpose"


def test_elapsed_is_labelled_not_a_bare_time():
    rows = _rows(2)
    view = ProgressView(rows, enabled=False)
    view.finish(0, DONE)
    body = "\n".join(view.compose(99, 24))
    assert body.count("Elapsed") >= 2, "both Overall and the file rows carry the label"


def test_size_is_shown_as_done_over_total():
    row = ProgressRow(name="a.mkv", total=1_000_000, completed=250_000, state=ACTIVE)
    line = ProgressView([row], enabled=False).compose(99, 24)[-1]
    assert " / " in line, "a total with no progress beside it says nothing"


def test_a_full_row_survives_a_normal_terminal_width():
    row = ProgressRow(name="Season 1/Episode 01.mkv", total=489_401_205,
                      percent=83.5, state=ACTIVE, detail="")
    view = ProgressView([row], enabled=False)
    lines = view.compose(width=99, height=24)
    assert all(visible_length(line) <= 99 for line in lines), \
        "a row wider than the terminal would be cut mid-number"


# --- ratio ----------------------------------------------------------------

def test_reported_percent_wins_over_byte_count():
    # FFmpeg reports a position on the timeline; the byte count of a remux says
    # nothing useful about how far along it is.
    row = ProgressRow(name="a.mkv", total=1000, completed=100, percent=75.0)
    assert row.ratio == pytest.approx(0.75)


def test_ratio_falls_back_to_bytes_when_no_percent_was_reported():
    row = ProgressRow(name="a.mkv", total=1000, completed=250)
    assert row.ratio == pytest.approx(0.25)


def test_ratio_is_unknown_when_neither_is_available():
    assert ProgressRow(name="a.mkv").ratio is None


def test_an_unknown_ratio_draws_an_empty_track_rather_than_zero_percent():
    row = ProgressRow(name="a.mkv", state=ACTIVE)
    line = ProgressView([row], enabled=False).compose(99, 24)[-1]
    assert "--.-%" in line, "a copy that cannot report bytes has not done nothing"


# --- overall --------------------------------------------------------------

def test_overall_counts_every_finished_state_not_just_success():
    rows = _rows(4)
    view = ProgressView(rows, enabled=False)
    view.finish(0, DONE)
    view.finish(1, FAILED)
    view.finish(2, SKIPPED)
    assert "3/4 files" in view.overall_line(99)


def test_overall_advances_while_one_long_file_is_running():
    rows = _rows(4)
    view = ProgressView(rows, enabled=False)
    view.finish(0, DONE)
    view.start(1)
    before = view.overall_line(99)
    view.update(1, percent=50.0)
    after = view.overall_line(99)
    assert before != after, "the bar must move during a file, not only between files"
    # One of four done, plus half of the second: 25% + 12.5%.
    assert " 37.5%" in after


# --- viewport -------------------------------------------------------------

def test_a_block_taller_than_the_terminal_keeps_the_active_file_visible():
    rows = _rows(40)
    view = ProgressView(rows, enabled=False)
    for index in range(30):
        view.finish(index, DONE)
    view.start(30)
    lines = view.compose(width=99, height=20)
    body = "\n".join(lines)
    assert "file30.mkv" in body, "the file being worked on scrolled out of view"
    assert "file(s) above" in body, "hidden rows must be announced, not silently dropped"


# --- output gating --------------------------------------------------------

def test_a_disabled_view_writes_nothing(monkeypatch):
    stream = io.StringIO()          # no isatty -> redirected output
    monkeypatch.setattr("sys.stdout", stream)
    view = ProgressView(_rows(2))
    view.start(0)
    view.update(0, percent=50.0)
    view.finish(0, DONE)
    view.close()
    assert stream.getvalue() == "", "redirected output must not receive cursor control"


def test_an_enabled_view_repaints_in_place(monkeypatch):
    console = FakeConsole()
    monkeypatch.setattr("sys.stdout", console)
    view = ProgressView(_rows(2))
    assert view.enabled
    view.start(0)
    view.finish(0, DONE)
    output = console.getvalue()
    assert "\x1b[?25l" in output, "the cursor should be hidden while the block owns the screen"
    assert "\x1b[J" in output, "frame 2+ must clear the old block instead of appending"


def test_close_restores_the_cursor(monkeypatch):
    console = FakeConsole()
    monkeypatch.setattr("sys.stdout", console)
    view = ProgressView(_rows(1))
    view.start(0)
    view.close()
    assert console.getvalue().endswith("\x1b[?25h"), "the cursor must come back"


def test_a_row_that_only_knows_a_percentage_still_shows_how_much_is_done():
    """Robocopy reports a percentage and no byte count. Reading row.completed
    directly left the size column at 0 B for the whole copy while the bar beside
    it moved."""
    row = ProgressRow(name="a.mkv", total=1_000_000, percent=40.0, state=ACTIVE)
    line = ProgressView([row], enabled=False).compose(99, 24)[-1]

    assert "391 KB / 977 KB" in line, "the size must follow the bar, not sit at 0 B"
