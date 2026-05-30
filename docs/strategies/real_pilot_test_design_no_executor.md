# Real Pilot 실전 테스트 설계 — 주문 Executor 미구현 기준

상태: 설계 문서 / 주문 실행 코드 없음  
작성 기준: 2026-05-29  
기준 workspace: `/home/june/trading`

---

## 1. 목적

이 문서는 실전 주문 executor를 만들기 전, 소액 실전 테스트가 무엇을 검증해야 하는지 정의한다.

실전 테스트의 1차 목적은 수익 극대화가 아니다.

```text
1. 백테스트/모의 전략이 실전 호가에서 체결되는가?
2. 진입 직후 가격이 밀리는가?
3. 지정가 미체결/부분체결이 얼마나 발생하는가?
4. 수수료·세금·슬리피지 후에도 기대값이 남는가?
5. API 지연/주문 지연/데이터 지연이 전략을 망가뜨리는가?
```

---

## 2. 현재 금지 사항

```text
real order executor 구현 금지
실전 주문 API 호출 금지
시장가 주문 금지
자동 cron 실전 주문 금지
백테스트 성과 음수 상태에서 paper/real 전환 금지
```

현재 `core/trading_mode.py` 기준 real order는 아래 3개가 모두 켜지기 전까지 불가하다.

```text
REAL_ORDER_ENABLED=true
USER_CONFIRMED_REAL_ORDER=true
READINESS_REAL_ORDER_GATE=true
```

그리고 Kiwoom env가 반드시 `prod`여야 한다.

---

## 3. 실전 계좌 예산 가정

사용자 입력:

```text
실전 계좌는 1,000,000원 미만
```

권장 pilot 제한:

| 항목 | 제한 |
|---|---:|
| 총 pilot 예산 | 100,000원 이하 |
| 1회 주문 금액 | 20,000~30,000원 |
| 1일 주문 수 | 1~3건 |
| 주문 방식 | 지정가 우선 |
| 시장가 | 금지 |
| 종목 조건 | 거래대금 충분, 호가 얇은 종목 제외 |
| 손실 중단 | 일 손실 1~2만원 또는 -2% 도달 시 중단 |

실전 pilot은 계좌 전체를 쓰지 않는다.

---

## 4. Real Pilot 전제 조건

아래가 모두 충족되어야 한다.

### 4.1 데이터/백테스트

```text
ka10080 1분봉 수집 완료
09:00~09:30 eligible-day 필터 통과
partial day 제외
rows/trades 기준 통과
avg_return_pct > 0
수수료/슬리피지 반영 후에도 avg_return_pct > 0
```

### 4.2 Paper 검증

```text
paper ledger에 assumed_fill_price 저장
fee/slippage/impact 반영
paper PnL 5~10 거래 이상 확인
미체결 가정 또는 지정가 실패 가정 포함
```

### 4.3 Shadow Mode

실전 주문 전 최소 며칠 동안 주문을 보내지 않고 관찰만 한다.

```text
신호 발생 시점
추천 진입가
당시 bid/ask 또는 현재가
1분/3분/5분 후 가격
체결 가능했을 가격
미체결 가능성
```

---

## 5. 실전에서 반드시 기록할 항목

실전 주문 executor를 나중에 만들 경우, 주문 결과는 최소 아래를 기록해야 한다.

| 항목 | 설명 |
|---|---|
| signal_id | 어떤 신호에서 나온 주문인지 |
| order_request_time | 주문 요청 시각 |
| kiwoom_ack_time | Kiwoom 응답 시각 |
| requested_price | 전략 기준 주문가 |
| order_type | limit/market. 초기에는 limit만 허용 |
| requested_qty | 주문 수량 |
| filled_qty | 체결 수량 |
| avg_fill_price | 평균 체결가 |
| unfilled_qty | 미체결 수량 |
| fill_latency_ms | 요청→체결 지연 |
| slippage_bps | 기준가 대비 체결 차이 |
| post_entry_1m/3m/5m_return | 진입 직후 가격 밀림 확인 |
| cancel_reason | 미체결 취소/조건 미달 사유 |

---

## 6. 실전 체결 품질 지표

전략 성과와 별도로 아래 지표를 본다.

```text
fill_rate = filled_orders / submitted_orders
partial_fill_rate = partial_fills / submitted_orders
avg_slippage_bps
max_adverse_excursion_1m
max_adverse_excursion_5m
order_ack_latency_ms
signal_to_order_latency_ms
entry_to_exit_realized_return
paper_vs_real_return_gap
```

특히 사용자 경험상 중요한 항목:

```text
내가 진입하면 가격이 떨어지는가?
```

이를 위해 `post_entry_1m/3m/5m_return`을 반드시 기록한다.

---

## 7. 실전 pilot 단계

### Phase 0 — No Order Shadow

```text
주문 없음
신호만 기록
체결됐을 가격 추정
```

통과 조건:

```text
신호→추천가→이후 가격 기록이 정상
paper expected return이 음수 아님
```

### Phase 1 — Manual One-Click Test

```text
자동 주문 없음
사용자가 직접 증권앱/HTS로 극소액 지정가 주문
시스템은 기록만 함
```

통과 조건:

```text
체결 기록과 시스템 신호가 매칭됨
슬리피지/가격충격 허용 범위
```

### Phase 2 — Approved API Order 후보

```text
아직 executor 구현 전 단계
설계만 하고 코드 구현은 사용자 승인 후
```

필수 게이트:

```text
REAL_ORDER_ENABLED=true
USER_CONFIRMED_REAL_ORDER=true
READINESS_REAL_ORDER_GATE=true
```

---

## 8. Executor를 만들 때 금지할 기본값

```text
시장가 주문 기본값 금지
전액 주문 금지
분할 매수 자동 확대 금지
손실 중 물타기 금지
cron 자동 real order 금지
mock/prod 자동 전환 금지
```

---

## 9. 다음 작업

현재는 executor를 만들지 않는다.

다음 순서:

```text
1. ka10080 eligible-day 백테스트 성과 개선
2. paper ledger에 수수료/슬리피지/가격충격 반영
3. shadow mode 기록 테이블/리포트 설계
4. 사용자가 승인하면 real pilot executor 상세 설계
5. 그 이후에만 코드 구현
```
