"""The display-only demo (demo UI/demo_ui.py) draws its screens with the
application's own rendering functions. That is what keeps it honest, and it is
also what makes it fragile: renaming any of those functions breaks the demo
silently, because nothing else imports them together.

This runs the whole walkthrough with one file and no waiting, so a rename shows
up here instead of the next time someone opens the launcher.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo UI"
sys.path.insert(0, str(DEMO_DIR))

# Skip only when the demo is genuinely absent. importorskip would also swallow an
# ImportError from a renamed application function - exactly the failure this file
# exists to catch - and turn it into a green skip.
pytestmark = pytest.mark.skipif(not (DEMO_DIR / "demo_ui.py").exists(),
                                reason="demo UI/demo_ui.py is not present")
if (DEMO_DIR / "demo_ui.py").exists():
    import demo_ui


@pytest.mark.parametrize("scenario", ["remux", "copy", "mixed"])
def test_demo_walkthrough_renders_every_screen(scenario, capsys):
    demo_ui.walkthrough(scenario, count=4, seconds=0)
    out = capsys.readouterr().out

    for marker in ["MuxCls", "Scan Report", "Unique Stream Summary",
                   "Confirm Settings", "Processing Files", "All Done",
                   "Total:", "Elapsed", "END OF DEMO"]:
        assert marker in out, f"{scenario}: the demo never printed {marker!r}"


def test_demo_reports_the_states_only_the_mixed_run_reaches(capsys):
    demo_ui.walkthrough("mixed", count=4, seconds=0)
    out = capsys.readouterr().out

    assert "FAILED to scan" in out
    assert "no video stream found" in out
    assert "SKIP no matching audio selected" in out


LAUNCHER = DEMO_DIR / "Run-Demo.ps1"
PWSH = shutil.which("pwsh")


@pytest.mark.skipif(os.name != "nt" or not PWSH or not LAUNCHER.exists(),
                    reason="the .ps1 launcher needs Windows and pwsh")
def test_launcher_menu_actually_prints_the_walkthrough(tmp_path):
    """The launcher must let the demo's output reach its own stdout.

    This regressed twice the same way: assigning the call that runs the demo
    ($code = Invoke-Demo ...) makes the child's output part of the function's
    return value, so the screen stays blank after choosing a run - and Python,
    seeing a pipe instead of a console, also stops drawing the timer. Driving
    demo_ui.py directly cannot catch that; only the menu path can.
    """
    answers = tmp_path / "menu.txt"
    # change settings -> 1 file -> 0 seconds -> remux run -> exit
    answers.write_text("4\n1\n0\n1\n5\n", encoding="ascii")

    with answers.open("r", encoding="ascii") as stdin:
        proc = subprocess.run(
            [PWSH, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(LAUNCHER), "-NoRelaunch"],
            stdin=stdin, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180,
        )

    assert proc.returncode == 0, proc.stderr[-500:]
    assert "MuxCls - UI demo" in proc.stdout, "the menu itself never appeared"
    for marker in ("Scan Report", "Confirm Settings", "Processing Files",
                   "All Done", "END OF DEMO"):
        assert marker in proc.stdout, f"the launcher swallowed the demo output: {marker!r} missing"


def test_demo_creates_nothing(tmp_path, monkeypatch, capsys):
    # The whole point of the rewrite: no file is produced anywhere.
    monkeypatch.chdir(tmp_path)
    demo_ui.walkthrough("remux", count=2, seconds=0)
    capsys.readouterr()

    assert list(tmp_path.iterdir()) == [], "the demo wrote something"
