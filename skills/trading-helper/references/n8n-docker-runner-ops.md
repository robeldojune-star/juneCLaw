# n8n Docker trading-runner operations

Use this reference when operating the trading project's n8n daily workflow in Docker.

## Durable pattern

When n8n runs inside Docker, do **not** rely on Execute Command nodes to run host paths such as `/home/june/trading` or host Python. Instead:

1. Mount the trading repo into a dedicated `trading-runner` service.
2. Expose an internal-only HTTP endpoint, e.g. `http://trading-runner:8765/run-stage`.
3. Let n8n use HTTP Request nodes with JSON bodies:

```json
{"stage":"system_health_check","timeout":180,"notify":true}
```

4. The runner should whitelist stage names and execute only:

```bash
python scripts/run_daily_workflow_stage.py --stage <stage>
```

5. Keep secrets out of n8n stdout. Let the runner read project `.env` and, when needed, Hermes `.env` for Telegram token/chat ID fallback without printing values.

## Activation sequence

Recommended safe sequence after changing workflow JSON:

```bash
python3 -m json.tool workflows/n8n/daily_trading_workflow_v1.http.import.json >/dev/null
python3 -m json.tool workflows/n8n/leader_approval_order_workflow.template.json >/dev/null

docker cp workflows/n8n/daily_trading_workflow_v1.http.import.json n8n-n8n-1:/tmp/daily_trading_workflow_v1.http.import.json
docker exec n8n-n8n-1 n8n import:workflow --input=/tmp/daily_trading_workflow_v1.http.import.json --projectId=<project_id>

docker exec n8n-n8n-1 n8n publish:workflow --id=daily_trading_workflow_v1
docker compose -f /home/june/n8n/docker-compose.yml restart n8n worker
```

Verify activation:

```bash
docker exec n8n-postgres-1 psql -U n8nuser -d n8ndb -c \
  "select id,name,active,\"updatedAt\" from workflow_entity where id='daily_trading_workflow_v1';"

docker logs --since 10m n8n-n8n-1 | grep -E 'Activated workflow|published workflows|Start Active Workflows'
```

A healthy activation log contains:

```text
Activated workflow "daily_trading_workflow_v1_docker_http" (ID: daily_trading_workflow_v1)
```

## Alert-spam guard

High-frequency intraday nodes should not send Telegram on every run. Use `notify=false` for stages that run every 5 minutes unless the runner implements conditional alerting.

Recommended defaults:

| Stage class | notify |
|---|---:|
| system health, daily news, watchlist summary, daily PnL | true |
| 5-minute snapshot collection | false |
| 5-minute intraday timing alert scan | false until conditional alert logic exists |
| opening/approval summaries | true or conditional |

## Orphan cleanup

After adding/removing nodes, statically validate:

- every connection source exists
- every connection target exists
- non-note nodes are not orphaned, except manual triggers and cron triggers
- all HTTP Request nodes point to `http://trading-runner:8765/run-stage`

Remove leftover placeholder nodes such as disconnected IF/Telegram smoke nodes once runner `notify=true` is the real alert path.

## Leader paper-order workflow

The Leader approval workflow should remain inactive by default and be run manually/explicitly. Its paper-order node should call:

```json
{"stage":"simulate_approved_orders","timeout":300,"notify":true}
```

Paper order constraints:

- create `SIMULATED` orders only
- never call Kiwoom live-order APIs
- require candidates, risk checks, budget checks, and explicit approval gates before real-order workflows are considered

## Known n8n reverse proxy warning

If n8n is behind Caddy/reverse proxy, logs may show an `X-Forwarded-For` / `trust proxy` warning. It does not necessarily block workflow execution, but should be cleaned up with the n8n version-appropriate proxy setting such as `N8N_PROXY_HOPS=1`.
