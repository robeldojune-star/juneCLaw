# ka10080 과거 1분봉 백테스트 파이프라인 적용 보고서

상태: 구현/검증 완료, 전략 성과 게이트 blocked  
작성 기준: 2026-05-29 19:33 KST  
기준 workspace: `/home/june/trading`  

---

## 1. 결론

키움 REST API의 `ka10080 주식분봉차트조회요청`을 과거 1분봉 백테스트 데이터 소스로 연결했다.

```text
백테스트 데이터 소스:
  source = kiwoom_ka10080_minute
  time_frame = 1min

실시간 장중 감시 데이터 소스:
  source = kiwoom_ka10006_snapshot
  time_frame = snapshot_1m
```

기존 `ka10005`는 계속 분봉 소스로 사용하지 않는다.

현재 결과는 다음과 같다.

```text
수집/저장: 성공
백테스트 rows/trades 게이트: 통과
백테스트 성과 게이트: blocked
paper/real 주문: 계속 금지
```

---

## 2. 구현 변경 사항

| 파일 | 변경 내용 |
|---|---|
| `core/market_data_service.py` | `get_minute_chart_raw()` 추가. `ka10080` `/api/dostk/chart` 호출 |
| `scripts/collect_intraday_90d.py` | `ka10005` 기반 수집기에서 `ka10080` 1분봉 수집기로 교체 |
| `scripts/backtest_opening_strategy.py` | `--source kiwoom_ka10080_minute`, pagination 조회 추가 |
| `scripts/run_daily_workflow_stage.py` | `collect_intraday_90d` stage를 실제 `ka10080` 수집 실행으로 변경, `backtest_opening_strategy_90d`는 `1min` 소스로 변경 |
| `scripts/check_backtest_readiness.py` | rows/trades 외 `backtest_performance_ok` 성과 게이트 추가 |
| `docs/strategies/current_trading_execution_plan.md` | 백테스트=`ka10080`, 실시간 감시=`ka10006` 분리 기준 반영 |
| `docs/strategies/time_ordered_trading_workflow_report.md` | 시간순 워크플로우의 데이터 소스 기준 갱신 |

---

## 3. 실제 수집 검증

실행 stage:

```bash
python3 scripts/run_daily_workflow_stage.py --stage collect_intraday_90d --pretty
```

결과 요약:

```text
status = completed
source = kiwoom_ka10080_minute
time_frame = 1min
stock_codes = 005930, 000660, 035420, 005380, 068270
prepared_rows = 15000
upserted_rows = 15000
blocking_conditions = []
alerts = []
```

DB 직접 확인 결과:

| 종목 | rows | first_timestamp UTC | last_timestamp UTC |
|---|---:|---|---|
| 000660 | 3000 | 2026-05-15T01:22:00+00:00 | 2026-05-29T06:30:00+00:00 |
| 005380 | 3000 | 2026-05-15T01:22:00+00:00 | 2026-05-29T06:30:00+00:00 |
| 005930 | 3000 | 2026-05-15T01:22:00+00:00 | 2026-05-29T06:30:00+00:00 |
| 035420 | 3000 | 2026-05-15T01:22:00+00:00 | 2026-05-29T06:30:00+00:00 |
| 068270 | 3000 | 2026-05-15T01:22:00+00:00 | 2026-05-29T06:30:00+00:00 |

총 저장 행:

```text
15,000 rows
```

---

## 4. 백테스트 검증 결과

실행 stage:

```bash
python3 scripts/run_daily_workflow_stage.py --stage backtest_opening_strategy_90d --pretty
```

결과 요약:

```text
status = completed
source = kiwoom_ka10080_minute
time_frame = 1min
rows_used = 15000
min_rows_required = 300
total_variant_trades = 80
min_trades_required = 5
blocking_conditions = []
```

variant 결과:

| Variant | trades | win_rate | avg_return_pct | max_drawdown_pct |
|---|---:|---:|---:|---:|
| OR10 | 40 | 25.5873% | -0.7768% | -7.1465% |
| OR30 | 40 | 25.5873% | -0.7768% | -7.1465% |

해석:

```text
데이터 수와 거래 수 기준은 통과했다.
하지만 평균 수익률이 음수이므로 paper 전환 근거로 사용할 수 없다.
```

---

## 5. Readiness 결과

실행:

```bash
python3 scripts/check_backtest_readiness.py
```

결과:

```text
status = blocked
blocking_conditions = [backtest_avg_return_not_positive]
```

readiness gate:

| Gate | 상태 |
|---|---:|
| snapshot_quality_ok | true |
| snapshot_lag_ok | true |
| snapshot_volume_ok | true |
| backtest_rows_ok | true |
| backtest_trades_ok | true |
| backtest_performance_ok | false |

---

## 6. 운영 판단

현재는 백테스트 파이프라인이 복구되었지만 전략 자체의 단순 OR 진입/종가 청산 결과가 좋지 않다.

따라서 다음 단계는 주문 전환이 아니라 전략 진단이다.

```text
1. paper 주문 금지
2. real 주문 금지
3. OR10/OR30 score_details replay 구현
4. 진입/청산 규칙, 손절/익절, 수수료/슬리피지 반영
5. 후보 압축/뉴스/거래대금 필터 적용 전후 성과 비교
```

---

## 7. 다음 작업

1. `ka10080` 수집 범위를 90일 전체로 확장할지 결정한다.
2. 현재 백테스트가 단순형이므로 실제 운영 `score_details`와 동일한 replay 백테스트를 구현한다.
3. OR10/OR30이 같은 결과를 내는 현재 단순 로직을 개선한다. 현재 로직은 opening high 기준 돌파를 사용해 window 차이가 충분히 반영되지 않는다.
4. 성과 게이트를 명확히 한다.

권장 최소 성과 게이트 예:

```text
avg_return_pct > 0
win_rate >= 40%
max_drawdown_pct >= -3% 또는 손절/익절 반영 후 재평가
trades >= 30
```

단, 위 수치는 운영 제안이며 실제 threshold/weight/order behavior 변경은 사용자 검토 후 적용한다.
