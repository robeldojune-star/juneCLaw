# 후지모토 시게루 1-2-6 분할매매 전략 초안 v1

원본 영상: https://youtu.be/RI5LwXBaN-0?si=6u9WUcK_n_5oC6MG  
자막 확인일: 2026-05-30  
상태: **전략 설계 초안 / 구현 전 검토용 / 주문 금지**  
적용 목적: 기존 `opening_multi_factor_v1`의 보조 필터 또는 별도 전략 후보로 검증한다.

> 주의: 본 문서는 투자 자문이 아니라 시스템 설계·백테스트용 전략 명세다. 실제 주문 전에는 실데이터 백테스트, 차트 검증, 모의투자, 비용/슬리피지 반영, 손실 한도 검증이 필요하다.

---

## 1. 영상 핵심 요약

영상은 후지모토 시게루식 매매를 다음 구조로 설명한다.

1. **시황 분석이 먼저**
   - 글로벌 유동성/M2, 금리, 미국 시장, 선물, 시장 심리를 먼저 본다.
   - 차트는 마지막 진입 타점 도구일 뿐이다.
2. **펀더멘탈로 종목을 추린다**
   - 업황, 매출, 영업이익, PBR 등으로 거래 대상 후보를 줄인다.
3. **기술적 분석으로 타점을 잡는다**
   - RSI, MACD, 일목균형표 3개를 기본 지표로 사용한다.
4. **2% 리스크 룰**
   - 한 거래에서 계좌 손실 허용액은 계좌의 2% 이내로 제한한다.
5. **1-2-6 분할 진입/청산**
   - 가격 하락 시 물타기가 아니라, 신호가 추가로 확인될수록 비중을 키운다.

---

## 2. 한국 주식/우리 시스템 적용 방향

### 2.1 전략 이름 후보

```text
fujimoto_126_trend_confirmation_v1
```

### 2.2 적용 프레임

영상은 일봉/스윙성 설명이 섞여 있지만, 우리 시스템에서는 아래 2가지 버전으로 나눈다.

| 버전 | 데이터 | 용도 | 우선순위 |
|---|---|---|---|
| A. 일봉/2~15일 보유형 | daily_prices + technical_indicators | 후보 선별/스윙 검증 | 2차 |
| B. 장중 1분봉/오프닝 보조형 | ka10080 과거 1분봉 + snapshot_1m | OR10/OR30 진입 신뢰도 보조 | 1차 |

현재 프로젝트 흐름상 **B. 장중 1분봉/오프닝 보조형**을 먼저 검증한다. 단, 영상의 핵심인 RSI/MACD/일목은 1분봉에서 노이즈가 크므로 OR10/OR30 돌파 전략의 단독 대체가 아니라 **보조 확인 필터**로 시작한다.

---

## 3. 데이터 요구사항

| 항목 | 필요 데이터 | 현재 사용 가능 경로 | 비고 |
|---|---|---|---|
| RSI | OHLCV 연속 캔들 | `intraday_prices` ka10080 1min 또는 daily | 기간 14 기본값 |
| MACD | 종가 시계열 | 동일 | 12/26/9 기본값 |
| 일목균형표 | 고가/저가/종가 | 동일 | 9/26/52 기본값. 1분봉에서는 최소 52개 이상 필요 |
| 시황 필터 | KOSPI/KOSDAQ/미국 선물/금리/M2 | 미구현 또는 외부 데이터 필요 | 초기에는 market_regime=unknown 처리 |
| 펀더멘탈 | OpenDART/일봉 후보 압축 결과 | trading_signals/후보 압축 | 단타에서는 보조 필터 |
| 리스크 | 계좌 평가금/포지션/손절거리 | Kiwoom 계좌 + paper ledger | 실제 주문 전 필수 |

---

## 4. 매수 진입 규칙 초안

### 4.1 Long 1단계: RSI 정찰 진입

