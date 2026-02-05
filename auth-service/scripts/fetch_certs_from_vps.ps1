# Fetch client-2048.p12 from VPS (betfair-bot deployment)
# Usage: .\scripts\fetch_certs_from_vps.ps1
# Requires: SSH key at C:\Users\WatMax\.ssh\id_ed25519_contabo

$VPS = "root@158.220.83.195"
$KEY = "C:\Users\WatMax\.ssh\id_ed25519_contabo"
$REMOTE = "/root/NetBet/betfair-bot/certs/client-2048.p12"
$LOCAL = "C:\Users\WatMax\NetBet\auth-service\certs\client-2048.p12"

$certsDir = Split-Path -Parent $LOCAL
if (-not (Test-Path $certsDir)) { New-Item -ItemType Directory -Path $certsDir -Force | Out-Null }

Write-Host "Fetching client-2048.p12 from VPS..."
scp -i $KEY "${VPS}:${REMOTE}" $LOCAL
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: Saved to $LOCAL"
    Write-Host "Run: python scripts/verify_login.py"
} else {
    Write-Host "Failed. Check: key path, VPS reachability, remote path."
    Write-Host "Alternative path on VPS: /root/betfair-bot/certs/client-2048.p12"
}
