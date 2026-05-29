# 현재 트레이딩 운영 실행 계획 — ka10006 snapshot_1m 안정화 기준

상태: **현재 기준 문서 / 운영 우선순위 확정**  
작성 기준: 2026-05-29 현재 `/home/june/trading` 실제 운영 상태  
목표: `ka10005` 분봉 오염을 배제하고, `ka10006` 장중 snapshot 누적 데이터를 기반으로 오프닝 전략/백테스트/승인형 주문을 단계적으로 복구한다.

---

## 1. 현재 확정 방향

```text
전략 철학은 유지한다.
데이터 소스 전제는 ka10005 분봉 후보에서 ka10006 snapshot_1m 누적으로 전환한다.
n8n 중심 운영은 중단하고, Hermes cron + trading-runner 직접 호출을 1차 운영 경로로 쓴다.
백테스트와 paper 검증 전까지 실주문은 계속 blocked 상태로 둔다.
```

---

## 2. 현재 실제 운영 구조

```text
Hermes cron, no_agent=true
  -> ~/.hermes/scripts/trading_snapshot_collector.py
      -> docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner
          -> python scripts/run_daily_workflow_stage.py --stage collect_current_session_snapshots
              -> Kiwoom ka10006 current-session snapshot
                  -> Supabase intraday_prices
          -> python scripts/inspect_snapshot_1m_status.py
              -> 정상: stdout empty / 이상: Hermes alert
```

저장 식별자:

```text
source = kiwoom_ka10006_snapshot
time_frame = snapshot_1m
```

현재 n8n 위치:

```text
n8n daily_trading_workflow_v1 = active=true
n8n은 일일 오케스트레이션/알림/향후 승인 UI 후보로 유지한다.
장중 snapshot_1m 반복 수집의 1차 경로는 Hermes cron이며, n8n의 collect_current_session_snapshots 노드는 중복 방지를 위해 disabled 상태다.
n8n intraday_timing_alert_10m/30m은 snapshot_1m read-only 평가만 수행하며 notify=false로 유지한다.
```

---

## 3. 폐기된 전제

아래 전제는 더 이상 현재 계획의 기준이 아니다.

```text
ka10005를 1분/5분 분봉 소스로 사용한다.
ka10005 date-only 응답을 intraday_prices time_frame=1min으로 저장한다.
n8n active workflow가 장중 수집을 책임진다.
백테스트 전 BUY 후보를 자동 주문으로 연결한다.
```

`ka10005` 관련 단계는 아래처럼 해석한다.

| 예전 표현 | 현재 해석 |
|---|---|
| `ka10005_timeframe_needs_market_hours_validation` | `ka10005`는 분봉 소스로 사용 금지 |
| `ka10005` 90일 intraday backfill | 검증된 별도 minute-history API가 나오기 전까지 disabled |
| `intraday_prices / ka10005 후보` | `intraday_prices / ka10006 snapshot_1m accumulation` |

---

## 4. 전체 단계

### Phase 1 — 수집 안정화/무결성 확인

목표:

```text
장중 5분마다 실제 ka10006 snapshot_1m이 누락/오염 없이 쌓이는지 확인한다.
```

작업:

1. `scripts/inspect_snapshot_1m_status.py`로 최근 snapshot 상태 점검
2. 종목별 row count, 날짜 범위, 최신 timestamp 확인
3. OHLC 구조 오류, 중복 timestamp, source/time_frame 혼입 확인
4. 이상 시 명확한 `blocking_conditions` 출력
5. 필요하면 Hermes cron watchdog에 품질검사 hook 추가

