# Run pytest and show ACTUAL output. Requires Python + pytest in PATH.
# Usage: .\run_pytest_and_capture.ps1
# Or: python -m pytest tests/test_risk.py -v
Set-Location $PSScriptRoot
$out = python -m pytest tests/test_risk.py -v 2>&1
$out
$out | Out-File -FilePath "pytest_output.txt" -Encoding utf8
Write-Host "`n(Output also saved to pytest_output.txt)"
