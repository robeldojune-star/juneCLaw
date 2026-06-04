# Trading System Backup & Restore Checklist

## What to Backup

### 1. Source Code & Config (Git tracked)
- `/home/june/trading/` (already in git)
  - Strategies, backtests, scripts, docs, dashboard, etc.

### 2. Environment & Secrets (NOT in git)
- `.env` (API keys, DB passwords, etc.)
- Any files under `envs/` containing credentials
- SSH keys, GPG keys if used

### 3. Data & State
- `/home/june/trading/data/` (SQLite, CSV, raw data)
- `/home/june/.hermes/` (Hermes agent config, skills, model cache, sessions)
  - `config.yaml`
  - `skills/`
  - `model_cache/` (optional)
  - `sessions/`
  - `webui/attachments/` (UI uploads)
- Any custom model files or checkpoints

### 4. Logs (optional, for debugging)
- `/home/june/trading/logs/`
- `/home/june/.hermes/webui/bootstrap-*.log`
- System logs: `/var/log/syslog`, `/var/log/caddy/`

### 5. Service Configurations
- `/etc/caddy/Caddyfile` (reverse proxy for WebUI)
- `/etc/systemd/system/caddy.service.d/duckdns.conf` (if any)
- `/etc/duckdns/duckdns.sh` (if using DuckDNS updater)
- Any custom NGINX/Apache configs

### 6. Cron Jobs
- Output of `crontab -l` (user cron)
- System cron: `/etc/cron.d/`, `/etc/cron.daily/`, etc.
- Hermes cron jobs: `hermes cron list` (store output)

### 7. Miscellaneous
- List of installed Python packages: `pip freeze > requirements.txt`
- List of installed system packages (dpkg/apt list)
- SSH config (`~/.ssh/config`) if used for remote access
- Backup of this checklist and restore script (self-referential)

## How to Backup (example commands)

```bash
# 1. Ensure git is up-to-date
cd /home/june/trading
git add -A
git commit -m "Pre-backup snapshot: $(date +%F_%T)"
git push

# 2. Copy secrets and data
rsync -av --progress /home/june/trading/.env /path/to/backup/
rsync -av --progress /home/june/trading/envs/ /path/to/backup/envs/
rsync -av --progress /home/june/trading/data/ /path/to/backup/data/
rsync -av --progress /home/june/.hermes/ /path/to/backup/hermes/
rsync -av --progress /home/june/.hermes/webui/attachments/ /path/to/backup/attachments/
rsync -av --progress /etc/caddy/Caddyfile /path/to/backup/caddy/
rsync -av --progress /etc/systemd/system/caddy.service.d/ /path/to/backup/caddy-service.d/
crontab -l > /path/to/backup/crontab.txt
hermes cron list > /path/to/backup/hermes_cron.txt
pip freeze > /path/to/backup/requirements.txt
dpkg --get-selections > /path/to/backup/pkg_list.txt
```

## How to Restore

```bash
#!/usr/bin/env bash
set -euo pipefail

# ==== CONFIGURE THESE ====
BACKUP_ROOT="/path/to/backup"   # <-- change to where you stored the backup
TARGET_HOME="/home/june"
# =========================

echo "=== Restore Trading System from $BACKUP_ROOT ==="

# 1. Restore source code (git)
if [ -d "$TARGET_HOME/trading" ]; then
  echo "Trading directory exists, pulling latest..."
  cd "$TARGET_HOME/trading"
  git reset --hard HEAD
  git pull origin main
else
  echo "Cloning trading repo..."
  git clone https://github.com/robeldojune-star/juneCLaw.git "$TARGET_HOME/trading"
fi

# 2. Restore secrets & env
echo "Restoring .env and envs..."
cp -v "$BACKUP_ROOT/.env" "$TARGET_HOME/trading/" 2>/dev/null || true
cp -rv "$BACKUP_ROOT/envs/" "$TARGET_HOME/trading/" 2>/dev/null || true

# 3. Restore data
echo "Restoring data..."
cp -rv "$BACKUP_ROOT/data/" "$TARGET_HOME/trading/" 2>/dev/null || true

# 4. Restore Hermes config & cache
echo "Restoring Hermes agent files..."
mkdir -p "$TARGET_HOME/.hermes"
cp -rv "$BACKUP_ROOT/hermes/"* "$TARGET_HOME/.hermes/" 2>/dev/null || true

# 5. Restore WebUI attachments
echo "Restoring WebUI attachments..."
mkdir -p "$TARGET_HOME/.hermes/webui/attachments"
cp -rv "$BACKUP_ROOT/attachments/"* "$TARGET_HOME/.hermes/webui/attachments/" 2>/dev/null || true

# 6. Restore Caddy config
echo "Restoring Caddy configuration..."
sudo cp -v "$BACKUP_ROOT/caddy/Caddyfile" /etc/caddy/Caddyfile 2>/dev/null || true
sudo cp -rv "$BACKUP_ROOT/caddy-service.d/"* /etc/systemd/system/caddy.service.d/ 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl reload caddy 2>/dev/null || true

# 7. Restore cron jobs
echo "Restoring user crontab..."
crontab "$BACKUP_ROOT/crontab.txt" 2>/dev/null || true
echo "Restoring Hermes cron jobs (informational only):"
cat "$BACKUP_ROOT/hermes_cron.txt" 2>/dev/null || true

# 8. Restore Python environment (optional)
echo "Recreating Python environment from requirements..."
cd "$TARGET_HOME/trading"
if [ -f "$BACKUP_ROOT/requirements.txt" ]; then
  python3 -m venv venv
  source venv/bin/activate
  pip install -r "$BACKUP_ROOT/requirements.txt"
fi

# 9. Verify
echo "=== Restore complete ==="
echo "Please check:"
echo " - Trading code: $TARGET_HOME/trading"
echo " - Hermes config: $TARGET_HOME/.hermes/config.yaml"
echo " - WebUI URL: https://june-hermes.duckdns.org"
echo " - Remember to restart any services (hermes gateway, dashboard, etc.)"
```

**Notes**
- Replace `/path/to/backup` with your actual backup location (external drive, cloud storage, etc.).
- Run the restore script as the same user that runs Hermes (`june`).
- After restoring, you may need to re‑export environment variables (`source .env`) or restart the Hermes gateway and dashboard.
- Test the restore on a non‑production machine first if possible.

---
*Last updated: $(date +%F)*