# Adds this MuxCls folder to the current user's PATH so `MuxCls` works in new terminals.

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ([string]::IsNullOrWhiteSpace($UserPath)) {
    $PathParts = @()
}
else {
    $PathParts = $UserPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
}

$AlreadyInstalled = $PathParts | Where-Object { $_.TrimEnd('\') -ieq $ProjectDir.TrimEnd('\') }

if (-not $AlreadyInstalled) {
    $NewPath = (@($PathParts) + $ProjectDir) -join ';'
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "MuxCls was added to the user PATH." -ForegroundColor Green
    Write-Host "Open a new terminal, then run: MuxCls" -ForegroundColor Cyan
}
else {
    Write-Host "MuxCls is already in the user PATH." -ForegroundColor Green
}
