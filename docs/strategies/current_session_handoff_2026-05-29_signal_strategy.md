# 현재 세션 이어가기 보고서 — 시게루식 신호 기반 단타+스윙 자동화

상태: 이어가기 기준 보고서  
작성 기준: 2026-05-29  
기준 workspace: `/home/june/trading`

---

## 1. 현재 결론

데이터 수집/검증 토대는 만족 가능한 수준까지 구축됐다.

```text
ka10080 과거 1분봉 수집: 정상
데이터 중복/OHLC 품질: 정상
차트 검증: 가능
일봉 BUY/HOLD/SELL 신호: 생성됨
후보 압축: 작동
```

이제 핵심은 데이터 수집이 아니라 **생산된 신호를 제대로 활용하는 구조**다.

사용자 목적:

```text
시황 분석으로 상승 가능 종목을 추리고,
기술적 분석으로 매수/매도 신호를 만들고,
사람이 공포/탐욕 때문에 못 하는 진입·청산을 시스템이 관찰/기록/후보화한다.
단타만이 아니라 스윙도 적절히 섞는다.
```

---

## 2. 현재 신호 생산 상태

`trading_signals` 기준:

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

최신 BUY 상위 후보:

| 종목 | 신호 | 점수 | 가격 |
|---|---|---:|---:|
| 현대차 `005380` | BUY | 87 | 677000 |
| SK스퀘어 `402340` | BUY | 85 | 1237000 |
| 삼성전자 `005930` | BUY | 82 | 299500 |
| SK하이닉스 `000660` | BUY | 75 | 2289000 |

---

## 3. 현재 신호 활용 문제

신호는 생산되지만 활용이 끊긴다.

```text
technical_score_v1 일봉 신호 생성: 정상
→ candidate_compression_layer 후보 압축: 정상
→ opening_10m/30m 후보 루프: 대부분 HOLD/blocked
→ simulate_approved_orders: 후보 0개로 blocked
→ orders/positions: 없음
→ missed_entry/missed_exit 기록: 없음
```

후보 압축 결과:

```text
today_signal_count = 50
buy_signal_count = 23
candidate_count = 10
```

opening loop 결과:

```text
candidate_count = 10
evaluated_count = 10
buy_candidate_count = 0
alerts = [no_opening_buy_candidates]
```

대표 차단 조건:

```text
pattern_model_not_ready
fujimoto_volume_insufficient
financial_filter_failed
fujimoto_financial_data_missing
fujimoto_stage_entry_not_ready
```

문제는 차단 자체가 아니라, 차단된 신호의 이후 결과가 기록되지 않는 것이다.

---

## 4. 전략 방향 재정의

시게루식으로 해석한 자동화 구조는 4층이다.

```text
1. 시황 분석
2. 종목 선별
3. 분봉 진입 신호
4. 매도/보유 신호
```

### 4.1 시황 분석

목적:

```text
오늘 매매해도 되는 시장인가?
어떤 섹터/테마가 강한가?
```

입력 후보:

```text
뉴스, 지수, 미국장, 반도체지수, 환율, 금리, 섹터별 거래대금, 테마 급등
```

### 4.2 종목 선별

현재 구현:

```text
technical_score_v1
candidate_compression_layer
```

추가 필요:

```text
시황/섹터 매칭
뉴스/공시
재무 안정성
최근 1~3일 모멘텀
```

### 4.3 분봉 진입

일봉 BUY는 바로 매수가 아니라 후보다.

```text
일봉 BUY = 후보 선정 신호
분봉 ENTRY_SIGNAL = 실제 진입 트리거
```

### 4.4 매도/보유

매도는 반드시 신호화해야 한다.

```text
STOP_LOSS_SIGNAL
TAKE_PROFIT_SIGNAL
TIME_EXIT_SIGNAL
TRAILING_STOP_SIGNAL
TREND_BREAK_SIGNAL
SWING_HOLD_SIGNAL
PARTIAL_SELL_SIGNAL
```

---

## 5. 단타와 스윙 분리

### 5.1 shigeru_intraday_v1

```text
목적: 당일 단타
진입: 시황 양호 + 일봉 BUY 후보 + OR10/OR30 분봉 돌파
청산: 손절/익절/15:20 시간청산
보유: 당일
```

현재 백테스트 기본:

```text
OR10: 09:00~09:10 range, 09:10 이후 돌파 진입
OR30: 09:00~09:30 range, 09:30 이후 돌파 진입
stop_loss_pct = -1.0
take_profit_pct = +1.5
time_exit = 15:20
fee_bps = 23
slippage_bps = 10
```

현재 결과:

```text
OR10 trades=18, avg_return=-1.0765%, stop_loss=12, take_profit=5
OR30 trades=14, avg_return=-1.2741%, stop_loss=10, take_profit=2
```

판정:

```text
현재 단타형은 성과 음수. paper/real 적용 금지.
```

### 5.2 shigeru_swing_3d_v1

```text
목적: 장초반 강한 신호 후 1~3거래일 추세 추종
진입: 일봉 BUY + 분봉 진입 신호
청산: +5%/+10% 익절, -2~-3% 손절, trailing stop, 3거래일 시간청산
보유: 1~3거래일
```

하이닉스 사례:

```text
000660 2026-05-22 진입가 약 1,950,000
5/26 종가 매도 수익률 +5.23%
5/27 종가 매도 수익률 +15.03%
```

삼성전자 가정 분석:

```text
005930 2026-05-22 10:00 진입가 292,750
5/22 15:00 수익률 +0.0854% → 당일 매도 신호 없음
5/26 15:30 수익률 +2.1349%
5/27 +5% 익절 신호 발생 가능
```

판정:

```text
스윙형은 검토 가치 있음. 다종목 batch 백테스트 필요.
```

---

## 6. 다음 핵심 구현: signal_events

현재 가장 필요한 것은 전략 수식 추가보다 신호 활용 이벤트 기록이다.

필요 event_type:

```text
DAILY_ENTRY_CANDIDATE
INTRADAY_ENTRY_SIGNAL
BLOCKED_ENTRY_SIGNAL
MISSED_ENTRY
EXIT_SIGNAL
MISSED_EXIT
PAPER_ORDER_CANDIDATE
```

목적:

```text
일봉 BUY를 따랐으면 어떻게 됐나?
opening layer가 차단한 게 맞았나?
사람이 안 들어간 게 손해였나?
매도 신호를 무시한 결과가 어땠나?
```

---

## 7. 실전 계좌 조회 준비

사용자 요청:

```text
.env 파일 수정해서 실전 계좌 조회 검증 테스트 진행
```

보안 원칙:

```text
.env 내용은 출력하지 않는다.
계좌번호/토큰/API key/secret은 보고서나 채팅에 남기지 않는다.
사용자가 터미널에서 직접 수정한다.
```

현재 코드가 지원하는 구조:

```text
KIWOOM_REST_API_KEY_PROD
KIWOOM_REST_API_SECRET_PROD
KIWOOM_ACCOUNT_NO_PROD
KIWOOM_REST_API_KEY_MOCK
KIWOOM_REST_API_SECRET_MOCK
KIWOOM_ACCOUNT_NO_MOCK
```

또는 기존 공통 키:

```text
KIWOOM_REST_API_KEY
KIWOOM_REST_API_SECRET
KIWOOM_ACCOUNT_NO
TRADING_ENV
```

권장:

```text
mock/prod 접미사 구조로 전환하고, 스크립트에서 --trading-env mock/prod 명시.
cron이 TRADING_ENV를 바꾸지 않게 유지.
```

실전 계좌 읽기 전용 검증 명령:

```bash
python3 scripts/check_kiwoom_account_balance.py --trading-env prod
```

현재 검증 결과:

```text
.env 구조: *_MOCK / *_PROD 접미사 분리 완료, 중복 키 없음
prod 계좌 읽기 전용 조회: 성공
account_no: [REDACTED]
cash_or_deposit: 51,455원
total_estimated_asset: 863,673원
holdings_count: 4
read_only: true
```

주의:

```text
실전 주문 API는 호출하지 않았다.
실전 주문은 별도 real-order multi-key gate와 사용자 승인 없이는 계속 금지한다.
```

---

## 8. 다음 액션 순서

1. 사용자가 `.env`에 prod 키/계좌를 직접 입력한다.
2. 키 목록만 마스킹 확인한다.
3. `check_kiwoom_account_balance.py --trading-env prod` 실행.
4. 실전 계좌 잔고/보유종목을 `[REDACTED]` 계좌번호로 읽기 전용 확인한다.
5. 그 후 `signal_events` 테이블/로그 설계를 구현한다.
6. `technical_score_v1` → `DAILY_ENTRY_CANDIDATE` event 변환.
7. `analyze_daily_to_minute_signal_scenario.py`를 다종목 batch로 확장.

---

## 9. 현재 금지 사항

```text
실전 주문 API 호출 금지
real order executor 구현 금지
cron 기반 실전 자동 주문 금지
백테스트 성과 음수 상태에서 paper/real 전환 금지
```

실전 계좌 확인은 읽기 전용만 수행한다.
