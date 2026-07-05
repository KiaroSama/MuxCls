# Adds this MuxCls folder to the current user's PATH so `run.ps1` can be run by name in new terminals.

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$MaxUserPathLength = 2047

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
        Write-Warning "Could not broadcast the PATH change. Open a new terminal before running run.ps1."
    }
}

if ([string]::IsNullOrWhiteSpace($UserPath)) {
    $PathParts = @()
}
else {
    $PathParts = @($UserPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

$AlreadyInstalled = @($PathParts | Where-Object { $_.TrimEnd('\') -ieq $ProjectDir.TrimEnd('\') })

if (-not $AlreadyInstalled) {
    $NewPath = (@($PathParts) + $ProjectDir) -join ';'

    if ($NewPath.Length -gt $MaxUserPathLength) {
        Write-Host "ERROR: The user PATH would become too long to update safely." -ForegroundColor Red
        Write-Host "Current length: $($UserPath.Length)" -ForegroundColor Yellow
        Write-Host "New length: $($NewPath.Length)" -ForegroundColor Yellow
        Write-Host "Remove unused entries from the user PATH, then run this installer again." -ForegroundColor Yellow
        exit 1
    }

    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Send-EnvironmentChange
    Write-Host "MuxCls was added to the user PATH." -ForegroundColor Green
    Write-Host "Open a new terminal, then run: run.ps1" -ForegroundColor Cyan
    Write-Host "To remove it later, delete this folder from your user PATH (Environment Variables)." -ForegroundColor Cyan
}
else {
    Write-Host "MuxCls is already in the user PATH." -ForegroundColor Green
    Write-Host "To remove it, delete this folder from your user PATH (Environment Variables)." -ForegroundColor Cyan
}
