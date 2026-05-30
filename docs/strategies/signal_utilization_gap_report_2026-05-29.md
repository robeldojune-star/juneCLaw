# 신호 활용 누락 진단 보고서

상태: 진단 완료 / 개선 필요  
작성 기준: 2026-05-29  
기준 workspace: `/home/june/trading`

---

## 1. 결론

현재 시스템은 **신호를 생산하고는 있지만, 그 신호를 충분히 활용하지 못하고 있다.**

신호 흐름은 다음처럼 중간에서 끊긴다.

```text
일봉 technical_score_v1 신호 생성: 정상
→ candidate_compression_layer 후보 압축: 정상
→ opening_10m/30m 후보 루프: 대부분 HOLD/blocked
→ paper 주문: 후보 0개로 blocked
→ positions/orders: 없음
→ missed_entry/missed_exit 기록: 없음
```

즉, 문제는 신호 생성 자체보다 **신호 활용층**이다.

---

## 2. 현재 신호 생산 상태

DB `trading_signals` 기준:

| signal_type | count | avg_score |
|---|---:|---:|
| BUY | 23 | 73.39 |
| HOLD | 21 | 43.14 |
| SELL | 6 | 27.17 |

전략:

```text
strategy = technical_score_v1
signal_date = 2026-05-28 15:30 KST
```

최신 BUY 상위 예:

| 종목 | 신호 | 점수 | 가격 | 이유 요약 |
|---|---|---:|---:|---|
| 현대차 `005380` | BUY | 87 | 677000 | 상승 배열, RSI 안정, MACD 상승 |
| SK스퀘어 `402340` | BUY | 85 | 1237000 | 상승 배열, RSI 안정, MACD 상승 |
| 삼성전자 `005930` | BUY | 82 | 299500 | 상승 배열, RSI 안정, MACD 상승 |
| SK하이닉스 `000660` | BUY | 75 | 2289000 | 상승 배열, RSI 과열, MACD 개선 |

신호 생산은 정상이다.

---

## 3. 후보 압축은 정상 작동

`candidate_compression_layer.py` 결과:

```text
today_signal_count = 50
buy_signal_count = 23
candidate_count = 10
signal_window = latest_available_batch:2026-05-28
```

즉 일봉 BUY 신호는 TOP 5~10 후보로 잘 압축된다.

---

## 4. 끊기는 지점: opening candidate loop

`run_opening_strategy_candidate_loop.py --window 10 --limit 10` 결과:

```text
candidate_count = 10
evaluated_count = 10
buy_candidate_count = 0
order_execution_enabled = false
alerts = [no_opening_buy_candidates]
```

문제:

```text
일봉 BUY 후보가 장중 opening loop에서 대부분 HOLD/blocked로 바뀐다.
```

대표 차단 사유:

```text
pattern_model_not_ready
fujimoto_volume_insufficient
financial_filter_failed
fujimoto_financial_data_missing
fujimoto_stage_entry_not_ready
```

즉 일봉 신호는 살아 있지만, opening layer가 이를 너무 강하게 차단한다.

---

## 5. paper 주문으로 연결되지 않음

`simulate_approved_orders` 결과:

```text
candidate_buy_count = 0
approved_order_count = 0
inserted_order_count = 0
blocking_conditions = [no_buy_candidates_for_simulation]
```

현재 `orders` 테이블:

```text
orders = []
```

현재 `positions`:

```text
open_positions = 0
```

즉 신호가 실제 paper ledger로도 이어지지 않는다.

---

## 6. SELL 신호는 있지만 청산에 활용되지 않음

`technical_score_v1`에는 SELL 6개가 있다.

하지만 현재 포지션이 없기 때문에 SELL 신호는 청산에 연결되지 않는다.

```text
open_positions = 0
```

또한 OR 백테스트에서는 손절/익절/시간청산 신호를 최근에 추가했지만, 이 결과도 아직 `signal_events` 또는 paper ledger에 남지 않는다.

---

## 7. 핵심 원인

### 원인 1 — 신호 종류가 분리되지 않음

