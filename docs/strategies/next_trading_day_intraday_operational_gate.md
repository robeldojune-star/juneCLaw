# 다음 실제 거래일 장중 운영 게이트

상태: 운영 체크리스트  
기준 workspace: `/home/june/trading`  
목표: `snapshot_1m` 누적 품질과 OR10/OR30 후보 루프를 확인하되, rows/trades 기준 통과 전까지 paper/real 주문을 계속 차단한다.

---

## 1. 원칙

```text
1. snapshot_1m 누적은 계속 유지한다.
2. 다음 실제 장중에 lag / rows / active_codes를 재확인한다.
3. OR10/OR30 candidate loop는 후보별 score breakdown을 출력해야 한다.
4. rows/trades 기준 통과 전까지 paper/real 주문은 모두 금지한다.
5. 휴장·주말·장외 latest_timestamp_stale은 고장으로 보지 않는다.
```

금지:

```text
- ka10005 date-only 응답을 1min으로 저장 금지
- sample/mock/random market data로 백테스트 통과 처리 금지
- 백테스트 준비도 통과 전 paper/real 주문 활성화 금지
- 전략 threshold/weight/order behavior 임의 수정 금지
```

---

## 2. 장중 1차 확인 — snapshot_1m 품질

실행:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/inspect_snapshot_1m_status.py --days 2 --min-rows 20
```

확인 항목:

| 항목 | 정상 기준 |
|---|---|
| `source` | `kiwoom_ka10006_snapshot` |
| `time_frame` | `snapshot_1m` |
| `rows` | 장중 증가 중 |
| `active_codes` | 최소 5, 가능하면 10개 이상 |
| `latest_lag_minutes` | 장중 수집 주기 대비 과도하게 벌어지지 않음 |
| `duplicate_stock_timestamp_keys` | `0` |
| `quality_error_counts` | `{}` |

해석:

- 장중 `latest_lag_minutes`가 계속 커지면 collector/runner/API 경로 점검
- 장외/휴장/주말 stale은 장애로 보지 않음
- 품질 오류나 중복이 있으면 backtest/order 단계는 계속 blocked

---

## 3. 장중 2차 확인 — OR10/OR30 후보 루프

OR10:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_10m_aggressive_layer --pretty
```

OR30:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_30m_standard_layer --pretty
```

확인 항목:

| 항목 | 정상 기준 |
|---|---|
| `candidate_count` | 후보 압축 결과 존재 시 5~10 수준 |
| `evaluated_count` | 후보 수와 일치 또는 명확한 차단 사유 출력 |
| `score_details` | 후보별 출력 필수 |
| `blocking_conditions` | BUY 미발생/차단 사유 명확해야 함 |
| `order_execution_enabled` | 반드시 `false` |
| auto order guard | 반드시 blocked |

BUY 후보가 없어도 다음이 명확하면 정상:

```text
no_opening_buy_candidates
pattern_model_not_ready_for_auto_order
snapshot_1m_accumulation_and_backtest_required
```

---

## 4. 백테스트 준비도 게이트

실행:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/check_backtest_readiness.py
```

또는 stage 직접 실행:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage backtest_opening_strategy_90d --pretty
```

통과 기준:

| 항목 | 기준 |
|---|---:|
| `rows_used` | `>= min_rows_required` |
| `total_variant_trades` | `>= min_trades_required` |
| `snapshot_quality_ok` | `true` |
| `backtest_rows_ok` | `true` |
| `backtest_trades_ok` | `true` |

미통과 시 정상 차단:

```text
insufficient_intraday_rows_for_backtest
insufficient_backtest_trade_count
backtest_rows_below_min_required
backtest_trades_below_min_required
```

---

## 5. 주문 게이트

아래 조건을 모두 만족하기 전까지 주문은 금지한다.

```text
snapshot 품질 정상
rows_used 기준 통과
total_variant_trades 기준 통과
OR10/OR30 후보 루프 score breakdown 검증
Leader 승인형 paper 주문 설계/리스크 체크 통과
사용자 명시 승인
```

현재 기본값:

```json
{
  "paper_order_allowed": false,
  "real_order_allowed": false,
  "order_execution_enabled": false
}
```

---

## 6. signal=0 재확인

다음 거래일 morning pipeline에서 `signal=0`이 나오면 아래 네 가지로 원인을 분리한다.

| 원인 후보 | 확인 내용 |
|---|---|
| 데이터 부재 | `daily_prices`, `technical_indicators` 최신 거래일 존재 여부 |
| 날짜 필터 | UTC/KST 경계, 최근 24시간 window, latest batch 조회 여부 |
| 임계값 | BUY threshold 과도 여부. 단, 즉시 변경 금지 |
| 시장 조건 | 실제로 조건 만족 종목이 없었는지 |

주의:

```text
signal=0이라고 해서 threshold/weight/order behavior를 즉시 변경하지 않는다.
관찰 → strategy_change_candidate → 백테스트/paper 검증 → 사용자 승인 순서로만 반영한다.
```

---

## 7. 장후 확인

실행:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage daily_pnl_feedback_report --pretty
```

확인 항목:

- `snapshot_1m_accumulation.rows`
- `active_codes`
- `latest_timestamp`
- `quality_error_counts`
- `today_signal_count`
- `intraday_timing_alert_summary`
- `strategy_change_candidates`

장후에는 lag 증가 자체보다 `rows`, `active_codes`, `quality_error_counts`, `duplicate`를 우선 본다.
