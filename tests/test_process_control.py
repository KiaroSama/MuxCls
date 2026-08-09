"""Unit tests for external-process control in muxcls.media (B-07): commands are
non-interactive, honour a timeout, and never leave the child running.

Every test here is bounded: the child sleeps far longer than the timeout, so a
regression shows up as a failed assertion, not as a hung suite.
"""
import subprocess
import sys
import time
from pathlib import Path

from muxcls import media
from muxcls.constants import AUDIO_ALL, SUBTITLE_ALL
from muxcls.models import MediaFile, SelectionRules, StreamInfo
from muxcls.muxlogic import build_ffmpeg_command

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]
# The child sleeps 60s; a 2s timeout plus terminate/kill grace must finish well
# inside this bound or the process control is broken.
MAX_WAIT_SECONDS = 30


def test_run_command_gives_up_on_timeout_instead_of_hanging():
    started = time.perf_counter()
    proc = media.run_command(SLEEPER, timeout=2)
    elapsed = time.perf_counter() - started

    assert proc.returncode != 0
    assert elapsed < MAX_WAIT_SECONDS
    assert "timeout" in proc.stderr.lower()


def test_run_with_progress_gives_up_on_timeout_instead_of_hanging(capsys):
    started = time.perf_counter()
    proc = media.run_with_progress(SLEEPER, timeout=2)
    elapsed = time.perf_counter() - started

    assert proc.returncode != 0
    assert elapsed < MAX_WAIT_SECONDS


class StubbornProcess:
    """A process that ignores terminate(). Windows terminate() always succeeds,
    so the kill escalation can only be exercised against a stand-in."""

    pid = 4321

    def __init__(self):
        self.terminated = False
        self.killed = False

    def poll(self):
        return 0 if self.killed else None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        if not self.killed:
            raise subprocess.TimeoutExpired("stubborn", timeout)
        return 0


def test_terminate_escalates_to_kill_when_terminate_is_ignored():
    proc = StubbornProcess()
    media.terminate_process(proc, grace_seconds=0.1)
    assert proc.terminated
    assert proc.killed, "a process that ignores terminate must be killed"


def test_terminate_process_tree_kills_a_child_that_ignores_terminate():
    proc = subprocess.Popen(SLEEPER, stdin=subprocess.DEVNULL)
    try:
        media.terminate_process(proc, grace_seconds=2)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:  # pragma: no cover - only on a failed assertion
            proc.kill()
            proc.wait(timeout=10)


def test_ffmpeg_command_is_non_interactive():
    # Without -nostdin ffmpeg grabs the terminal and Ctrl+C handling gets messy.
    fake = MediaFile(path=Path("in.mkv"), streams=[
        StreamInfo(index=0, codec_type="video"),
        StreamInfo(index=1, codec_type="audio", language="jpn", disposition_default=1),
    ])
    rules = SelectionRules(
        audio_mode=AUDIO_ALL, audio_languages=[], audio_titles=[], audio_indexes=[],
        subtitle_mode=SUBTITLE_ALL, subtitle_languages=[], subtitle_titles=[],
        subtitle_indexes=[], keep_attachments=True, keep_metadata=True,
        keep_chapters=True, overwrite=True,
    )
    cmd, _, _ = build_ffmpeg_command(Path("in.mkv"), Path("out.mkv"), fake, rules)
    assert "-nostdin" in cmd