```text
조건:
- RSI가 30 아래로 내려갔다가 다시 30 위로 회복
- 또는 장중형에서는 RSI가 40 아래에서 45~50 위로 회복하는 완화 조건을 별도 테스트
- OR10/OR30 전략에서는 아직 실제 매수하지 않고 `stage_1_probe_signal`로 기록 가능

비중:
- 전체 계획 포지션의 1/9
```

### 4.2 Long 2단계: MACD 확인 진입

```text
조건:
- MACD line이 Signal line을 상향 돌파
- 가능하면 MACD가 0선 아래 또는 0선 근처에서 골든크로스
- RSI가 다시 30 아래로 무너지지 않음

비중:
- 추가 2/9
- 누적 3/9
```

### 4.3 Long 3단계: 일목 추세 확정 진입

```text
조건:
- 전환선 > 기준선
- 가격이 구름대 상단을 상향 돌파
- 돌파 직후 도지/긴 윗꼬리면 즉시 진입 금지
- 구름대 상단이 저항에서 지지로 전환되는 재확인 캔들 우선
- 후행스팬이 과거 가격 위에 있으면 가산점

비중:
- 추가 6/9
- 누적 9/9
```

---

## 5. 매도/청산 규칙 초안

### 5.1 Long 포지션 청산

```text
1차 청산:
- MACD 데드크로스 발생
- 단, RSI가 50 위이고 가격이 구름대 위면 일부만 청산
- 청산 비중: 1/9

2차 청산:
- RSI가 50 아래로 하락
- 청산 비중: 2/9

3차 청산:
- 가격이 구름대 하단 또는 주요 지지 구간을 하향 이탈
- 청산 비중: 잔여 6/9 전량
```

### 5.2 손실 제한

영상은 “손절 없는 매매”라고 표현하지만, 시스템에서는 손실 제한 없이 운영하지 않는다.

```text
하드 리스크 룰:
- 1회 거래 최대 허용 손실: 계좌 평가금의 2% 이하
- 장중 전략 초기값: 1회 후보당 계좌 0.3~0.7% 위험으로 축소 테스트
- 손절 기준: OR low 이탈, 구름대 하단 이탈, 또는 진입 후 max_adverse_excursion 임계 초과
- 실제 주문 전 paper ledger에서 수수료/슬리피지/시장충격 bps 반영 필수
```

---

## 6. 점수화 설계 후보

전략을 바로 BUY/SELL로 쓰지 않고, 먼저 점수와 blocking condition을 남긴다.

```json
{
  "strategy": "fujimoto_126_trend_confirmation_v1",
  "score_total": 0,
  "score_details": {
    "rsi_recovery": 0,
    "macd_confirmation": 0,
    "ichimoku_confirmation": 0,
    "market_regime": 0,
    "fundamental_filter": 0,
    "risk_position_sizing": 0
  },
  "position_stage": "NONE|STAGE1|STAGE2|STAGE3|EXIT1|EXIT2|EXIT3",
  "blocking_conditions": []
}
```

| 항목 | 점수 | 기준 |
|---|---:|---|
| RSI 회복 | 15 | 과매도 이탈/50선 회복 구조 |
| MACD 확인 | 20 | 골든크로스/히스토그램 양전환 |
| 일목 확인 | 30 | 전환선>기준선, 구름대 돌파, 지지 전환, 후행스팬 |
| 시장 레짐 | 10 | KOSPI/선물/금리/유동성 방향 우호적 |
| 펀더멘탈/후보 품질 | 10 | 기존 daily 후보 압축, OpenDART/뉴스 리스크 제외 |
| 리스크/체결 가능성 | 15 | 2% 룰, 손절거리, 거래대금/호가 안정성 |
| **합계** | **100** | BUY 후보는 백테스트 후 임계값 결정 |

초기 blocking condition 후보:

```text
insufficient_intraday_bars_for_ichimoku
rsi_signal_not_confirmed
macd_signal_not_confirmed
ichimoku_cloud_not_confirmed
breakout_without_retest
doji_or_long_upper_wick_after_breakout
market_regime_unavailable
risk_per_trade_exceeds_limit
liquidity_too_low
backtest_gate_not_passed
paper_order_blocked
real_order_blocked
```

