# Research AI 점수 Breakdown 표준 v1

연결 전략: `opening_multi_factor_v1`  
적용 스크립트: `scripts/run_opening_strategy_research.py`  
상태: 최소 구현 반영 완료

---

## 1. 목적

Research AI는 단순 BUY/HOLD만 내지 않고, 사용자가 검토할 수 있는 점수 분해와 차단 조건을 함께 출력해야 한다.

---

## 2. 출력 JSON 필드

```json
{
  "ok": true,
  "workflow": "run_opening_strategy_research",
  "strategy_id": "opening_multi_factor_v1",
  "stock_code": "005930",
  "signal_type": "HOLD",
  "score": 15.0,
  "score_details": {},
  "blocking_conditions": [],
  "reason": "...",
  "data_quality": {}
}
```

---

## 3. 점수 구조

| 영역 | 최대점 | 현재 구현 상태 |
|---|---:|---|
| volatility | 30 | 최소 구현 |
| flow | 30 | 최소 구현 |
| pattern | 25 | placeholder, 90일 분봉 백테스트 필요 |
| risk_adjustment | 15 | 최소 구현 |
| 합계 | 100 | 최소 구현 |

---

## 4. 차단 조건 원칙

Research AI는 부족한 데이터를 감추지 않고 `blocking_conditions`에 명시한다.

예:

```text
pattern_model_not_ready
missing_volatility_breakout_inputs
missing_opening_range_inputs
financial_filter_failed
rsi_overheated
```

---

## 5. n8n 분기 기준 후보

```text
IF ok == true AND score >= 70 AND critical blocking condition 없음
  → BUY 후보 알림 또는 order_candidate 생성 후보
ELSE IF score >= 55
  → WATCH 알림
ELSE
  → HOLD 요약
```

주의:

```text
- 현재 임계값은 후보값이며 백테스트 전 확정하지 않는다.
- pattern_model_not_ready가 있으면 자동 주문으로 연결하지 않는다.
- 초기에는 알림 전용으로 운용한다.
```
