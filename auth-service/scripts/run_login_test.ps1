# Betfair Login Test
# Uses .env and certs/client-2048.p12
Set-Location $PSScriptRoot\..

# Try Docker first
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "Running login test via Docker..."
    docker compose run --rm auth-service python -c @"
import os
from dotenv import load_dotenv
load_dotenv()
from src.auth_service import BetfairAuthService
auth = BetfairAuthService(
    app_key=os.getenv('BETFAIR_APP_KEY'),
    username=os.getenv('BETFAIR_USERNAME'),
    password=os.getenv('BETFAIR_PASSWORD'),
    cert_path='/certs/client-2048.p12',
    cert_password=os.getenv('CERT_PASSWORD'),
)
if auth.login():
    t = auth.get_session_token()
    print('SUCCESS: Login verified. Token:', t[:30] + '...' if t and len(t) > 30 else t)
    exit(0)
else:
    print('FAILED: Login failed.')
    exit(1)
"@
    exit $LASTEXITCODE
}

# Fallback: Python
$py = @('python', 'py -3', 'python3') | Where-Object { 
    $cmd = ($_ -split ' ')[0]
    Get-Command $cmd -ErrorAction SilentlyContinue 
} | Select-Object -First 1
if ($py) {
    Write-Host "Running login test via Python..."
    & python scripts/verify_login.py
    exit $LASTEXITCODE
}

Write-Host "Need Docker Desktop or Python. Start Docker and retry, or: pip install -r requirements.txt && python scripts/verify_login.py"
exit 1
