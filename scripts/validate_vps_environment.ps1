# PowerShell VPS Environment Validation Script
# Run this from the project root on the VPS: .\scripts\validate_vps_environment.ps1
# This performs the pre-verification checks before running the full build verification

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "VPS Environment Validation" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1: Confirm current working directory" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow
$CURRENT_DIR = Get-Location
Write-Host "Current directory: $CURRENT_DIR"
Write-Host ""

# Check if docker-compose.yml exists
if (Test-Path "docker-compose.yml") {
    Write-Host "✓ docker-compose.yml found in current directory" -ForegroundColor Green
} else {
    Write-Host "✗ ERROR: docker-compose.yml NOT found in current directory" -ForegroundColor Red
    Write-Host "  Please run this script from the project root where docker-compose.yml is located." -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "Step 2: Verify the updated source exists on the VPS" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow
Write-Host "Running: Select-String -Pattern 'back and forward from now' -Recurse"
Write-Host ""
$SOURCE_GREP = Select-String -Path . -Pattern "back and forward from now" -Recurse -ErrorAction SilentlyContinue
if (-not $SOURCE_GREP) {
    Write-Host "✗ NOT_FOUND: 'back and forward from now' NOT found in source code" -ForegroundColor Red
    Write-Host "  The VPS source is not updated." -ForegroundColor Red
    Write-Host ""
    Write-Host "Checking if LeaguesAccordion.tsx exists..."
    if (Test-Path "risk-analytics-ui\web\src\components\LeaguesAccordion.tsx") {
        Write-Host "  File exists. Checking contents..."
        Select-String -Path "risk-analytics-ui\web\src\components\LeaguesAccordion.tsx" -Pattern "Time window" | Select-Object -First 3
    } else {
        Write-Host "  File does not exist at expected path"
    }
    exit 1
} else {
    Write-Host "✓ Found 'back and forward from now' in source code:" -ForegroundColor Green
    $SOURCE_GREP | Select-Object -First 5 | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
}
Write-Host ""

Write-Host "Step 3: Confirm Docker build context" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow
Write-Host "Running: docker compose config | Select-String -Pattern 'risk-analytics-ui-web' -Context 0,5"
Write-Host ""
$BUILD_CONTEXT = docker compose config 2>&1 | Select-String -Pattern "risk-analytics-ui-web" -Context 0,5
if (-not $BUILD_CONTEXT) {
    Write-Host "✗ ERROR: Could not find risk-analytics-ui-web in docker compose config" -ForegroundColor Red
    Write-Host "  Full config output:"
    docker compose config 2>&1 | Select-Object -Last 20
    exit 1
} else {
    Write-Host $BUILD_CONTEXT
    Write-Host ""
    # Extract build context path
    $CONTEXT_MATCH = $BUILD_CONTEXT | Select-String -Pattern "context:\s*(.+)" | ForEach-Object { $_.Matches.Groups[1].Value }
    if ($CONTEXT_MATCH) {
        Write-Host "Build context path: $CONTEXT_MATCH"
        if ($CONTEXT_MATCH -match "risk-analytics-ui[\\/]web") {
            Write-Host "✓ Build context appears correct (contains risk-analytics-ui/web)" -ForegroundColor Green
        } else {
            Write-Host "⚠ WARNING: Build context may not point to expected location" -ForegroundColor Yellow
        }
    }
}
Write-Host ""

Write-Host "Step 4: Confirm container currently running" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow
Write-Host "Running: docker ps | Select-String -Pattern 'risk-analytics-ui-web'"
Write-Host ""
$CONTAINER_STATUS = docker ps 2>&1 | Select-String -Pattern "risk-analytics-ui-web"
if (-not $CONTAINER_STATUS) {
    Write-Host "⚠ Container is NOT currently running" -ForegroundColor Yellow
    Write-Host "  Checking if container exists..."
    docker ps -a 2>&1 | Select-String -Pattern "risk-analytics-ui-web" || Write-Host "  Container does not exist"
} else {
    Write-Host "✓ Container is running:" -ForegroundColor Green
    Write-Host $CONTAINER_STATUS
}
Write-Host ""

Write-Host "Step 5: Verify whether the running container contains the updated string" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow
Write-Host "Running: docker exec risk-analytics-ui-web sh -c \"grep -R 'back and forward from now' /usr/share/nginx/html || echo NOT_FOUND\""
Write-Host ""

# Check if container is running first
$CONTAINER_RUNNING = docker ps 2>&1 | Select-String -Pattern "risk-analytics-ui-web"
if ($CONTAINER_RUNNING) {
    $CONTAINER_GREP = docker exec risk-analytics-ui-web sh -c "grep -R 'back and forward from now' /usr/share/nginx/html 2>/dev/null || echo NOT_FOUND" 2>&1
    
    if ($CONTAINER_GREP -match "NOT_FOUND") {
        Write-Host "✗ NOT_FOUND: 'back and forward from now' NOT found in running container" -ForegroundColor Red
        Write-Host "  The current image does not include the updated code." -ForegroundColor Red
        Write-Host ""
        Write-Host "Checking what files exist in container..."
        docker exec risk-analytics-ui-web sh -c "find /usr/share/nginx/html -name '*.js' -type f | head -5" 2>&1
    } elseif ($LASTEXITCODE -ne 0) {
        Write-Host "✗ ERROR: Could not execute command in container" -ForegroundColor Red
    } else {
        Write-Host "✓ Found 'back and forward from now' in container:" -ForegroundColor Green
        $CONTAINER_GREP | Select-Object -First 3 | ForEach-Object { Write-Host "  $_" }
    }
} else {
    Write-Host "⚠ Container is not running. Skipping container check." -ForegroundColor Yellow
    Write-Host "  Start the container first: docker compose -p netbet up -d risk-analytics-ui-web"
}
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Validation Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Please share the following outputs:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Step 2 output (source grep):" -ForegroundColor White
Write-Host "   (Shown above)" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Step 3 output (build context):" -ForegroundColor White
Write-Host "   (Shown above)" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Step 5 output (container grep):" -ForegroundColor White
Write-Host "   (Shown above)" -ForegroundColor Gray
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
