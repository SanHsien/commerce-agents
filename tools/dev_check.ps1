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
# Windows CPython ships no system IANA time zone database, so the suite's clock tests
# fail unless `tzdata` (requirements-dev.txt, Windows-only via an environment marker;
# see docs/DIVERGENCE.md) is installed. Fail here with the fix rather than four
# confusing ValidationErrors 10 seconds later.
& $pythonExe -c "import zoneinfo; zoneinfo.ZoneInfo('Europe/Lisbon')" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No IANA time zone database. Run: $pythonExe -m pip install -r requirements-dev.txt"
}

# One upstream test asserted POSIX 0o600 file permissions, which Windows has no
# equivalent for. It is now fixed at the test-condition level (platform-conditional
# assertion, not a `--deselect`) -- see docs/DIVERGENCE.md for why and how -- so a
# plain `pytest -q` is the real, unmodified gate.
Invoke-Step -Label "Pytest" -Exe $pythonExe -Arguments @("-m", "pytest", "-q")
Invoke-Step -Label "Repo consistency checks (scripts/check.py)" -Exe $pythonExe -Arguments @("scripts\check.py")

Write-Host "==> Check Markdown links (tools/check_links.py)"
& $pythonExe "tools\check_links.py"
if ($LASTEXITCODE -ne 0) {
    throw "Check Markdown links failed with exit code $LASTEXITCODE"
}

Write-Host "==> Check divergence registry (tools/check_divergence.py)"
& $pythonExe "tools\check_divergence.py"
if ($LASTEXITCODE -ne 0) {
    throw "Check divergence registry failed with exit code $LASTEXITCODE"
}

# Dependabot now opens pull requests against requirements.txt and requirements-dev.txt.
# scripts/check.py never reads those files, so this is the only check that catches a bump
# walking a pin outside a range some pyproject.toml declares.
Write-Host "==> Check pins against declared ranges (tools/check_pin_bounds.py)"
& $pythonExe "tools\check_pin_bounds.py"
if ($LASTEXITCODE -ne 0) {
    throw "Check pin bounds failed with exit code $LASTEXITCODE"
}

Write-Host "WINDOWS DEV CHECK GREEN"
