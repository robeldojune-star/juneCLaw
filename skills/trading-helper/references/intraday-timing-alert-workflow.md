# Intraday Timing Alert Workflow Pattern

Use this reference when extending the user's day-trading workflow from pre-market candidate selection into live-session alerting.

## Durable flow

```text
candidate_compression_layer
→ build_today_watchlist.py / today_watchlist stage
→ collect_current_session_snapshots.py every 5 minutes during KRX hours
→ run_intraday_timing_alerts.py OR10/OR30 alert-only evaluation
→ daily_pnl_feedback_report strategy-change review
```

## Data integrity rules

- Use only `intraday_prices` rows where:
  - `source=kiwoom_ka10006_snapshot`
  - `time_frame=snapshot_1m`
- Do not use `ka10005` as minute bars.
- If the watchlist is empty or snapshot rows are insufficient, emit explicit `blocking_conditions`; do not fabricate candidates or bars.

## Script/stage pattern

Recommended scripts/stages:

```text
scripts/build_today_watchlist.py
  stage: today_watchlist
  purpose: candidate_compression_layer → TOP watchlist bridge

scripts/run_intraday_timing_alerts.py
  stages: intraday_timing_alert_10m, intraday_timing_alert_30m
  purpose: today_watchlist + snapshot_1m → OR10/OR30 timing events
```

`run_daily_workflow_stage.py` should expose:

```text
today_watchlist                    08:50
intraday_timing_alert_10m           09:10~15:30
intraday_timing_alert_30m           09:30~15:30
```

`trading_stage_http_server.py` must also allow these stages in `ALLOWED_STAGES`. Restart `trading-runner` after changing allowlists because the running process keeps the old stage list in memory.

## n8n HTTP workflow pattern

For Docker/n8n, keep n8n as scheduler/orchestrator only. Add HTTP Request nodes that call:

```text
POST http://trading-runner:8765/run-stage
```

with body examples:

```json
{"stage":"today_watchlist","timeout":600,"notify":true}
{"stage":"intraday_timing_alert_10m","timeout":600,"notify":true}
{"stage":"intraday_timing_alert_30m","timeout":600,"notify":true}
```

Suggested cron nodes:

```text
08:50 today_watchlist
09:10~15:30 intraday_timing_alert_10m every 5 minutes
09:30~15:30 intraday_timing_alert_30m every 5 minutes
```

Before importing into n8n DB, export a backup of the existing workflow. After import, export again and verify the expected node names exist.

## Safety flags

Intraday timing events are not orders. Keep these fields false until backtest + paper + Leader approval gates pass:

```json
{
  "order_execution_enabled": false,
  "paper_order_allowed": false,
  "real_order_allowed": false,
  "suggested_mode": "alert_only"
}
```

Keep blocker examples:

```text
snapshot_1m_accumulation_and_backtest_required
pattern_model_not_ready_for_auto_order
paper_order_workflow_not_validated
real_order_disabled_until_user_approval
```

## Verification checklist

```bash
python3 -m json.tool workflows/n8n/daily_trading_workflow_v1.http.import.json
python3 -m py_compile scripts/run_intraday_timing_alerts.py scripts/run_daily_workflow_stage.py scripts/trading_stage_http_server.py
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner python scripts/run_daily_workflow_stage.py --stage intraday_timing_alert_10m --pretty || true
```

HTTP path smoke test from n8n container:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T n8n node - <<'NODE'
const http = require('http');
const body = JSON.stringify({stage:'intraday_timing_alert_10m', timeout:600, notify:false});
const req = http.request({hostname:'trading-runner', port:8765, path:'/run-stage', method:'POST', headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}}, res => {
  let data='';
  res.on('data', c => data += c);
  res.on('end', () => { console.log('HTTP', res.statusCode); console.log(data.slice(0, 2000)); });
});
req.on('error', e => { console.error(e); process.exit(1); });
req.write(body);
req.end();
NODE
```

Expected safe blocked state when no morning candidates exist:

```text
ok=false
blocking_conditions includes today_watchlist_empty or no_today_signals_found_for_candidate_compression
order_execution_enabled=false
```
