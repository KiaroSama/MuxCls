# MuxCls PowerShell Launcher
# Put this .ps1 file in the same folder as "MuxCls.py".

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PassThruArgs
)

$Host.UI.RawUI.WindowTitle = "MuxCls"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    $env:TERM = "xterm-256color"
    if (Get-Variable -Name PSStyle -Scope Global -ErrorAction SilentlyContinue) {
        $PSStyle.OutputRendering = "Ansi"
    }
}
catch {
    # Console color support is best-effort; the Python app also enables ANSI output.
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "MuxCls.py"

Set-Location $ScriptDir

if (-not (Test-Path $PythonScript)) {
    Write-Host "ERROR: MuxCls.py was not found next to this launcher." -ForegroundColor Red
    Write-Host ""
    Write-Host "Expected path:" -ForegroundColor Yellow
    Write-Host $PythonScript -ForegroundColor White
    Write-Host ""
    exit 1
}

$PythonCmd = $null
$PythonArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $PythonCmd = "py"
        $PythonArgs = @("-3", $PythonScript)
    }
}

if (-not $PythonCmd -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $PythonCmd = "python"
        $PythonArgs = @($PythonScript)
    }
}

if (-not $PythonCmd) {
    Write-Host "ERROR: Python was not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install Python or add it to PATH, then run this launcher again." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

& $PythonCmd @PythonArgs @PassThruArgs
exit $LASTEXITCODE