현재 BUY 신호는 여러 의미를 섞고 있다.

```text
일봉 BUY = 후보 선정 신호
분봉 BUY = 실제 진입 신호
paper BUY = 주문 후보
real BUY = 실제 주문
```

이 4개가 분리되어 기록되지 않는다.

### 원인 2 — missed_entry/missed_exit 기록 없음

사람이 진입하지 않았거나 시스템이 차단했을 때 이후 결과가 기록되지 않는다.

그래서 다음 질문에 답하기 어렵다.

```text
일봉 BUY였는데 opening layer가 막은 게 맞았나?
사람이 못 들어간 게 손해였나?
안 판 게 이익이었나 손해였나?
```

### 원인 3 — opening loop가 일봉 신호를 활용보다 재심사/차단 위주로 사용

현재 opening loop는 일봉 후보를 받아도 다음 조건 때문에 대부분 blocked된다.

```text
pattern_model_not_ready
fujimoto_volume_insufficient
financial_filter_failed
```

이 조건들이 주문 차단에는 필요하지만, **신호 이벤트 기록까지 막으면 안 된다.**

### 원인 4 — paper 단계가 BUY 후보만 받음

`simulate_approved_orders.py`는 `buy_candidates`가 없으면 아무것도 기록하지 않는다.

하지만 운영상 필요한 것은 다음이다.

```text
BUY 후보가 없어도 BLOCKED_SIGNAL/MISSED_ENTRY를 기록해야 함
```

---

## 8. 개선 방향

### 8.1 신호 이벤트 테이블 도입

새 테이블 또는 JSON 기록:

```text
signal_events
```

기록할 event_type:

```text
DAILY_ENTRY_CANDIDATE
INTRADAY_ENTRY_SIGNAL
BLOCKED_ENTRY_SIGNAL
MISSED_ENTRY
EXIT_SIGNAL
MISSED_EXIT
PAPER_ORDER_CANDIDATE
```

### 8.2 일봉 BUY를 무시하지 말고 outcome 추적

일봉 BUY 후보가 opening layer에서 막혀도 기록한다.

```text
event_type = BLOCKED_ENTRY_SIGNAL
blocking_conditions = [...]
after_1d_return_pct
after_3d_return_pct
```

### 8.3 진입하지 못한 경우도 기록

실제 주문을 안 해도 다음을 남긴다.

```text
signal_time
signal_price
after_1m/3m/5m/1d/3d return
human_action = NOT_ENTERED
system_action = BLOCKED or WATCH_ONLY
```

### 8.4 SELL 신호는 포지션이 없어도 후보로 기록

SELL 신호가 기존 보유 포지션에만 의미 있는 것은 아니다.

포지션이 없어도 다음 정보가 된다.

```text
과열/하락/회피 신호
신규 진입 금지 후보
watchlist 제외 후보
```

---

## 9. 다음 구현 제안

1. `signal_events` 테이블 또는 JSON event log 생성
2. `candidate_compression_layer.py`가 DAILY_ENTRY_CANDIDATE 이벤트를 남김
3. `run_opening_strategy_candidate_loop.py`가 BUY/HOLD/BLOCKED 결과를 모두 이벤트로 남김
4. `simulate_approved_orders.py`가 후보 0개여도 BLOCKED/MISSED_ENTRY를 기록
5. `analyze_daily_to_minute_signal_scenario.py`를 다종목 batch로 확장해 after_1d/3d outcome 계산
6. 신호 활용 리포트 생성:

```text
생성 신호 수
후보 압축 수
진입 후보 수
차단 수
놓친 신호 수
놓친 신호의 이후 수익률
SELL 신호 이후 하락 여부
```

---

## 10. 최종 판단

현재 시스템은 신호를 생산하지만, 아직 다음 질문에 답하지 못한다.

```text
이 신호를 따랐으면 어떻게 됐나?
이 신호를 무시한 게 맞았나?
매도 신호를 놓쳤을 때 손해가 났나?
```

따라서 다음 단계는 전략 수식 추가보다 **신호 활용 이벤트 기록과 outcome 분석**이다.
