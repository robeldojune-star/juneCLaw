# n8n Docker trading-runner pattern (CLI-first, UI-minimal)

When n8n runs in Docker, do **not** assume host Python paths are executable from n8n nodes.

## Problem pattern

- n8n container often lacks `/home/june/trading` and `python3`.
- `Execute Command` nodes like `cd /home/june/trading && python3 ...` fail in Docker mode.

## Durable fix

1. Add a dedicated `trading-runner` service in Docker Compose.
2. Mount project as `/app` and run a constrained HTTP server:
   - `POST /run-stage` with `{ "stage": "...", "timeout": ..., "notify": true|false }`
3. Convert n8n stage nodes from `Execute Command` to `HTTP Request`:
   - URL: `http://trading-runner:8765/run-stage`
4. Keep stage allowlist in runner (never arbitrary shell execution).

## Telegram pattern in Docker

- Prefer runner-level Telegram notify (`notify=true`) for stage summaries when UI credential wiring is incomplete.
- Read env safely in this order:
  1) `/home/june/trading/.env`
  2) `~/.hermes/.env`
- Accept either `TELEGRAM_CHAT_ID` or `HERMES_TELEGRAM_CHAT_ID`.

## Publish/activation pitfall

`n8n publish:workflow --id=...` can print:

> "Changes will not take effect if n8n is running. Please restart n8n..."

Treat this as actionable. In Docker mode, restart both services after publish:

```bash
docker compose -f /home/june/n8n/docker-compose.yml restart n8n worker
```

Then verify:

```bash
docker exec n8n-postgres-1 psql -U n8nuser -d n8ndb -c \
"select id,name,active from workflow_entity where id='daily_trading_workflow_v1';"
```

## Health-check blocking policy (important)

For `system_health_check` in this stack:

- **Critical (block on fail):** `ka10001`, `kt00004`, `ka10081`
- **Warning only:** `ka10030` volume ranking (mock/env variance can fail intermittently)

If `ka10030` is required for a specific strategy step, enforce there — not in global health gate.

## Quick smoke commands

```bash
# runner health
docker exec n8n-n8n-1 sh -lc 'wget -qO- --timeout=10 http://trading-runner:8765/health'

# stage execution from n8n network
docker exec n8n-n8n-1 sh -lc \
"wget -qO- --timeout=60 --header='Content-Type: application/json' \
 --post-data='{"stage":"system_health_check","timeout":180,"notify":true}' \
 http://trading-runner:8765/run-stage"
```

## UI-minimal operator checklist

If user is not comfortable with n8n UI:

1. Import/update workflow by CLI.
2. Publish workflow by CLI.
3. Restart n8n + worker.
4. Trigger one smoke run from runner endpoint.
5. Ask user for only one UI action: verify execution row + Telegram message.
6. Activate only after smoke is green.
