# Temporary deploy: copy risk-analytics-ui/web from local to VPS and rebuild only the web service.
# Same VPS/SSH as rest-client deploy: root@158.220.83.195, key id_ed25519_contabo.
# No Git, Apache, or backend steps; only the web service is updated.
#
# Prereqs: SSH key and /opt/netbet with docker-compose already set up on VPS.
#
# How to run (from repo root):
#   .\scripts\deploy_risk_analytics_ui_web_to_vps.ps1
# Or:
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy_risk_analytics_ui_web_to_vps.ps1

$ErrorActionPreference = "Stop"
$KEY = "C:\Users\WatMax\.ssh\id_ed25519_contabo"
$VPS = "root@158.220.83.195"
$REMOTE = "/opt/netbet"
$LOCAL = (Get-Item $PSScriptRoot).Parent.FullName

$webSource = Join-Path $LOCAL "risk-analytics-ui\web"
if (-not (Test-Path $webSource)) {
    Write-Error "Local path not found: $webSource (run from repo root or ensure risk-analytics-ui/web exists)"
}

Write-Host "=== 1. Upload risk-analytics-ui/web to VPS (overwrite) ==="
Write-Host "   From: $webSource"
Write-Host "   To:   ${VPS}:${REMOTE}/risk-analytics-ui/  (service at .../risk-analytics-ui/web/)"
& scp -i $KEY -r "$webSource" "${VPS}:${REMOTE}/risk-analytics-ui/"

Write-Host ""
Write-Host "=== 2. On VPS: rebuild and start risk-analytics-ui-web ==="
$script = @'
set -e
cd /opt/netbet
docker compose build --no-cache risk-analytics-ui-web
docker compose up -d --no-deps risk-analytics-ui-web
echo ""
echo "Done. Check http://158.220.83.195/ (hard refresh: Ctrl+Shift+R)."
'@
$script | & ssh -i $KEY $VPS "bash -s"

Write-Host ""
Write-Host "Deploy finished. Validate in production that /api/leagues (single /api) returns 200 and 404s are gone."
