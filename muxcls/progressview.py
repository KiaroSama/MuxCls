"""A multi-row progress block that repaints in place.

Adapted from EVdlc's `utils/progress.py` / `utils/progress_render.py`: the same
`Overall` line, `File NN:` rows, bar/percent/size/speed/ETA/elapsed layout,
sticky in-place repaint and viewport windowing. What was dropped on the way in:
the optional `rich` backend and the background ticker thread (MuxCls has no
third-party dependencies and processes one file at a time, so the poll loop that
already watches the child process drives the frames), and the byte-level stall
detection its network transfers needed.

The block is only drawn on a real terminal. With redirected output there is no
cursor to move, so the caller keeps printing one line per file instead - which
is what a log or a CI transcript wants to read anyway.
"""
from __future__ import annotations

import re
import shutil
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple

from .colors import C, color
from .textutil import format_elapsed_time, format_stream_size

QUEUED = "queued"
ACTIVE = "active"
DONE = "done"
FAILED = "failed"
SKIPPED = "skipped"

# How long a window the speed readout averages over. Short enough to react,
# long enough that one slow chunk does not make the ETA jump minutes.
SPEED_WINDOW_SECONDS = 3.0

MAX_FRAMES_PER_SECOND = 8.0


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def visible_length(text: str) -> int:
    return len(ANSI_PATTERN.sub("", text))


def truncate_visible(text: str, limit: int) -> str:
    """Cut a coloured line to `limit` printable characters.

    Counting the raw string instead would count every escape sequence as
    visible text and chop the line many columns early - a `Done` row lost its
    elapsed time that way.
    """
    if visible_length(text) <= limit:
        return text
    out: List[str] = []
    shown = 0
    index = 0
    while index < len(text) and shown < limit:
        match = ANSI_PATTERN.match(text, index)
        if match:
            out.append(match.group(0))
            index = match.end()
            continue
        out.append(text[index])
        shown += 1
        index += 1
    out.append(C.RESET)
    return "".join(out)


def supports_unicode() -> bool:
    encoding = getattr(sys.stdout, "encoding", "") or ""
    try:
        "━─".encode(encoding)
        return True
    except (LookupError, UnicodeEncodeError):
        return False


