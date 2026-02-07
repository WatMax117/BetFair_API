# Run risk unit tests. Requires: pip install -r requirements-dev.txt
Set-Location $PSScriptRoot
& python -m pytest tests/test_risk.py -v --tb=short
if ($LASTEXITCODE -ne 0) { & python3 -m pytest tests/test_risk.py -v --tb=short }
exit $LASTEXITCODE
