# Deploy auth-service to VPS
# Usage: .\scripts\deploy_to_vps.ps1

$KEY = "C:\Users\WatMax\.ssh\id_ed25519_contabo"
$VPS = "root@158.220.83.195"
$REMOTE_BASE = "/opt/netbet"
$REMOTE = "/opt/netbet/auth-service"
$LOCAL = "C:\Users\WatMax\NetBet\auth-service"

Write-Host "Creating remote directory..."
ssh -i $KEY $VPS "mkdir -p $REMOTE"
Write-Host "Uploading auth-service files..."
scp -i $KEY -r $LOCAL\* "${VPS}:${REMOTE}/"
Write-Host "Uploading .env (dotfile)..."
scp -i $KEY "$LOCAL\.env" "${VPS}:${REMOTE}/"
Write-Host "Setting cert permissions for container..."
ssh -i $KEY $VPS "chmod -R a+rX $REMOTE/certs"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Deploy complete. To build/start and stream logs:"
    Write-Host "  ssh -i $KEY $VPS `"cd $REMOTE && docker compose build && docker compose up -d && docker compose logs -f`""
} else {
    Write-Host "Upload failed. Ensure SSH key and VPS are reachable."
}
