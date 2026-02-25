# NetBet Auth Service – VPS Deployment

## VPS Details

- **Target**: Ubuntu VPS at `158.220.83.195`
- **SSH**: Use SSH keys; disable password authentication

## SSH Key Setup

### 1. Generate SSH key (if needed)

```bash
ssh-keygen -t ed25519 -C "netbet-deploy" -f ~/.ssh/netbet_deploy
```

### 2. Copy public key to VPS

```bash
ssh-copy-id -i ~/.ssh/netbet_deploy.pub user@158.220.83.195
```

### 3. Disable password authentication (on VPS)

Edit `/etc/ssh/sshd_config`:

```
PasswordAuthentication no
PermitRootLogin prohibit-password   # or create a dedicated deploy user
```

Then: `sudo systemctl restart sshd`

### 4. Create dedicated deployment user (recommended)

```bash
sudo adduser deploy
sudo usermod -aG docker deploy
sudo mkdir -p /opt/netbet/auth-service
sudo chown deploy:deploy /opt/netbet -R
```

## Deploy

```bash
# From your local machine
scp -i ~/.ssh/netbet_deploy -r ./* deploy@158.220.83.195:/opt/netbet/auth-service/

# SSH and start
ssh deploy@158.220.83.195 "cd /opt/netbet/auth-service && cp .env.example .env && docker compose up -d"
```

**Important**: Copy `.env.example` to `.env` and edit with real credentials before first run. Place SSL certs in `./certs/` on the VPS.