검증 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/inspect_snapshot_1m_status.py --days 2 --min-rows 20
```

현재 단계: **운영 감시 연결 완료 / 장중 수집 정상**

2026-05-29 확인값:

```text
Hermes cron 156937d1ec14 = enabled, */5 * * * *, last_status=ok
Hermes cron 69cc2e19a78c = enabled, 15:45 weekday readiness report
inspect_snapshot_1m_status = ok
rows=601 / active_codes=14 / duplicate=0 / quality_error_counts={}
latest_lag_minutes는 장후에는 증가하므로 hard block으로 보지 않음; 장중에만 lag gate 적용
```

---

### Phase 2 — 오프닝 전략 후보 루프 안전 검증

목표:

```text
OR10/OR30 후보 평가가 snapshot_1m만 사용하고, 데이터 부족 시 blocked로 끝나는지 확인한다.
```

대상 stage:

```text
opening_10m_aggressive_layer
opening_30m_standard_layer
```

검증 기준:

- `snapshot_1m` 외 분봉 소스 사용 금지
- 후보별 score breakdown 출력
- 데이터 부족/패턴 미검증 시 `blocking_conditions` 유지
- 자동 주문 guard 유지

검증 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_10m_aggressive_layer --pretty

docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_30m_standard_layer --pretty
```

2026-05-29 확인값:

```text
OR10/OR30 모두 collect_current_session_snapshots 선행 실행 OK
run_opening_strategy_research.py는 time_frame=eq.snapshot_1m, source=eq.kiwoom_ka10006_snapshot만 조회
candidate_count=0이면 opening_candidate_list_empty로 blocked
order_execution_enabled=false, auto_order_guard 유지
```

---

### Phase 2.5 — today_watchlist + 장중 타이밍 알림

목표:

```text
아침 브리핑/후보 압축 결과를 오늘 감시할 TOP 5~10 watchlist로 고정하고,
장중에는 snapshot_1m 기반 OR10/OR30/거래량/돌파 조건을 빠르게 감시해
타이밍 후보를 놓치지 않도록 알림을 발생시킨다.
```

기준 문서:

```text
docs/strategies/today_watchlist_intraday_timing_alert_design_v1.md
docs/strategies/today_watchlist_intraday_timing_alert_schema_v1.json
```

핵심 원칙:

- `today_watchlist`는 장 시작 전 `candidate_compression_layer` 결과를 확장해 만든다.
- 장중 감시는 `source=kiwoom_ka10006_snapshot`, `time_frame=snapshot_1m`만 사용한다.
- 초기 상태는 `alert_only` 또는 `ENTRY_TIMING_CANDIDATE`까지만 허용한다.
- `paper_order_allowed=false`, `real_order_allowed=false`를 기본값으로 둔다.
- 알림은 낼 수 있지만, `snapshot_1m_accumulation_and_backtest_required`가 있으면 주문 가능 신호로 해석하지 않는다.

구현/예상 파일:

```text
scripts/build_today_watchlist.py          # 완료: candidate_compression_layer → today_watchlist 표준 변환
scripts/run_intraday_timing_alerts.py     # 완료: today_watchlist + snapshot_1m → 장중 timing event 평가
```

2026-05-29 연결 상태:

```text
run_daily_workflow_stage.py --stage today_watchlist 등록 완료
run_daily_workflow_stage.py --stage intraday_timing_alert_10m / intraday_timing_alert_30m 등록 완료
trading_stage_http_server.py ALLOWED_STAGES에 today_watchlist 및 intraday_timing_alert_10m/30m 등록 완료
workflows/n8n/daily_trading_workflow_v1.http.import.json에 08:50 today_watchlist, 09:10~15:30 intraday_timing_alert_10m, 09:30~15:30 intraday_timing_alert_30m 노드 추가 완료
n8n DB workflow daily_trading_workflow_v1에 import 완료; import 전 백업은 .hermes/backups/daily_trading_workflow_v1.before_intraday_import.json
현재 실행 결과는 오늘 BUY signal 부재로 today_watchlist_empty blocked; 주문 안전값 false 유지
```

---

### Phase 3 — 백테스트 준비도 게이트

목표:

```text
데이터가 충분히 쌓이기 전에는 백테스트가 성공처럼 보이지 않게 막는다.
```

필수 차단 조건 후보:

```text
snapshot_1m_accumulation_and_backtest_required
need_90_trading_days_intraday_prices
insufficient_intraday_rows_for_backtest
insufficient_backtest_trade_count
```

