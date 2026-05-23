# Removes this MuxCls folder from the current user's PATH.

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")

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

if ([string]::IsNullOrWhiteSpace($UserPath)) {
    Write-Host "MuxCls is not installed in the user PATH." -ForegroundColor Yellow
    exit 0
}

$PathParts = @($UserPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$NewPathParts = @($PathParts | Where-Object { $_.TrimEnd('\') -ine $ProjectDir.TrimEnd('\') })

if ($NewPathParts.Count -eq $PathParts.Count) {
    Write-Host "MuxCls is not installed in the user PATH." -ForegroundColor Yellow
    exit 0
}

$NewPath = $NewPathParts -join ';'
[Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
Send-EnvironmentChange

Write-Host "MuxCls was removed from the user PATH." -ForegroundColor Green
Write-Host "Open a new terminal to use the updated PATH." -ForegroundColor Cyan
