# PowerShell diagnostic script for both issues
# Run on Windows or via SSH to VPS: pwsh scripts/diagnose_both_issues.ps1

Write-Host "=== Snapshot Ingestion & Impedance Diagnostic ===" -ForegroundColor Cyan
Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')" -ForegroundColor Gray
Write-Host ""

# 1. Check container status
Write-Host "--- Container Status ---" -ForegroundColor Yellow
docker ps --filter "name=betfair-rest-client" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>&1
Write-Host ""

# 2. Check latest snapshot timestamp
Write-Host "--- Latest Snapshot Timestamp ---" -ForegroundColor Yellow
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    MAX(snapshot_at) as latest_snapshot_at,
    COUNT(*) as total_snapshots,
    COUNT(DISTINCT market_id) as distinct_markets,
    NOW() as current_time,
    EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_at))) as seconds_since_latest
FROM rest_ingest.market_book_snapshots;
" 2>&1
Write-Host ""

# 3. Check impedance columns and data
Write-Host "--- Impedance Data Check ---" -ForegroundColor Yellow
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    COUNT(*) as total_rows,
    COUNT(home_impedance) as rows_with_home_impedance,
    COUNT(home_impedance_norm) as rows_with_home_impedance_norm,
    MAX(snapshot_at) as latest_snapshot_with_impedance
FROM rest_ingest.market_derived_metrics;
" 2>&1
Write-Host ""

# 4. Sample recent snapshot with impedance
Write-Host "--- Sample Recent Snapshot with Impedance ---" -ForegroundColor Yellow
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    snapshot_id,
    snapshot_at,
    market_id,
    home_impedance,
    home_impedance_norm,
    away_impedance,
    draw_impedance
FROM rest_ingest.market_derived_metrics
WHERE home_impedance IS NOT NULL
ORDER BY snapshot_at DESC
LIMIT 3;
" 2>&1
Write-Host ""

# 5. Check container logs for errors
Write-Host "--- Recent Errors in Logs (last 20) ---" -ForegroundColor Yellow
docker logs --tail 200 netbet-betfair-rest-client 2>&1 | Select-String -Pattern "error|warning|exception|failed" -CaseSensitive:$false | Select-Object -Last 20
Write-Host ""

Write-Host "=== Diagnostic Complete ===" -ForegroundColor Cyan
