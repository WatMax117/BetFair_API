# PowerShell verification script for UI Docker build
# Run this from the project root on the VPS: .\scripts\verify_ui_build.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 1: Verify updated source exists" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$grepResult = Select-String -Path . -Pattern "back and forward from now" -Recurse -ErrorAction SilentlyContinue
if ($grepResult) {
    Write-Host "✓ Found 'back and forward from now' in source code" -ForegroundColor Green
    $grepResult | Select-Object -First 5 | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber)" }
} else {
    Write-Host "✗ ERROR: 'back and forward from now' NOT found in source code" -ForegroundColor Red
    Write-Host "  The change is not present in the deployed source directory." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 2: Confirm Docker build context" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "Checking docker-compose.yml build context..."
if (Test-Path "docker-compose.yml") {
    Write-Host "Main docker-compose.yml:"
    Get-Content "docker-compose.yml" | Select-String -Pattern "risk-analytics-ui-web" -Context 0,5
}

if (Test-Path "risk-analytics-ui\docker-compose.yml") {
    Write-Host ""
    Write-Host "risk-analytics-ui\docker-compose.yml:"
    Get-Content "risk-analytics-ui\docker-compose.yml" | Select-String -Pattern "risk-analytics-ui-web" -Context 0,5
}

Write-Host ""
Write-Host "Running: docker compose config"
docker compose config | Select-String -Pattern "risk-analytics-ui-web" -Context 0,5

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 3: Rebuild with --no-cache" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Building risk-analytics-ui-web with --no-cache..."
Write-Host "This may take a few minutes..."

$buildLog = docker compose -p netbet build --no-cache risk-analytics-ui-web 2>&1
$buildLog | Tee-Object -FilePath "$env:TEMP\build.log"

if ($buildLog | Select-String -Pattern "error" -CaseSensitive:$false | Where-Object { $_ -notmatch "WARNING" }) {
    Write-Host ""
    Write-Host "⚠ WARNING: Errors detected in build log. Check $env:TEMP\build.log for details." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "✓ Build completed. Check logs above for TypeScript/Vite compilation status." -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 4: Restart container" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Restarting risk-analytics-ui-web container..."
docker compose -p netbet up -d risk-analytics-ui-web
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 5: Verify built bundle contains change" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Checking inside container at /usr/share/nginx/html..."

$containerCheck = docker exec risk-analytics-ui-web sh -c "grep -r 'back and forward from now' /usr/share/nginx/html 2>/dev/null" 2>&1
if ($LASTEXITCODE -eq 0 -and $containerCheck) {
    Write-Host "✓ Found 'back and forward from now' in built bundle!" -ForegroundColor Green
    $containerCheck | Select-Object -First 3 | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "✗ ERROR: 'back and forward from now' NOT found in built bundle" -ForegroundColor Red
    Write-Host "  The Docker image does not include the updated code." -ForegroundColor Red
    Write-Host ""
    Write-Host "Checking what files exist in the container..."
    docker exec risk-analytics-ui-web sh -c "find /usr/share/nginx/html -name '*.js' -type f | head -5"
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Verification Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✓ Source code contains the change" -ForegroundColor Green
Write-Host "✓ Docker build completed" -ForegroundColor Green
Write-Host "✓ Built bundle contains the change" -ForegroundColor Green
Write-Host ""
Write-Host "The UI should now display the updated label."
Write-Host "Please verify in your browser that the label shows:"
Write-Host "  'Time window (hours back and forward from now)'" -ForegroundColor Yellow
