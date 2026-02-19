# Validate /events/{market_id}/buckets: ASC order (oldest first), latest = last element.
# Usage: .\validate_buckets_order.ps1 [-BaseUrl 'http://localhost:8000'] [-MarketId '1.253378204']
param(
    [string]$BaseUrl = $(if ($env:BASE_URL) { $env:BASE_URL } else { 'http://localhost:8000' }),
    [string]$MarketId = '1.253378204'
)
$base = $BaseUrl.TrimEnd('/')
$path = if ($base -match '/stream') { "$base/events/$MarketId/buckets" } else { "$base/stream/events/$MarketId/buckets" }
try {
    $data = Invoke-RestMethod -Uri $path -Method Get
} catch {
    Write-Error "Fetch failed: $_"
    exit 2
}
if (-not ($data -is [Array])) {
    Write-Error "Response is not an array"
    exit 2
}
if ($data.Count -eq 0) {
    Write-Host "OK (no buckets): array empty, order N/A"
    exit 0
}
$starts = @($data | ForEach-Object { $_.bucket_start } | Where-Object { $_ })
if ($starts.Count -eq 0) {
    Write-Error "No bucket_start in response"
    exit 2
}
for ($i = 1; $i -lt $starts.Count; $i++) {
    if ($starts[$i] -le $starts[$i - 1]) {
        Write-Error "Order violation: index $i '$($starts[$i])' <= previous '$($starts[$i - 1])'"
        exit 1
    }
}
$first = $starts[0]
$last = $starts[-1]
Write-Host "OK: buckets in ASC order (oldest first). Count: $($data.Count)"
Write-Host "  First (oldest): $first"
Write-Host "  Last (latest):  $last"
exit 0
