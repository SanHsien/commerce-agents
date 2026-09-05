[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Invoke-Step {
    param(
        [Parameter(Mandatory)]
        [string]$Label,
        [Parameter(Mandatory)]
        [string]$Exe,
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    Write-Host "==> $Label"
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

# Canonical gate for this fork (matches the README's "Verify" section and CI's
# `python` job): ruff check, ruff format --check, pytest, then the repo's own
# consistency checks. Runs the same four commands the upstream README documents,
# plus this fork's own maintenance-tool checks.
Invoke-Step -Label "Ruff check" -Exe $pythonExe -Arguments @("-m", "ruff", "check", ".")
Invoke-Step -Label "Ruff format --check" -Exe $pythonExe -Arguments @("-m", "ruff", "format", "--check", ".")
Invoke-Step -Label "Pytest" -Exe $pythonExe -Arguments @("-m", "pytest", "-q")
Invoke-Step -Label "Repo consistency checks (scripts/check.py)" -Exe $pythonExe -Arguments @("scripts\check.py")

Write-Host "==> Check Markdown links (tools/check_links.py)"
& $pythonExe "tools\check_links.py"
if ($LASTEXITCODE -ne 0) {
    throw "Check Markdown links failed with exit code $LASTEXITCODE"
}

Write-Host "WINDOWS DEV CHECK GREEN"
