# Cron Job Setup Lessons Learned (2026-06-01)

## Overview
Documented lessons learned from setting up Hermes cron jobs for the RSI/CCI strategy, including path issues and environment variable handling.

## Key Issues Encountered

### 1. Path Resolution in Cron Jobs
- Cron jobs run in a minimal environment without user shell initialization
- Relative paths in scripts fail because the working directory is not the user's home or project directory
- Solution: Use absolute paths or explicitly set `workdir` parameter in cron job creation

### 2. Environment Variable Loading
- Cron jobs don't automatically source user's `.bashrc` or `.profile`
- Environment variables like `TRADING_ENV` and Kiwoom credentials must be explicitly set in the cron job prompt or script
- Solution: Either set environment variables directly in the cron job prompt or create a wrapper script that sources the environment

### 3. Working Directory Problems
- The `run_strategy.py` script relies on relative paths to access:
  - Shared modules (`shared/`)
  - Environment files (`envs/`)
  - Dashboard signal logging (`dashboard/data/`)
- When cron job runs from wrong directory, imports and file access fail

## Recommended Solutions

### Solution 1: Use workdir Parameter (Preferred)
When creating the cron job, specify the working directory explicitly:
```bash
hermes cronjob create \
    --name rsi_cci_live \
    --schedule '*/1 9-15 * * 1-5' \
    --prompt "python3 scripts/run_strategy.py --env prod --stock 042660 --execute --quantity 1" \
    --workdir /home/june/trading \
    --deliver telegram:<your_chat_id>
```

### Solution 2: Wrapper Script Approach
Create a wrapper script that handles environment setup:
```bash
#!/usr/bin/env bash
# File: /home/june/.hermes/scripts/run_rsi_cci.sh
cd /home/june/trading
source envs/prod/.env  # or mock/.env as appropriate
python3 scripts/run_strategy.py --stock 042660 --execute --quantity 1
```

Then reference this script in the cron job:
```bash
hermes cronjob create \
    --name rsi_cci_live \
    --schedule '*/1 9-15 * * 1-5' \
    --prompt "/home/june/.hermes/scripts/run_rsi_cci.sh" \
    --workdir /home/june/trading \
    --deliver telegram:<your_chat_id>
```

### Solution 3: Inline Environment Variables
Set environment variables directly in the cron prompt:
```bash
hermes cronjob create \
    --name rsi_cci_live \
    --schedule '*/1 9-15 * * 1-5' \
    --prompt "TRADING_ENV=prod python3 /home/june/trading/scripts/run_strategy.py --stock 042660 --execute --quantity 1" \
    --workdir /home/june/trading \
    --deliver telegram:<your_chat_id>
```

## Verification Steps
1. Test the command manually first: `cd /home/june/trading && TRADING_ENV=prod python3 scripts/run_strategy.py --stock 042660 --execute --quantity 1`
2. Check that signals are being logged to dashboard/data/signals.csv
3. Verify Telegram alerts are received if using --execute
4. Monitor cron job output: `hermes cronjob list` then check `~/.hermes/cron/output/<job_id>/` for logs

## Files Related to Cron Setup
- `scripts/run_strategy.py` - main strategy script
- `shared/` directory - core logic modules
- `envs/mock/.env` and `envs/prod/.env` - environment-specific credentials
- `dashboard/data/signals.csv` - where signals are logged for visualization
- Wrapper scripts in `~/.hermes/scripts/` (optional)