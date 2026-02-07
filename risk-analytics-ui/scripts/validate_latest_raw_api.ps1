# Validation: prove GET /api/events/{market_id}/latest_raw works.
# Requires: API running (e.g. http://localhost:8000). Optional: set $ApiBase.
# Usage: .\validate_latest_raw_api.ps1 [market_id]
# If market_id omitted, fetches first league and first event to get one.

$ErrorActionPreference = "Stop"
$ApiBase = if ($env:API_BASE) { $env:API_BASE } else { "http://localhost:8000" }

function Get-FirstMarketId {
    $from = (Get-Date).AddHours(-24).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $to   = (Get-Date).AddHours(24).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $q = "from_ts=$([uri]::EscapeDataString($from))&to_ts=$([uri]::EscapeDataString($to))"
    $leagues = Invoke-RestMethod -Uri "$ApiBase/leagues?$q" -Method Get
    if (-not $leagues -or $leagues.Count -eq 0) {
        Write-Host "No leagues returned. Try a wider time window or check API."
        exit 1
    }
    $leagueName = $leagues[0].league
    $events = Invoke-RestMethod -Uri "$ApiBase/leagues/$([uri]::EscapeDataString($leagueName))/events?$q" -Method Get
    if (-not $events -or $events.Count -eq 0) {
        Write-Host "No events in first league. Try include_in_play=true or wider window."
        exit 1
    }
    return $events[0].market_id
}

$marketId = $args[0]
if (-not $marketId) {
    Write-Host "No market_id provided; fetching first available..."
    $marketId = Get-FirstMarketId
    Write-Host "Using market_id: $marketId"
}

$url = "$ApiBase/events/$marketId/latest_raw"
Write-Host "GET $url"
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri $url -Method Get
    $json = $r | ConvertTo-Json -Depth 3
    $lines = ($json -split "`n")
    $head = if ($lines.Count -gt 30) { $lines[0..29] } else { $lines }
    $head | ForEach-Object { Write-Host $_ }
    if ($lines.Count -gt 30) { Write-Host "..." ; Write-Host "(total lines: $($lines.Count))" }
    Write-Host ""
    Write-Host "OK: latest_raw returned market_id, snapshot_at, raw_payload."
} catch {
    Write-Host "Error: $_"
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "404 = no raw snapshot for this market_id in market_book_snapshots."
    }
    exit 1
}
