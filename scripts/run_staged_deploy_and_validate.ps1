# Full staged deploy and validation (final run).
# Prereqs: Docker Desktop running; from repo root.
# Stage 1: after deploy, wait 15-20 min (one snapshot cycle) before running validation.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $root

Write-Host "`n========== STAGE 1: Deploy betfair-rest-client ==========" -ForegroundColor Magenta
docker compose stop betfair-rest-client
docker compose build --no-cache betfair-rest-client
docker compose up -d --force-recreate betfair-rest-client
Write-Host "Waiting 5s for container to start..." -ForegroundColor Gray
Start-Sleep -Seconds 5
Write-Host "Stage 1 deploy done. Wait 15-20 min for one snapshot cycle, then run Stage 1 validation:" -ForegroundColor Yellow
Write-Host "  .\scripts\run_validate_stage1.ps1" -ForegroundColor Cyan
Write-Host "Proceed to Stage 2 only if validation passes. Run this script again and comment out Stage 1, or run stages manually.`n" -ForegroundColor Gray

Read-Host "Press Enter after Stage 1 validation passed to continue to Stage 2"

Write-Host "`n========== STAGE 2: Deploy risk-analytics-ui-api ==========" -ForegroundColor Magenta
docker compose stop risk-analytics-ui-api
docker compose build --no-cache risk-analytics-ui-api
docker compose up -d --force-recreate risk-analytics-ui-api
Start-Sleep -Seconds 5
Write-Host "Running Stage 2 API validation..." -ForegroundColor Cyan
& "$root\scripts\run_validate_stage2_api.ps1"
if ($LASTEXITCODE -ne 0) { Write-Host "Stage 2 validation failed. Stop." -ForegroundColor Red; exit 1 }

Read-Host "Press Enter after confirming Stage 2 to continue to Stage 3"

Write-Host "`n========== STAGE 3: Deploy risk-analytics-ui-web ==========" -ForegroundColor Magenta
docker compose stop risk-analytics-ui-web
docker compose build --no-cache risk-analytics-ui-web
docker compose up -d --force-recreate risk-analytics-ui-web
Write-Host "Stage 3 deploy done. Hard refresh browser (Ctrl+F5) or use Incognito." -ForegroundColor Yellow
Write-Host "Validate: Imbalance unchanged; 'Impedance (norm) (H/A/D)' when enabled; separate charts/columns." -ForegroundColor Cyan
Write-Host "`nStaged deploy and validation complete when Stage 3 UI checks pass." -ForegroundColor Green