검증 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage backtest_opening_strategy_90d --pretty
```

2026-05-29 확인값:

```text
time_frame=snapshot_1m으로 실행됨
rows_used=43 / min_rows_required=300
total_variant_trades=0 / min_trades_required=5
status=blocked
blocking_conditions=[insufficient_intraday_rows_for_backtest, insufficient_backtest_trade_count]
```

---

### Phase 4 — 일일 운영 리포트

목표:

```text
장후에 수집 상태, 신호, 차단 사유, 손익/미체결/실패 원인을 리포트화한다.
```

추가된 항목:

- snapshot_1m 최신 timestamp
- 장중 수집 row count
- active stock count
- 품질 오류/중복 여부
- OR10/OR30 후보와 차단 사유
- PnL 또는 paper 결과가 있을 경우 신호 대비 실행 비교

2026-05-29 확인값:

```text
daily_pnl_feedback_report.summary.snapshot_1m_accumulation 포함 완료
snapshot rows=141 / active_codes=10 / latest_lag_minutes=약 3분 / quality_error_counts={}
PnL 리포트 자체는 no_today_signals_found이면 blocked 유지
```

---

### Phase 4.5 — 전략 수정 후보 리포트

목표:

```text
daily/weekly feedback에서 반복 관찰된 문제를 strategy_change_candidate로 분리하고,
검증 전에는 threshold/weight/order behavior를 즉시 변경하지 않는다.
```

수정 후보 예시:

| 관찰 결과 | 수정 후보 |
|---|---|
| BUY 후보가 계속 0개 | 후보 압축 기준/점수 임계값 검토 |
| 신호가 너무 늦음 | OR10/OR30 조건 또는 알림 주기 조정 |
| 돌파 후 자주 실패 | false breakout 필터 추가 |
| 거래 수가 너무 적음 | 임계값 과도 보수 여부 검토 |
| 손실 변동성이 큼 | 손절/포지션 크기 조정 |

반영 절차:

```text
관찰 → strategy_change_candidate → 백테스트/paper 검증 → 사용자 승인 → strategy_registry/code 반영
```

2026-05-29 연결 상태:

```text
daily_pnl_feedback_report.py에 intraday_timing_alert_summary, missed_timing_events, strategy_change_candidates 연결 완료
현재 리포트 실행 결과: snapshot_1m rows=221, active_codes=10, quality_errors=0, latest_lag≈6분
today_signal_count=0이므로 strategy_change_candidates에 no_today_signals_review 후보 1개 생성
모든 strategy_change_candidates는 candidate_only이며 approved_for_code_change=false
```

---

### Phase 5 — Leader 승인형 paper 주문

목표:

```text
백테스트 통과 후에도 바로 실주문이 아니라 Leader 승인형 paper-only 주문부터 검증한다.
```

게이트:

- 충분한 `snapshot_1m` 거래일 확보
- 백테스트 trade count 충분
- 손익/드로우다운 기준 통과
- 계좌/리스크 체크 통과
- 사용자 승인
- paper-only 검증

---

### Phase 6 — Real 주문 검토

아직 진행하지 않는다.

필수 조건:

```text
데이터 충분
백테스트 통과
paper 검증 통과
리스크 한도 명확화
사용자 명시 승인
```

---

## 5. 절대 금지

```text
ka10005 date-only 응답을 1min으로 저장 금지
sample/mock/random market data로 백테스트 통과 처리 금지
백테스트 전 자동 주문 활성화 금지
n8n과 Hermes cron의 중복 스케줄 활성화 금지
전략 threshold/weight/order behavior 임의 수정 금지
secrets/API key/account number 출력 금지
```

---

## 6. 현재 다음 작업

1. `snapshot_1m` 장중 누적을 계속 관찰한다. 정상 조건: cron `last_status=ok`, 품질 오류 0, 최신 lag가 수집 주기 대비 과도하게 벌어지지 않음.
2. 다음 장중 신호 생성일에 OR10/OR30 candidate loop가 후보별 score breakdown을 출력하는지 재확인한다.
3. `backtest_opening_strategy_90d`는 rows/trades가 기준 미달이면 계속 blocked로 둔다.
4. `daily_pnl_feedback_report`에서 snapshot 누적 추세를 장후마다 확인한다.
5. Phase 5 Leader 승인형 paper 주문은 백테스트 준비도 기준 통과 전까지 시작하지 않는다.
