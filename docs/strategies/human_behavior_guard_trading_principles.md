# 인간 행동 편향 차단형 트레이딩 시스템 원칙

상태: 핵심 운영 철학 / 전략 설계 기준  
작성 기준: 2026-05-29  
기준 workspace: `/home/june/trading`

---

## 1. 프로젝트의 진짜 목적

이 프로젝트의 목적은 단순히 백테스트 수익률을 높이는 것이 아니다.

핵심 목적은 다음이다.

```text
1. 신호가 발생했을 때 인간이 공포 때문에 진입하지 못하는 문제를 줄인다.
2. 진입 후 매도 신호가 발생했을 때 인간이 탐욕 때문에 팔지 못하는 문제를 줄인다.
3. 동시에 여러 종목의 1분봉/신호/리스크를 사람이 직접 관찰할 수 없는 한계를 시스템으로 보완한다.
4. 장초반 급변 상황에서 감정이 아니라 규칙과 기록에 따라 판단한다.
```

즉, 이 시스템은 다음을 보조한다.

```text
기술적 분석 → 신호 생성 → 다종목 감시 → 진입/청산 후보화 → 기록/피드백
```

최종 목표는 "무조건 자동매매"가 아니라, 먼저 **감정 개입을 줄이는 규칙 기반 관찰·후보화·paper 검증 시스템**이다.

---

## 2. 인간이 실패하는 지점

### 2.1 진입 실패 — 공포

사람은 신호가 보여도 다음 이유로 들어가지 못한다.

```text
- 방금 급등해서 무섭다.
- 눌림이 올 것 같아 기다린다.
- 여러 종목이 동시에 움직여 판단이 늦는다.
- 차트를 보다가 이미 지나간다.
- 손실 경험 때문에 확신이 약해진다.
```

시스템이 해야 할 일:

```text
- 신호 발생 시각을 정확히 기록한다.
- 진입 조건이 충족됐는지 기계적으로 판단한다.
- 진입하지 못한 경우에도 missed_entry로 기록한다.
- 1분/3분/5분 후 결과를 기록해 공포 때문에 놓친 기회를 수치화한다.
```

### 2.2 청산 실패 — 탐욕

사람은 매도 신호가 보여도 다음 이유로 팔지 못한다.

```text
- 더 오를 것 같다.
- 익절 기준을 즉석에서 바꾼다.
- 손실을 인정하기 싫어 손절하지 않는다.
- 여러 종목을 동시에 보다가 매도 타이밍을 놓친다.
- 이미 수익이 났기 때문에 리스크를 과소평가한다.
```

시스템이 해야 할 일:

```text
- 손절/익절/시간청산 신호를 명확히 구분한다.
- 매도 신호 발생 시각과 가격을 기록한다.
- 매도하지 않았을 경우의 이후 수익/손실도 기록한다.
- 탐욕 때문에 보유한 결과가 좋은지 나쁜지 피드백한다.
```

---

## 3. 다종목 관찰 한계

사람은 동시에 여러 종목의 1분봉을 안정적으로 볼 수 없다.

특히 장초반에는 다음이 동시에 발생한다.

```text
- 여러 종목의 OR10/OR30 돌파
- 거래량 급증
- 호가 급변
- 뉴스/테마 반응
- 눌림/재돌파
- 손절/익절 조건 접근
```

따라서 시스템은 다음 역할을 해야 한다.

```text
1. 여러 종목을 동시에 스캔한다.
2. 신호가 발생한 종목만 압축해서 보여준다.
3. 왜 신호가 발생했는지 score_details를 남긴다.
4. 왜 진입/청산하지 않았는지 blocking_conditions를 남긴다.
5. 사람이 나중에 차트로 검증할 수 있게 PNG/HTML 리포트를 생성한다.
```

---

## 4. 자동 실행보다 먼저 필요한 것

바로 실전 자동주문으로 가면 안 된다.

먼저 해야 할 것은 다음이다.

```text
1. 신호 관찰 정확도 검증
2. missed_entry 기록
3. missed_exit 기록
4. paper ledger 기록
5. 실제 체결 가능성 추정
6. 사람의 판단과 시스템 판단의 차이 기록
```

즉 현재 단계의 우선순위는:

```text
자동매매 < 자동관찰 < 자동기록 < 자동피드백
```

이다.

---

## 5. 시스템에 추가해야 할 핵심 이벤트

### 5.1 Signal Event

