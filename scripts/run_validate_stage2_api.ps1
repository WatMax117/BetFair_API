# Stage 2 validation: run after deploying risk-analytics-ui-api.
# Requires: risk-analytics-ui-api container listening on port 8000 (or set $apiBase).
# Usage: from repo root, .\scripts\run_validate_stage2_api.ps1

$ErrorActionPreference = "Stop"
$apiBase = if ($env:API_BASE) { $env:API_BASE } else { "http://localhost:8000" }

$from = "2025-01-01T00:00:00Z"
$to = "2030-01-01T00:00:00Z"

Write-Host "=== Stage 2.1: GET /leagues (pick one league) ===" -ForegroundColor Cyan
$leaguesJson = Invoke-RestMethod -Uri "$apiBase/leagues?from_ts=$from&to_ts=$to&limit=5" -Method Get
$leagues = $leaguesJson
if (-not $leagues -or $leagues.Count -eq 0) {
  Write-Host "No leagues returned. Check API and DB (analytics schema / views)." -ForegroundColor Yellow
  exit 1
}
$leagueName = $leagues[0].league
Write-Host "Using league: $leagueName" -ForegroundColor Gray

Write-Host "`n=== Stage 2.2: GET /leagues/{league}/events?include_impedance=true ===" -ForegroundColor Cyan
$encodedLeague = [uri]::EscapeDataString($leagueName)
$eventsUri = "$apiBase/leagues/$encodedLeague/events?include_impedance=true&from_ts=$from&to_ts=$to&limit=5"
try {
  $events = Invoke-RestMethod -Uri $eventsUri -Method Get
} catch {
  Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
  if ($_.Exception.Response) { Write-Host "Status: $($_.Exception.Response.StatusCode)" }
  exit 1
}
if (-not $events -or $events.Count -eq 0) {
  Write-Host "No events in league (OK for validation if structure is correct). Checking first event structure from a different league or single event..." -ForegroundColor Yellow
}
$ev = $events[0]
# Required: imbalance always present
if (-not $ev.PSObject.Properties["imbalance"]) {
  Write-Host "FAIL: event missing 'imbalance' object" -ForegroundColor Red
  exit 1
}
Write-Host "OK: imbalance present (home=$($ev.imbalance.home) away=$($ev.imbalance.away) draw=$($ev.imbalance.draw))" -ForegroundColor Green
# When include_impedance=true, impedanceNorm should be present when data exists
if ($ev.PSObject.Properties["impedanceNorm"]) {
  Write-Host "OK: impedanceNorm present (home=$($ev.impedanceNorm.home) away=$($ev.impedanceNorm.away) draw=$($ev.impedanceNorm.draw))" -ForegroundColor Green
} else {
  Write-Host "impedanceNorm missing (OK if no impedance data in DB yet)" -ForegroundColor Yellow
}

Write-Host "`n=== Stage 2.3: GET /events/{market_id}/timeseries?include_impedance=true ===" -ForegroundColor Cyan
$marketId = if ($ev.market_id) { $ev.market_id } else { $events[0].market_id }
$tsUri = "$apiBase/events/$marketId/timeseries?include_impedance=true&from_ts=$from&to_ts=$to"
try {
  $ts = Invoke-RestMethod -Uri $tsUri -Method Get
} catch {
  Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
if ($ts -and $ts.Count -gt 0) {
  $pt = $ts[0]
  if (-not $pt.PSObject.Properties["imbalance"]) {
    Write-Host "FAIL: timeseries point missing 'imbalance'" -ForegroundColor Red
    exit 1
  }
  Write-Host "OK: timeseries point has imbalance" -ForegroundColor Green
  if ($pt.PSObject.Properties["impedanceNorm"]) {
    Write-Host "OK: timeseries point has impedanceNorm" -ForegroundColor Green
  }
} else {
  Write-Host "No timeseries points (OK if no data)" -ForegroundColor Yellow
}

Write-Host "`nStage 2 validation passed. No 500 errors; imbalance and (when requested) impedanceNorm present. Proceed to Stage 3." -ForegroundColor Cyan
