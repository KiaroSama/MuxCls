# Registers a `MuxCls` command for the current user by adding a `MuxCls` function to the
# user's PowerShell profile(s). Typing `MuxCls` in a PowerShell terminal then launches
# run.ps1 directly - no .cmd shim and no PATH entry required.
#
# Note: `MuxCls` works in PowerShell (pwsh/powershell.exe) only, since profile functions
# are a PowerShell-only mechanism. In cmd.exe, run `.\run.ps1` from this folder instead.

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path -Path $ProjectDir -ChildPath "run.ps1"

if (-not (Test-Path -LiteralPath $Launcher)) {
    Write-Host "ERROR: Launcher was not found: $Launcher" -ForegroundColor Red
    exit 1
}

# --- Register a `MuxCls` function in the PowerShell profile(s) ---

$Documents = [Environment]::GetFolderPath("MyDocuments")
$ProfilePaths = @(
    (Join-Path $Documents "PowerShell\Microsoft.PowerShell_profile.ps1"),
    (Join-Path $Documents "WindowsPowerShell\Microsoft.PowerShell_profile.ps1")
)

$Begin = "# BEGIN MuxCls command"
$End = "# END MuxCls command"
$EscapedLauncher = $Launcher.Replace("'", "''")
$Block = @"
$Begin
function MuxCls {
    `$launcher = '$EscapedLauncher'
    `$pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if (`$pwsh) {
        & `$pwsh.Source -NoLogo -NoProfile -ExecutionPolicy Bypass -File `$launcher @args
    } else {
        & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File `$launcher @args
    }
}
$End
"@

# The profile belongs to the user, not to MuxCls: this rewrites the whole file,
# including lines it did not write. Get-Content/Set-Content cannot do that
# safely here, because their default encodings differ between Windows
# PowerShell 5.1 and PowerShell 7 - measured, a UTF-8 profile with no BOM comes
# back from 5.1 with its non-ASCII text destroyed, and a legacy-encoded one
# comes back from 7 full of replacement characters. The .NET calls below behave
# the same on both: they honour a BOM when present, assume UTF-8 when not, and
# write back in whichever of the two forms the file already used.
foreach ($ProfilePath in $ProfilePaths) {
    $ProfileDir = Split-Path -Parent $ProfilePath
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null

    $Content = ""
    $HadBom = $false
    if (Test-Path -LiteralPath $ProfilePath) {
        $Bytes = [System.IO.File]::ReadAllBytes($ProfilePath)
        $HadBom = $Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF

        # Decode strictly. If the profile is not UTF-8, rewriting it would
        # silently corrupt the user's own lines, so leave it alone and say so.
        try {
            $Strict = New-Object System.Text.UTF8Encoding($false, $true)
            $Start = if ($HadBom) { 3 } else { 0 }
            $Content = $Strict.GetString($Bytes, $Start, $Bytes.Length - $Start)
        }
        catch {
            Write-Host "Skipped (not UTF-8, so it cannot be rewritten safely): $ProfilePath" -ForegroundColor Yellow
            Write-Host "  Re-save that file as UTF-8, or paste this block into it yourself:" -ForegroundColor DarkGray
            Write-Host $Block -ForegroundColor DarkGray
            continue
        }
    }

    $Pattern = [regex]::Escape($Begin) + "(?s).*?" + [regex]::Escape($End)
    if ($Content -match $Pattern) {
        $Content = [regex]::Replace($Content, $Pattern, $Block)
    }
    elseif ([string]::IsNullOrWhiteSpace($Content)) {
        $Content = $Block + [Environment]::NewLine
    }
    else {
        $Content = $Content.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + $Block + [Environment]::NewLine
    }

    [System.IO.File]::WriteAllText($ProfilePath, $Content, (New-Object System.Text.UTF8Encoding($HadBom)))
    Write-Host "Updated PowerShell profile: $ProfilePath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Open a new PowerShell terminal, then run: MuxCls" -ForegroundColor Cyan
Write-Host "(The MuxCls function works in PowerShell only. In cmd.exe, run .\run.ps1 instead.)" -ForegroundColor DarkGray
