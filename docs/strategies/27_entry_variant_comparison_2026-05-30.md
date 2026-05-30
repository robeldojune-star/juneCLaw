# 27. OR 진입 변형 비교 보고서 — 즉시돌파 vs 눌림재돌파 vs 필터형 진입

상태: **검증중 / 표본 부족**  
작성 기준: 2026-05-30 07:35 KST  
작업 공간: `/home/june/trading`  
상위 기준 문서: `docs/strategies/00_master_trading_plan.md`  
원본 산출물: `reports/entry_variant_comparison_latest.md`, `reports/entry_variant_comparison_latest.json`  
실행 스크립트: `scripts/backtest_entry_variant_comparison.py`  
주문 영향: **read-only 백테스트. orders/positions 미변경. paper/real 주문 미실행.**

---

## 1. 결론 요약

현재 작은 표본 기준으로는 **어떤 진입 변형도 paper/real 주문 허용 근거가 아니다.**

핵심 결론:

```text
1. OR 돌파 직후 즉시 진입은 현재 표본에서 모두 손절이다.
2. 09:10~10:00 진입 제한은 현재 표본에서 손실 개선을 만들지 못했다.
3. pullback/rebreak와 돌파봉 거래량 조건은 진입 수를 줄였지만 수익성 개선 근거는 부족하다.
4. early_drop_filter는 OR10 손실 진입 2건을 모두 차단했으나, 진입 0건이라 수익성 검증이 아니다.
5. 10:00 확인 진입은 전부 차단되어 매우 보수적인 필터로만 관찰한다.
6. 표본 부족과 ka10080 다음 거래일 분봉 누락 때문에 전략 채택 판단은 보류한다.
```

---

## 2. 배경

기존 OR10/OR30 진입은 다음 문제가 있었다.

```text
- OR 돌파 후 바로 진입하면 고점 추격이 될 수 있다.
- 실제 진입 신호가 비용 반영 후 손실로 끝났다.
- 차단된 신호의 proxy 수익률이 일부 샘플에서 더 좋았다.
- 따라서 단순 돌파가 아니라, 눌림/재돌파/거래량/급락/10:00 확인 조건을 비교할 필요가 생겼다.
```

비교 목적은 주문을 열기 위한 것이 아니라, **어떤 진입 조건이 손실 진입을 줄이는지** 확인하는 것이다.

---

## 3. 비교한 진입 변형

| 사용자 요청 | 구현 variant | 설명 |
|---|---|---|
| OR 돌파 직후 즉시 진입 | `immediate_breakout` | OR high 돌파 첫 봉 종가 진입 |
| pullback/rebreak 진입 | `pullback_rebreak` | 최초 돌파 후 OR high 이하 눌림, 이후 재돌파 진입 |
| 09:10~10:00 진입 제한 | `entry_window` | OR 돌파를 10:00까지만 허용 |
| 돌파봉 거래량 조건 | `volume_confirmed_breakout` | 돌파봉 거래량 >= OR 평균 거래량 × 1.5 |
| 진입 후 3~5분 내 급락 필터 | `early_drop_filtered_breakout` | 진입 후보 후 5분 내 -0.7% 급락이면 차단 |
| OR10/OR30 대신 10:00 확인 진입 | `ten_oclock_confirmation` | 10:00 종가가 OR high 위일 때만 진입 |

---

## 4. 사용 데이터와 전제

| 항목 | 값 |
|---|---:|
| 대상 signal_date | `2026-05-28` |
| BUY 신호 수 | 23 |
| 다음 거래일 ka10080 분봉 누락 | 20 |
| 실제 평가 가능 종목 | 3 |
| 평가 row 수 | 36 |
| 비용 반영 | 왕복 0.66% |
| 손절/익절/시간청산 | -1.0% / +1.5% / 15:20 |

중요 제약:

```text
현재 trading_signals의 signal_date가 1개뿐이다.
BUY 23건 중 20건은 다음 거래일 ka10080 1분봉이 없다.
따라서 통계적 유의성이 매우 낮다.
```

---

## 5. 결과 요약