def is_terminal() -> bool:
    try:
        return bool(sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def terminal_size() -> Tuple[int, int]:
    try:
        size = shutil.get_terminal_size((100, 24))
        return max(40, size.columns - 1), max(10, size.lines)
    except OSError:
        return 99, 24


def format_speed(speed: Optional[float]) -> str:
    if not speed or speed <= 0:
        return "--"
    return f"{format_stream_size(int(speed))}/s"


def format_eta(seconds: Optional[float]) -> str:
    # Anything past a day is not a countdown any more, it is a guess.
    if seconds is None or seconds < 0 or seconds > 86400:
        return "--:--"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class SpeedMeter:
    """Bytes per second over a short trailing window."""

    def __init__(self, window: float = SPEED_WINDOW_SECONDS) -> None:
        self._samples: Deque[Tuple[float, int]] = deque()
        self._window = window

    def update(self, completed: int, now: Optional[float] = None) -> None:
        now = time.perf_counter() if now is None else now
        self._samples.append((now, completed))
        while len(self._samples) > 2 and now - self._samples[0][0] > self._window:
            self._samples.popleft()

    def current(self) -> Optional[float]:
        if len(self._samples) < 2:
            return None
        (first_at, first_bytes), (last_at, last_bytes) = self._samples[0], self._samples[-1]
        span = last_at - first_at
        if span <= 0 or last_bytes < first_bytes:
            return None
        return (last_bytes - first_bytes) / span


@dataclass
class ProgressRow:
    """One file's line in the block."""

    name: str
    total: Optional[int] = None
    completed: int = 0
    percent: Optional[float] = None
    state: str = QUEUED
    detail: str = ""
    started_at: Optional[float] = None
    elapsed: float = 0.0
    meter: SpeedMeter = field(default_factory=SpeedMeter)

    @property
    def ratio(self) -> Optional[float]:
        """0..1 when known. An explicit percent wins: FFmpeg reports how much of
        the timeline it has written, which a copy's byte count cannot express."""
        if self.percent is not None:
            return max(0.0, min(1.0, self.percent / 100.0))
        if self.total:
            return max(0.0, min(1.0, self.completed / self.total))
        return None

    def live_elapsed(self) -> float:
        if self.state == ACTIVE and self.started_at is not None:
            return time.perf_counter() - self.started_at
        return self.elapsed


def bar(ratio: Optional[float], width: int, state: str) -> str:
    full_char, empty_char = ("━", "─") if supports_unicode() else ("=", "-")
    width = max(1, width)
    if ratio is None:
        # Unknown progress is drawn as an empty track, never as 0% - a copy that
        # cannot report bytes is not a copy that has done nothing.
        return color(empty_char * width, C.GRAY)
    filled = int(ratio * width)
    fill_color = C.SUMMARY_FAILED if state == FAILED else C.PROCESS_DONE if state == DONE else C.AQUA
    return color(full_char * filled, fill_color) + color(empty_char * (width - filled), C.GRAY)


def stats_line(row: ProgressRow, width: int, show_elapsed: bool = True) -> str:
    bar_width = max(12, min(30, width - 62))
    ratio = row.ratio

    if row.state == QUEUED:
        return (
            f"  {bar(None, bar_width, QUEUED)} "
            f"{color('  Queued', C.GRAY)} | "
            f"{color(format_stream_size(row.total) if row.total else '-', C.GRAY)}"
        )

    if row.state in (DONE, FAILED, SKIPPED):
        label = {DONE: ("Done", C.PROCESS_DONE),
                 FAILED: ("Failed", C.SUMMARY_FAILED),
                 SKIPPED: ("Skipped", C.AMBER)}[row.state]
        line = (
            f"  {bar(1.0 if row.state == DONE else ratio, bar_width, row.state)} "
            f"{color(label[0].rjust(8), label[1])} | "
            f"{color(format_stream_size(row.total) if row.total else '-', C.SKY)}"
        )
        if row.detail:
            line += f" | {color(row.detail, C.GRAY)}"
        if show_elapsed:
            line += f" | {color(format_elapsed_time(row.elapsed), C.SUMMARY_ELAPSED)}"
        return line

    percent_text = f"{ratio * 100:6.1f}%" if ratio is not None else "  --.-%"
    speed = row.meter.current()
    eta = None
    if ratio is not None and speed and row.total:
        remaining = max(0, row.total - row.completed)
        eta = remaining / speed if speed > 0 else None
    elif ratio is not None and 0 < ratio < 1 and row.started_at is not None:
        # No byte meter (FFmpeg reports timeline position, not bytes), so the
        # countdown comes from how long this file has taken to reach `ratio`.
        spent = time.perf_counter() - row.started_at
        eta = spent / ratio - spent if spent > 0 else None

    line = (
        f"  {bar(ratio, bar_width, ACTIVE)} "
        f"{color(percent_text, C.BOLD + C.WHITE)} | "
        f"{color(format_stream_size(row.total) if row.total else '-', C.SKY)}"
    )
    if speed:
        line += f" | {color(format_speed(speed), C.MINT)}"
    if eta is not None:
        line += f" | {color('ETA ' + format_eta(eta), C.LAVENDER)}"
    if show_elapsed:
        line += f" | {color(format_elapsed_time(row.live_elapsed()), C.SUMMARY_ELAPSED)}"
    return line


class ProgressView:
    """The whole block: an Overall line, one group per file, and a status line.

    Frames are driven by the caller's existing poll loop; there is no thread.
    """

    def __init__(self, rows: List[ProgressRow], enabled: Optional[bool] = None) -> None:
        self.rows = rows
        self.enabled = is_terminal() if enabled is None else enabled
        self.status = ""
        self._started_at = time.perf_counter()
        self._lines_drawn = 0
        self._last_frame = 0.0
        self._min_interval = 1.0 / MAX_FRAMES_PER_SECOND
        self._cursor_hidden = False

    # -- row lifecycle ----------------------------------------------------
    def start(self, index: int, status: str = "") -> None:
        row = self.rows[index]
        row.state = ACTIVE
        row.started_at = time.perf_counter()
        row.meter = SpeedMeter()
        if status:
            self.status = status
        self.render(force=True)

    def update(self, index: int, percent: Optional[float] = None,
               completed: Optional[int] = None) -> None:
        row = self.rows[index]
        if percent is not None:
            row.percent = percent
        if completed is not None:
            row.completed = completed
            row.meter.update(completed)
        self.render()

    def finish(self, index: int, state: str, detail: str = "") -> None:
        row = self.rows[index]
        row.state = state
        row.detail = detail
        row.elapsed = row.live_elapsed()
        row.started_at = None
        if state == DONE:
            row.percent = 100.0
            if row.total:
                row.completed = row.total
        self.render(force=True)

    # -- drawing ----------------------------------------------------------
    def overall_line(self, width: int) -> str:
        finished = sum(1 for row in self.rows if row.state in (DONE, FAILED, SKIPPED))
        total_files = len(self.rows)
        ratio = finished / total_files if total_files else 0.0
        # The in-flight file contributes its own fraction, so the overall bar
        # advances during a long file instead of standing still until it ends.
        active = next((r for r in self.rows if r.state == ACTIVE), None)
        if active is not None and active.ratio is not None and total_files:
            ratio += active.ratio / total_files

        bar_width = max(12, min(30, width - 62))
        elapsed = time.perf_counter() - self._started_at
        return (
            f"{color('Overall ', C.BOLD + C.LAVENDER)}{bar(ratio, bar_width, ACTIVE)} "
            f"{color(f'{ratio * 100:6.1f}%', C.BOLD + C.WHITE)} | "
            f"{color(f'{finished}/{total_files} files', C.GOLD)} | "
            f"{color(format_elapsed_time(elapsed), C.SUMMARY_ELAPSED)}"
        )

    def compose(self, width: int, height: int) -> List[str]:
        lines = [self.overall_line(width), ""]

        groups: List[List[str]] = []
        for index, row in enumerate(self.rows, start=1):
            name_color = C.GRAY if row.state == QUEUED else C.SKY
            groups.append([
                color(f"File {index:02d}: ", C.BOLD + C.AZURE) + color(row.name, name_color),
                stats_line(row, width),
            ])

        # Keep the whole block inside the viewport so it repaints without
        # scrolling; when it cannot fit, follow the active file and say how many
        # rows are hidden rather than letting Overall scroll away.
        budget = max(4, height - 5)
        if sum(len(g) for g in groups) <= budget:
            for group in groups:
                lines.extend(group)
        else:
            first_active = next(
                (i for i, r in enumerate(self.rows) if r.state in (QUEUED, ACTIVE)),
                max(0, len(groups) - 1),
            )
            shown: List[int] = []
            used = 0
            cursor = first_active
            while cursor < len(groups) and used + len(groups[cursor]) <= budget - 2:
                shown.append(cursor)
                used += len(groups[cursor])
                cursor += 1
            back = first_active - 1
            while back >= 0 and used + len(groups[back]) <= budget - 2:
                shown.insert(0, back)
                used += len(groups[back])
                back -= 1
            if not shown:
                shown = [first_active]
            if shown[0] > 0:
                lines.append(color(f"... {shown[0]} file(s) above", C.GRAY))
            for i in shown:
                lines.extend(groups[i])
            hidden_below = len(groups) - 1 - shown[-1]
            if hidden_below > 0:
                lines.append(color(f"... +{hidden_below} more file(s) below", C.GRAY))

        if self.status:
            lines.append(color(f"Status: {self.status}", C.GRAY))
        return lines

    def render(self, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        if not force and now - self._last_frame < self._min_interval:
            return
        self._last_frame = now

        width, height = terminal_size()
        lines = [truncate_visible(line, width) for line in self.compose(width, height)]

        buffer: List[str] = []
        if not self._cursor_hidden:
            buffer.append("\x1b[?25l")
            self._cursor_hidden = True

        max_visible = max(2, height - 1)
        oversized = len(lines) > max_visible
        if self._lines_drawn:
            visible = lines[-max_visible:] if oversized else lines
            buffer.append(f"\x1b[{self._lines_drawn}F\x1b[J")
            buffer.append("\n".join(visible) + "\n")
            self._lines_drawn = len(visible)
        else:
            buffer.append("\n".join(lines) + "\n")
            self._lines_drawn = max_visible if oversized else len(lines)

        sys.stdout.write("".join(buffer))
        sys.stdout.flush()

    def close(self) -> None:
        if not self.enabled:
            return
        self.status = ""
        self.render(force=True)
        if self._cursor_hidden:
            sys.stdout.write("\x1b[?25h")
            self._cursor_hidden = False
        sys.stdout.flush()
        self._lines_drawn = 0
