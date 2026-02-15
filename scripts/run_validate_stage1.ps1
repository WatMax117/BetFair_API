# Stage 1 validation: run after deploying betfair-rest-client and at least one snapshot cycle.
# Requires: netbet-postgres container running; psql available via docker exec.
# Usage: from repo root, .\scripts\run_validate_stage1.ps1

$ErrorActionPreference = "Stop"
$schema = "rest_ingest"

Write-Host "=== Stage 1.1: Check impedance columns exist (expect 6 rows) ===" -ForegroundColor Cyan
$cols = @"
SELECT column_name
FROM information_schema.columns
WHERE table_schema = '$schema'
  AND table_name = 'market_derived_metrics'
  AND column_name IN (
    'home_impedance', 'away_impedance', 'draw_impedance',
    'home_impedance_norm', 'away_impedance_norm', 'draw_impedance_norm'
  )
ORDER BY column_name;
"@
docker exec -i netbet-postgres psql -U netbet -d netbet -t -A -c $cols
$count = (docker exec -i netbet-postgres psql -U netbet -d netbet -t -A -c $cols | Measure-Object -Line).Lines
if ([int]$count -lt 6) {
  Write-Host "FAIL: Expected 6 columns, got $count" -ForegroundColor Red
  exit 1
}
Write-Host "OK: 6 impedance columns present" -ForegroundColor Green

Write-Host "`n=== Stage 1.2: Recent rows with non-null impedance ===" -ForegroundColor Cyan
$recent = @"
SELECT COUNT(*) FROM ${schema}.market_derived_metrics
WHERE snapshot_at >= NOW() - INTERVAL '7 days'
  AND (home_impedance_norm IS NOT NULL OR away_impedance_norm IS NOT NULL OR draw_impedance_norm IS NOT NULL);
"@
$recentCount = [int](docker exec -i netbet-postgres psql -U netbet -d netbet -t -A -c $recent)
Write-Host $recentCount
if ($recentCount -lt 1) {
  Write-Host "FAIL: No recent rows with non-null impedance. Run another snapshot cycle or widen the interval." -ForegroundColor Red
  exit 1
}
Write-Host "OK: $recentCount recent row(s) with non-null impedance" -ForegroundColor Green

Write-Host "`n=== Stage 1.3: REST client logs ([Impedance] lines) ===" -ForegroundColor Cyan
docker logs netbet-betfair-rest-client --tail=200 2>&1 | Select-String -Pattern "\[Impedance\]"
if (-not $?) { Write-Host "No [Impedance] lines in last 200 log lines (may be OK if no markets processed yet)." -ForegroundColor Yellow }

Write-Host "`nStage 1 validation script finished. Confirm above and proceed to Stage 2." -ForegroundColor Cyan
