<#
Monthly retrain automation.

Runs the recommender pipeline and shows you the log so you can check
the anchor month, product count, and any warnings before anything
goes live. It deliberately stops there -- git add/commit/push are
always a manual final step you run yourself. See RETRAIN.md.
#>

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

# generate.log is written as UTF-8 (it contains arrows: "->"); without
# this, Get-Content reads it as the console's codepage and the arrows
# come out as mangled bytes.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Prefer the project's own venv python so this works even in a fresh
# terminal where the venv hasn't been manually activated -- generate.py
# depends on packages (pandas, xlrd, rapidfuzz...) only installed there.
$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "python"
}

Write-Host "Running scripts\generate.py ..." -ForegroundColor Cyan
& $Python scripts\generate.py
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    Write-Host ""
    Write-Host "generate.py FAILED (exit code $ExitCode)." -ForegroundColor Red
    Write-Host "Nothing was committed. See the error above, or logs\generate.log, for details." -ForegroundColor Red
    exit $ExitCode
}

Write-Host ""
Write-Host "generate.py finished. Last 20 lines of logs\generate.log:" -ForegroundColor Cyan
Write-Host "----------------------------------------------------------"
Get-Content "logs\generate.log" -Tail 20 -Encoding UTF8
Write-Host "----------------------------------------------------------"

Write-Host ""
Write-Host "Check the anchor month, product count, and any WARNING lines above." -ForegroundColor Yellow
Write-Host "If it looks correct, publish it yourself with:" -ForegroundColor Yellow
Write-Host ""
Write-Host "    git add docs\schedule.json"
Write-Host "    git commit -m `"Retrain -- <month> <year> data`""
Write-Host "    git push"
Write-Host ""