---

## 7. 기존 OR10/OR30 전략과 결합 방식

### 권장 1차 결합: 보조 필터

기존 오프닝 전략이 후보를 찾은 뒤, 후지모토 필터가 신호 품질을 평가한다.

```text
opening_multi_factor_v1 후보 발생
→ fujimoto_126_aux_filter 계산
→ score_details와 blocking_conditions 저장
→ alert_only 리포트
→ 백테스트 통과 전 주문 금지
```

예시:

| OR 신호 | Fujimoto 상태 | 처리 |
|---|---|---|
| OR10 상향 돌파 | RSI+MACD만 확인, 일목 미확인 | 관찰/알림만 |
| OR30 상향 돌파 | RSI+MACD+일목 확인 | 고신뢰 BUY 후보 |
| OR 상향 돌파 | 도지/긴 윗꼬리, 구름대 재지지 없음 | blocked |
| OR 하향 이탈 | MACD 데드크로스+RSI 50 하회 | EXIT/회피 후보 |

---

## 8. 백테스트 검증 계획

### 8.1 1차: 과거 1분봉 ka10080 기반

- 대상: KOSPI 주요 후보 또는 기존 watchlist
- 기간: 최소 60~90거래일
- 데이터: `intraday_prices`의 `source=kiwoom_ka10080_minute`, `time_frame=1min`
- 진입은 신호가 실제로 형성된 이후에만 허용한다.
- 일목 52개 캔들 이전에는 일목 조건을 계산하지 않는다.
- 첫 1분봉/첫 OR 캔들에서 즉시 돌파 처리하는 look-ahead 오류 금지.

### 8.2 성과 지표

| 지표 | 기준 후보 |
|---|---|
| trade count | 너무 적으면 전략/임계값 문제로 재검토 |
| win rate | 단독보다 OR 결합 시 개선되는지 비교 |
| avg return | 수수료/슬리피지 차감 후 양수 필요 |
| max drawdown | 단독/결합 모두 확인 |
| MFE/MAE | 1-2-6 단계별 유효성 검증 |
| blocked signal outcome | 차단된 신호가 실제로 나빴는지 추적 |

### 8.3 시각 검증 필수

사용자 선호에 따라 날짜별 1분봉 차트에 다음을 표시한다.

```text
- OR10/OR30 range
- RSI stage1 marker
- MACD stage2 marker
- Ichimoku stage3 marker
- entry/exit marker
- blocked reason label
```

---

## 9. 구현 전 의사결정 포인트

1. 이 전략을 **기존 OR10/OR30 보조 필터**로 붙일지, **별도 전략**으로 백테스트할지 결정 필요.
2. 장중 1분봉 기준 RSI 과매도 임계값을 `30 회복`으로 둘지, `40~50 회복`도 함께 테스트할지 결정 필요.
3. 일목균형표는 1분봉에서 지연이 크므로 1분/3분/5분 중 어떤 봉으로 볼지 비교 필요.
4. 한국 주식에서 숏 포지션은 현실 제약이 크므로 초기 구현은 **롱 진입/청산 전용**으로 제한 권장.
5. 실제 주문은 금지하고, 우선 `alert_only` + `signal_events` 기록 + 차트 검증으로 진행한다.

---

## 10. 결론

영상 내용은 전략화 가능하다. 다만 그대로 “RSI/MACD/일목이면 수익”으로 구현하면 위험하다. 우리 시스템에서는 다음처럼 안전하게 적용한다.

```text
거시/후보 압축
→ OR10/OR30 장초반 후보
→ RSI/MACD/일목 1-2-6 보조 확인
→ score_details + blocking_conditions 기록
→ ka10080 백테스트 + 1분봉 차트 검증
→ paper 검증 전 주문 금지
```

초기 추천 방향은 `fujimoto_126_trend_confirmation_v1`을 **기존 opening strategy의 보조 필터**로 붙여서, BUY 후보 신뢰도와 EXIT/회피 판단을 개선하는 것이다.