신호가 발생하면 주문 여부와 무관하게 기록한다.

```json
{
  "event_type": "ENTRY_SIGNAL",
  "stock_code": "000660",
  "strategy": "opening_swing_3d_v1",
  "signal_time": "2026-05-22T09:01:00+09:00",
  "signal_price": 1950000,
  "score": 82,
  "score_details": {},
  "blocking_conditions": [],
  "human_action": "not_entered",
  "system_recommendation": "BUY_CANDIDATE"
}
```

### 5.2 Missed Entry Event

신호 후 사람이 진입하지 않았을 때 기록한다.

```json
{
  "event_type": "MISSED_ENTRY",
  "stock_code": "000660",
  "signal_time": "09:01",
  "signal_price": 1950000,
  "after_1m_return_pct": 0.3,
  "after_3m_return_pct": 0.8,
  "after_5m_return_pct": 1.1,
  "after_1d_return_pct": 5.2,
  "reason": "human_fear_or_manual_delay"
}
```

### 5.3 Exit Signal Event

매도/청산 신호를 명확히 기록한다.

```json
{
  "event_type": "EXIT_SIGNAL",
  "exit_reason": "take_profit_sell_signal",
  "stock_code": "000660",
  "entry_price": 1950000,
  "exit_signal_price": 2052000,
  "return_pct": 5.23,
  "human_action": "held",
  "system_recommendation": "SELL_OR_PARTIAL_SELL"
}
```

### 5.4 Missed Exit Event

매도 신호 후 팔지 않았을 때 기록한다.

```json
{
  "event_type": "MISSED_EXIT",
  "stock_code": "000660",
  "exit_signal_price": 2052000,
  "after_1m_return_pct": -0.2,
  "after_5m_return_pct": -0.8,
  "after_1d_return_pct": -3.0,
  "reason": "human_greed_or_hoping_more_upside"
}
```

---

## 6. 전략 설계에 반영할 원칙

### 6.1 진입

진입은 다음 세 단계로 분리한다.

```text
WATCH: 후보 관찰
ENTRY_SIGNAL: 기계적 진입 신호 발생
BUY_CANDIDATE: paper 또는 승인형 주문 후보
```

사람이 진입하지 않아도 신호는 기록한다.

### 6.2 청산

청산은 반드시 신호화한다.

```text
STOP_LOSS_SIGNAL
TAKE_PROFIT_SIGNAL
TIME_EXIT_SIGNAL
TRAILING_STOP_SIGNAL
TREND_BREAK_SIGNAL
```

"그냥 마지막 가격으로 청산"은 백테스트 편의용이며, 운영 신호로 쓰면 안 된다.

### 6.3 다종목 동시 관찰

시스템은 한 번에 최소 다음을 감시해야 한다.

```text
- today_watchlist 10~30개
- OR10/OR30 돌파 여부
- 거래량 급증
- 신호 후 1/3/5분 결과
- 보유 후보의 손절/익절/시간청산 조건
```

---

## 7. 현재 시스템에 대한 적용 판단

현재까지 완료:

```text
ka10080 과거 1분봉 수집
데이터 차트 검증
진입/청산 차트 생성
OR10/OR30 range 이후 진입 로직 수정
손절/익절/시간청산 매도 신호 추가
```

아직 필요한 것:

```text
missed_entry 기록
missed_exit 기록
entry 후 1/3/5분 결과 자동 계산
1~3거래일 스윙 보유 결과 비교
다종목 실시간 신호 대시보드 또는 요약 리포트
```

---

## 8. 다음 구현 우선순위

1. `signal_events` 또는 기존 `trading_signals.score_details`에 ENTRY/EXIT/MISSED 이벤트를 기록한다.
2. OR10/OR30/day-swing 전략에서 entry/exit event를 모두 생성한다.
3. 신호 후 1분/3분/5분/1일/3일 결과를 자동 계산한다.
4. 사람이 진입/청산하지 않은 경우도 missed event로 남긴다.
5. paper ledger로 이동하기 전, 시스템 신호가 인간보다 나은지 리포트로 확인한다.

---

## 9. 최종 원칙

```text
사람은 공포 때문에 못 사고, 탐욕 때문에 못 판다.
시스템은 신호를 놓치지 않고, 감정 없이 기록하고, 나중에 검증 가능하게 해야 한다.
```

이 원칙을 지키지 못하면 이 프로젝트의 목적과 맞지 않는다.