| variant | entries | avg_net | positive_rate | 주요 차단 |
|---|---:|---:|---:|---|
| `immediate_breakout_OR10` | 2 | -1.66% | 0.0% | no breakout 1 |
| `entry_window_OR10` | 2 | -1.66% | 0.0% | window 내 no breakout 1 |
| `pullback_rebreak_OR10` | 1 | -1.66% | 0.0% | no initial/rebreak |
| `volume_confirmed_breakout_OR10` | 1 | -1.66% | 0.0% | volume below 1, no breakout 1 |
| `early_drop_filtered_breakout_OR10` | 0 | 없음 | 없음 | early drop 2, no breakout 1 |
| `ten_oclock_confirmation_OR10` | 0 | 없음 | 없음 | 10:00 close가 OR high 미돌파 3 |
| `immediate_breakout_OR30` | 1 | -1.66% | 0.0% | no breakout 2 |
| `entry_window_OR30` | 1 | -1.66% | 0.0% | window 내 no breakout 2 |
| `pullback_rebreak_OR30` | 1 | -1.66% | 0.0% | no initial breakout 2 |
| `volume_confirmed_breakout_OR30` | 1 | -1.66% | 0.0% | no breakout 2 |
| `early_drop_filtered_breakout_OR30` | 1 | -1.66% | 0.0% | no breakout 2 |
| `ten_oclock_confirmation_OR30` | 0 | 없음 | 없음 | 10:00 close가 OR high 미돌파 3 |

---

## 6. 운영 판단

### 6.1 즉시 돌파 진입

현재 표본에서는 실전 연결 금지다.

```text
진입 수는 가장 많지만, 발생한 진입이 모두 손절이다.
고점 추격 문제를 해결하지 못했다.
```

### 6.2 09:10~10:00 제한

단독 필터로는 부족하다.

```text
현재 손실 진입들이 이미 10:00 이전에 발생했기 때문에 개선 효과가 없다.
```

### 6.3 pullback/rebreak

추가 검증 후보로만 유지한다.

```text
진입 수는 줄었으나 남은 거래도 손절이다.
눌림 기준을 단순 OR high 이하로만 둘지, VWAP/거래량/캔들 조건을 추가할지 검토가 필요하다.
```

### 6.4 돌파봉 거래량 조건

보조 필터 후보로 유지한다.

```text
일부 손실 거래를 차단했지만, 남은 거래도 손실이다.
거래량 multiplier를 1.5로 고정하지 말고 1.2/1.5/2.0 grid 비교가 필요하다.
```

### 6.5 진입 후 3~5분 급락 필터

현재 표본에서는 가장 방어적으로 보인다.

```text
OR10 손실 진입 2건을 모두 차단했다.
다만 진입 0건이므로 수익성 개선이 아니라 손실 회피 가능성만 확인된 상태다.
```

### 6.6 10:00 확인 진입

강한 보수 필터로 유지한다.

```text
현재 표본에서는 전부 차단했다.
고점 추격 방지에는 유용할 수 있으나, 너무 보수적이라 기회 손실이 커질 수 있다.
```

---

## 7. 다음 작업

| 우선순위 | 작업 | 목적 |
|---:|---|---|
| 1 | ka10080 다음 거래일 분봉 누락 보완 | 평가 가능 종목 확대 |
| 2 | 과거 signal_date 신호 backfill | 표본을 1일에서 다일자로 확대 |
| 3 | 거래량 multiplier grid 비교 | 1.2/1.5/2.0 등 최적 범위 확인 |
| 4 | early_drop 기준 grid 비교 | 3분/5분, -0.5%/-0.7%/-1.0% 비교 |
| 5 | 10:00 확인을 단독 진입이 아닌 재확인 필터로 비교 | 과도한 진입 차단 완화 |
| 6 | after_1d/after_3d 후속 수익률 결합 | 장중 손실과 스윙 기대값 분리 |

---

## 8. 차단 조건

아래 조건이 해소되기 전까지 paper/real 주문 차단을 유지한다.

```text
- 표본 수 부족
- 다음 거래일 ka10080 분봉 누락
- 모든 실제 진입의 net return 음수
- positive_rate 0%
- after_1d/after_3d 미완성
- 사용자 승인 전 전략 수치 변경 금지
```

---

## 9. 마스터 플랜 반영 사항

`docs/strategies/00_master_trading_plan.md`에는 다음 판단을 반영한다.

```text
현재 어떤 OR 진입 변형도 주문 허용 근거가 아니다.
early_drop_filter와 10:00 confirmation은 손실 방어 후보로 유지한다.
다음 핵심 과제는 ka10080 backfill과 signal_date 확대다.
```
