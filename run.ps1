# MuxCls PowerShell Launcher
# Put this .ps1 file in the same folder as "MuxCls.py".

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PassThruArgs
)

$Host.UI.RawUI.WindowTitle = "MuxCls"

Clear-Host

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host " MuxCls Launcher" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$PythonScript = Join-Path $ScriptDir "MuxCls.py"

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

Write-Host "Working folder:" -ForegroundColor Cyan
Write-Host $ScriptDir -ForegroundColor White
Write-Host ""
Write-Host "Python script:" -ForegroundColor Cyan
Write-Host $PythonScript -ForegroundColor White
Write-Host ""
Write-Host "Running..." -ForegroundColor Cyan
Write-Host ""

& $PythonCmd @PythonArgs @PassThruArgs
exit $LASTEXITCODE
