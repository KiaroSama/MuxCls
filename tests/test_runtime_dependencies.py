"""The README promises "No external Python packages are required". Nothing checked it.

A dependency creeps in by import, not by manifest: someone writes `import requests`
in one module, it works on the machine that already has it, and the promise is quietly
false for everyone else. Neither the suite nor CI would notice - pytest, ruff and mypy
all bring third-party packages into the environment, so a check that looks at
`sys.modules` from inside a test run can only ever see them.

So the check runs in a fresh interpreter that imports the package and nothing else, and
reports what actually landed in `sys.modules`. That is the only place the answer is real.
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Imports every module in the package, then names anything that is not part of the
# standard library and not the package itself. `sys.stdlib_module_names` is the
# interpreter's own list, so it stays correct as the floor moves.
PROBE = """
import importlib, pkgutil, sys
import muxcls

for module in sorted(m.name for m in pkgutil.iter_modules(muxcls.__path__)):
    importlib.import_module("muxcls." + module)

outside = sorted({
    name.split(".")[0]
    for name in sys.modules
    if name.split(".")[0] not in sys.stdlib_module_names
    and not name.startswith("_")
    and name.split(".")[0] != "muxcls"
})
print("MODULES:" + ",".join(outside))
"""


def _probe() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        check=False, capture_output=True, text=True,
        cwd=PROJECT_ROOT, timeout=120,
    )
    assert result.returncode == 0, (
        "importing the package in a fresh interpreter failed:\n" + result.stderr[-2000:]
    )
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("MODULES:"))
    return [name for name in line[len("MODULES:"):].split(",") if name]


def test_the_package_imports_nothing_outside_the_standard_library():
    """The runtime guarantee the README states, and the one this project would break
    silently: every module has to import cleanly with no third-party package present."""
    outside = _probe()

    assert outside == [], (
        "muxcls imported non-standard-library packages: " + ", ".join(outside)
        + " - the README promises none are required, so either drop the import or "
        "change that promise and add the dependency to a manifest"
    )


def test_the_probe_can_actually_see_a_third_party_import(tmp_path, monkeypatch):
    """A guard that cannot fail is not a guard. This runs the same probe against a
    package that deliberately imports something outside the standard library, so a
    future change to `PROBE` that stops detecting anything fails here instead of
    passing the test above for the wrong reason."""
    fake = tmp_path / "muxcls"
    fake.mkdir()
    (fake / "__init__.py").write_text("", encoding="utf-8")
    # pytest is certainly importable and certainly not stdlib.
    (fake / "uses_a_dependency.py").write_text("import pytest\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        check=False, capture_output=True, text=True,
        cwd=tmp_path, timeout=120,
    )

    assert result.returncode == 0, result.stderr[-2000:]
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("MODULES:"))
    assert "pytest" in line, (
        "the probe did not report a third-party import it was handed on purpose: " + line
    )
