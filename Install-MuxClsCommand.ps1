# Registers a `MuxCls` command for the current user by adding a `MuxCls` function to the
# user's PowerShell profile(s). Typing `MuxCls` in a PowerShell terminal then launches
# run.ps1 directly - no .cmd shim and no PATH entry required.
#
# Note: `MuxCls` works in PowerShell (pwsh/powershell.exe) only, since profile functions
# are a PowerShell-only mechanism. In cmd.exe, run `.\run.ps1` from this folder instead.
#
# This installer also removes any stale entry for this project folder from the user PATH
# that older versions added (that entry never provided a working `MuxCls` command).

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path -Path $ProjectDir -ChildPath "run.ps1"

if (-not (Test-Path -LiteralPath $Launcher)) {
    Write-Host "ERROR: Launcher was not found: $Launcher" -ForegroundColor Red
    exit 1
}

function Send-EnvironmentChange {
    try {
        if (-not ([System.Management.Automation.PSTypeName]'MuxClsNativeMethods').Type) {
            Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class MuxClsNativeMethods {
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr hWnd,
        uint Msg,
        UIntPtr wParam,
        string lParam,
        uint fuFlags,
        uint uTimeout,
        out UIntPtr lpdwResult);
}
"@
        }

        $result = [UIntPtr]::Zero
        [void][MuxClsNativeMethods]::SendMessageTimeout(
            [IntPtr]0xffff,
            0x001A,
            [UIntPtr]::Zero,
            "Environment",
            0x0002,
            5000,
            [ref]$result)
    }
    catch {
        Write-Warning "Could not broadcast the PATH change. Open a new terminal to refresh PATH."
    }
}

# --- Step 1: remove any stale project-folder entry from the user PATH (older versions) ---

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not [string]::IsNullOrWhiteSpace($UserPath)) {
    $PathParts = @($UserPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $Kept = @($PathParts | Where-Object { $_.TrimEnd('\') -ine $ProjectDir.TrimEnd('\') })
    if ($Kept.Count -ne $PathParts.Count) {
        [Environment]::SetEnvironmentVariable("Path", ($Kept -join ';'), "User")
        Send-EnvironmentChange
        Write-Host "Removed a stale MuxCls folder entry from the user PATH." -ForegroundColor Green
    }
}

# --- Step 2: register a `MuxCls` function in the PowerShell profile(s) ---

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

foreach ($ProfilePath in $ProfilePaths) {
    $ProfileDir = Split-Path -Parent $ProfilePath
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null

    $Content = ""
    if (Test-Path -LiteralPath $ProfilePath) {
        $Content = Get-Content -LiteralPath $ProfilePath -Raw
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

    Set-Content -LiteralPath $ProfilePath -Value $Content -Encoding UTF8
    Write-Host "Updated PowerShell profile: $ProfilePath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Open a new PowerShell terminal, then run: MuxCls" -ForegroundColor Cyan
Write-Host "(The MuxCls function works in PowerShell only. In cmd.exe, run .\run.ps1 instead.)" -ForegroundColor DarkGray
