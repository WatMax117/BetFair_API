# Run 10-minute CSV data logging against a live football market
# 1. Discover market ID (requires Python + auth service)
# 2. Run Java stream client with CSV logging for 10 minutes

$ErrorActionPreference = "Stop"

Write-Host "Step 1: Discovering live football market..."
$marketId = python scripts/discover_live_football.py 2>$null
if (-not $marketId) {
    Write-Host "Discovery failed. Ensure Python auth service is running and reachable."
    Write-Host "You can set market ID manually: `$env:BETFAIR_MARKET_ID='1.234567890'"
    $marketId = $env:BETFAIR_MARKET_ID
}
if (-not $marketId) {
    exit 1
}
Write-Host "Market ID: $marketId"

Write-Host "Step 2: Starting stream (10 min, CSV logging to ./logs)..."
mvn spring-boot:run "-Dspring-boot.run.profiles=datalogging" "-Dspring-boot.run.arguments=--betfair.market-id=$marketId"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
Write-Host "Done. CSVs in ./logs/"
