"""The installer rewrites the user's PowerShell profile - a file it does not own.

These tests run the real splice logic out of `Install-MuxClsCommand.ps1` against
throwaway profile files, under whichever PowerShell editions are installed. The
original code used `Get-Content -Raw` / `Set-Content -Encoding UTF8`, whose
default encodings differ between Windows PowerShell 5.1 and PowerShell 7:
measured, a UTF-8 profile with no BOM lost its non-ASCII text under 5.1, and a
legacy-encoded one gained replacement characters under 7. Either way the damage
lands in lines the user wrote.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parent.parent / "Install-MuxClsCommand.ps1"

# Non-ASCII that a real profile might carry: Persian, an em dash, an accent.
NON_ASCII = "سلام — café"

SHELLS = [name for name in ("pwsh", "powershell.exe") if shutil.which(name)]
requires_powershell = pytest.mark.skipif(not SHELLS, reason="no PowerShell available")


def _splice_script(profile: Path) -> str:
    """The installer's profile-rewriting loop, pointed at one throwaway file.

    Lifted from the script itself so the test exercises the shipped logic rather
    than a paraphrase of it: everything from the `foreach` down is taken
    verbatim, with the profile list replaced by our temporary path.
    """
    source = INSTALLER.read_text(encoding="utf-8")
    start = source.index("foreach ($ProfilePath in $ProfilePaths) {")
    end = source.index("Write-Host \"\"", start)
    body = source[start:end]

    escaped = str(profile).replace("'", "''")
    return (
        "$Begin = '# BEGIN MuxCls command'\n"
        "$End = '# END MuxCls command'\n"
        "$Block = $Begin + [Environment]::NewLine + 'function MuxCls { }' + "
        "[Environment]::NewLine + $End\n"
        f"$ProfilePaths = @('{escaped}')\n"
        + body
    )


def _run(shell: str, profile: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    script = tmp_path / "splice.ps1"
    script.write_text(_splice_script(profile), encoding="utf-8")
    return subprocess.run(
        [shell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, timeout=120,
    )


@requires_powershell
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("bom", [False, True], ids=["no-bom", "bom"])
def test_the_users_own_lines_survive_the_rewrite(shell, bom, tmp_path):
    profile = tmp_path / "Microsoft.PowerShell_profile.ps1"
    original = f"# {NON_ASCII}\nfunction Get-Existing {{ '{NON_ASCII}' }}\n"
    profile.write_text(original, encoding="utf-8-sig" if bom else "utf-8")

    result = _run(shell, profile, tmp_path)
    assert result.returncode == 0, result.stderr

    rewritten = profile.read_bytes().decode("utf-8-sig")
    assert NON_ASCII in rewritten, f"{shell} destroyed the user's non-ASCII text"
    assert "function Get-Existing" in rewritten
    assert "# BEGIN MuxCls command" in rewritten


@requires_powershell
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("bom", [False, True], ids=["no-bom", "bom"])
def test_the_bom_state_of_the_file_is_preserved(shell, bom, tmp_path):
    profile = tmp_path / "Microsoft.PowerShell_profile.ps1"
    profile.write_text("# existing\n", encoding="utf-8-sig" if bom else "utf-8")

    assert _run(shell, profile, tmp_path).returncode == 0

    has_bom = profile.read_bytes()[:3] == b"\xef\xbb\xbf"
    assert has_bom is bom, "adding or dropping a BOM rewrites a file the user owns"


@requires_powershell
@pytest.mark.parametrize("shell", SHELLS)
def test_a_profile_that_is_not_utf8_is_left_untouched(shell, tmp_path):
    """Fail closed: a legacy-encoded profile cannot be re-encoded without
    guessing, and guessing wrong corrupts lines MuxCls never wrote."""
    profile = tmp_path / "Microsoft.PowerShell_profile.ps1"
    original = "# café legacy profile\n".encode("cp1252")
    profile.write_bytes(original)

    result = _run(shell, profile, tmp_path)

    assert result.returncode == 0, result.stderr
    assert profile.read_bytes() == original, "the file was rewritten despite not being UTF-8"
    assert "Skipped" in result.stdout


@requires_powershell
@pytest.mark.parametrize("shell", SHELLS)
def test_running_twice_replaces_the_block_instead_of_stacking_it(shell, tmp_path):
    profile = tmp_path / "Microsoft.PowerShell_profile.ps1"
    profile.write_text("# existing\n", encoding="utf-8")

    _run(shell, profile, tmp_path)
    _run(shell, profile, tmp_path)

    text = profile.read_text(encoding="utf-8-sig")
    assert len(re.findall(r"# BEGIN MuxCls command", text)) == 1
    assert "# existing" in text


def test_the_installer_no_longer_uses_the_editions_default_encoding():
    """A guard on the shipped script: `Get-Content -Raw` / `Set-Content` in the
    profile loop reintroduce the edition-dependent behaviour these tests exist
    to prevent, and no test would catch it on a machine with one edition."""
    source = INSTALLER.read_text(encoding="utf-8")
    loop = source[source.index("foreach ($ProfilePath in $ProfilePaths) {"):]

    assert "Get-Content" not in loop
    assert "Set-Content" not in loop
    assert "[System.IO.File]::ReadAllBytes" in loop
    assert "[System.IO.File]::WriteAllText" in loop
