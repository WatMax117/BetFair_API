# Deploy NetBet (auth-service + streaming-client) to VPS
# Usage: .\scripts\deploy_full.ps1

$KEY = "C:\Users\WatMax\.ssh\id_ed25519_contabo"
$VPS = "root@158.220.83.195"
$REMOTE = "/opt/netbet"
$LOCAL = "C:\Users\WatMax\NetBet"

Write-Host "Creating remote directories..."
ssh -i $KEY $VPS "mkdir -p $REMOTE/auth-service $REMOTE/betfair-streaming-client $REMOTE/scripts $REMOTE/logs"

Write-Host "Uploading project..."
scp -i $KEY "$LOCAL\docker-compose.yml" "${VPS}:${REMOTE}/"
scp -i $KEY -r $LOCAL\auth-service\* "${VPS}:${REMOTE}/auth-service/"
scp -i $KEY "$LOCAL\auth-service\.env" "${VPS}:${REMOTE}/auth-service/" 2>$null
scp -i $KEY -r $LOCAL\betfair-streaming-client\* "${VPS}:${REMOTE}/betfair-streaming-client/"
scp -i $KEY "$LOCAL\scripts\run_production_test.sh" "${VPS}:${REMOTE}/scripts/"
scp -i $KEY "$LOCAL\scripts\vps_cleanup_and_deploy.sh" "${VPS}:${REMOTE}/scripts/"

Write-Host "Setting permissions and fixing .env line endings..."
ssh -i $KEY $VPS "chmod -R a+rX $REMOTE/auth-service/certs 2>/dev/null; chmod +x $REMOTE/scripts/*.sh; mkdir -p $REMOTE/logs; chmod 777 $REMOTE/logs; sed -i 's/\r`$//' $REMOTE/auth-service/.env 2>/dev/null; exit 0"

Write-Host "Deploy complete."
Write-Host "Build and start: ssh -i $KEY $VPS `"cd $REMOTE && docker compose build && docker compose up -d`""
Write-Host "Stream logs:     ssh -i $KEY $VPS `"cd $REMOTE && docker compose logs -f streaming-client`""
Write-Host "10-min test:     ssh -i $KEY $VPS `"cd $REMOTE && ./scripts/run_production_test.sh`""
