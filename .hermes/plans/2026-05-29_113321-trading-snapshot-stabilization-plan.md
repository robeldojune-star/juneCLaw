# Trading Snapshot Stabilization Plan

> **For Hermes:** 진행은 한 번에 크게 바꾸지 말고, 데이터 무결성 → 모니터링 → 백테스트 → 승인형 주문 순서로 안전 게이트를 통과시키며 진행한다.

**Goal:** `ka10005` 분봉 오염을 완전히 배제하고, `ka10006` 장중 snapshot_1m 누적 데이터를 기반으로 오프닝 전략/백테스트/승인형 주문까지 단계적으로 복구한다.

**Architecture:** n8n은 현재 비활성화된 백업으로 유지한다. 실제 장중 수집은 Hermes cron(no_agent) → Docker `trading-runner` → Python stage → Supabase `intraday_prices` 경로로 단순화한다. 주문/실행 계층은 `snapshot_1m` 누적과 백테스트 통과 전까지 의도적으로 blocked 상태를 유지한다.

**Tech Stack:** Python, Kiwoom REST, Supabase REST/Postgres, Docker compose trading-runner, Hermes cron.

---

## 현재 확인된 상태

- Active workspace: `/home/june/trading`
- n8n `daily_trading_workflow_v1`: 비활성화 상태로 운영 의존성 제거
- Hermes cron: `trading-snapshot-1m-collector-no-n8n`, 5분마다 실행
- 수집 원천: Kiwoom `ka10006`
- 저장 위치: Supabase `intraday_prices`
- 저장 식별자: `source=kiwoom_ka10006_snapshot`, `time_frame=snapshot_1m`
- 자동 주문: `snapshot_1m_accumulation_and_backtest_required`로 차단 유지

## 전체 단계

### Phase 1 — 수집 안정화/무결성 확인

**목표:** 장중 5분마다 누락 없이 실제 snapshot_1m이 쌓이는지 매일 확인한다.

작업:
1. `scripts/inspect_snapshot_1m_status.py` 작성
   - 최근 `snapshot_1m` 행 조회
   - 종목별 row count, 날짜 범위, 최신 timestamp 확인
   - OHLC 구조 오류, 중복 timestamp, source/time_frame 혼입 여부 확인
   - 충분하지 않으면 명확한 `blocking_conditions` 출력
2. 실행 검증
   - Docker `trading-runner` 안에서 실행
   - JSON 결과가 `ok=true` 또는 정상적인 blocked 사유를 반환해야 함
3. 필요 시 Hermes cron 알림 스크립트에 품질검사 hook 추가
   - 성공은 silent
   - 수집 중단/오염/중복 급증만 alert

검증 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/inspect_snapshot_1m_status.py --days 2 --min-rows 20
```

### Phase 2 — 오프닝 전략 후보 루프 안전 검증

**목표:** OR10/OR30 후보 평가가 `snapshot_1m`만 사용하고, 데이터 부족 시 blocked로 끝나는지 확인한다.

작업:
1. `opening_10m_aggressive_layer` 실행
2. `opening_30m_standard_layer` 실행
3. 신호/후보별 score breakdown과 blocking_conditions 확인
4. 자동 주문 guard가 계속 존재하는지 확인

검증 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_10m_aggressive_layer --pretty
```

### Phase 3 — 백테스트 준비도 게이트

**목표:** 데이터가 충분히 쌓이기 전에는 백테스트가 성공처럼 보이지 않게 막는다.

작업:
1. `backtest_opening_strategy_90d` 실행
2. `rows_used`, `total_variant_trades`, `blocking_conditions` 확인
3. rows/trades 부족이면 blocked 정상으로 기록
4. 충분한 거래일 확보 전까지 전략 임계값/주문 로직은 수정하지 않음

검증 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage backtest_opening_strategy_90d --pretty
```

### Phase 4 — 일일 운영 리포트

**목표:** 수집/신호/미체결/차단 사유를 매일 장후 리포트화한다.

작업:
1. `daily_pnl_feedback_report` 점검
2. snapshot 누적 요약을 리포트에 포함할지 검토
3. 텔레그램/로컬 리포트는 중복 발송 없이 한 경로만 유지

### Phase 5 — 승인형 paper 주문만 복구

**목표:** 백테스트 통과 후에도 바로 실주문이 아니라 Leader 승인형 paper-only 주문부터 검증한다.

게이트:
- 최소 충분한 `snapshot_1m` 거래일 확보
- 백테스트 trade count 충분
- 손익/드로우다운 기준 통과
- 계좌/리스크 체크 통과
- 사용자 승인 후 paper-only → 이후 별도 승인으로 real 검토

## 절대 금지

- `ka10005` date-only 응답을 `1min`으로 저장 금지
- sample/mock market data로 백테스트 통과 처리 금지
- 백테스트 전 자동 주문 활성화 금지
- n8n과 Hermes cron의 중복 스케줄 활성화 금지
- 전략 threshold/weight/order behavior 임의 수정 금지

## 이번 턴에서 진행할 1단계

1. `scripts/inspect_snapshot_1m_status.py` 생성
2. Python compile 검증
3. Docker `trading-runner`에서 실행
4. 결과를 기준으로 다음 작업을 결정
