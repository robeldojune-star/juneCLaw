# 백테스트·모의·실전 모드 분리 운영 정책

상태: 운영 기준 초안 / 자동 모드 전환 방지  
작성 기준: 2026-05-29  
기준 workspace: `/home/june/trading`

---

## 1. 사용자가 원하는 목표

목표는 하나의 자동 모드 전환 시스템이 아니라, 다음 단계별 검증 파이프라인이다.

```text
1. 백테스트용 과거 데이터 수집
2. 데이터 무결성/차트 검증
3. 전략 검토 및 개선
4. 전략 적용 후 모의테스트/paper 검증
5. 제한된 실전테스트
6. 실전에서 체결/슬리피지/가격충격/미체결 문제 확인
```

중요한 제약:

```text
- 모의 모드에서는 과거 데이터 수집 가능
- 실전 모드에서는 과거 데이터 수집 불가 또는 제한적
- 실전 계좌는 100만원 미만
- 모의 계좌 예수금은 아직 모름
- 모의 체결은 실제 시장 가격충격이 없음
- 실전에서는 내가 진입하면 가격이 밀리는 경험적 문제가 있음
- 크론잡이 시간별로 모드를 바꾸면 데이터 수집/주문 모드가 섞일 위험이 있음
```

---

## 2. 결론: 모드 전환이 아니라 목적별 분리

`TRADING_ENV`를 시간에 따라 자동으로 mock/prod 전환하지 않는다.

대신 각 작업이 자기 목적을 명시한다.

| 목적 | Kiwoom env | 주문 가능 여부 | 설명 |
|---|---|---:|---|
| 과거 데이터 수집 | mock 고정 | 불가 | `ka10080` 과거 1분봉 수집, 백테스트용 |
| 백테스트 | DB 데이터만 사용 | 불가 | `kiwoom_ka10080_minute/1min` 기반 |
| 장중 실시간 관찰 | prod 명시 가능 | 불가 | `ka10006 snapshot_1m`, 실시간 호가/현재가 감시 |
| 모의/paper 주문 | mock 또는 DB simulation | Kiwoom 실주문 불가 | `orders.status=SIMULATED` 기록만 |
| 실전 테스트 | prod | 다중 게이트 통과 후만 | 별도 real-order executor 필요. 현재는 금지 |

핵심 원칙:

```text
크론은 TRADING_ENV를 바꾸지 않는다.
스크립트가 --trading-env mock/prod를 명시한다.
주문 API는 별도 실행기로 분리하고, 기본 workflow에는 넣지 않는다.
```

---

## 3. 왜 Kiwoom 모의/실전 URL이 다른가

일반적으로 모의투자 서버와 실전투자 서버는 목적이 다르다.

| 서버 | 목적 | 특성 |
|---|---|---|
| 모의 서버 | API 개발/검증/연습 | 과거조회/모의계좌/가상체결 중심. 실제 시장 체결 영향 없음 |
| 실전 서버 | 실제 주문/실시간 시세/계좌 | 안정성/보안/주문 리스크 우선. 과거 대량 데이터 조회는 제한될 수 있음 |

사용자 질문에 대한 해석:

```text
실전 서버는 실시간 대량 주문/시세/계좌 안정성이 우선이라, 백테스트용 과거 대량 데이터 수집을 제한하거나 별도 chart API/모의 환경으로 분리했을 가능성이 높다.
```

따라서 백테스트 데이터는 모의/차트 조회 환경에서 수집하고, 실전 서버는 실시간 관찰·계좌·주문 검증에 집중시키는 구조가 안전하다.

---

## 4. 모의테스트와 실전테스트는 분리한다

전략 적용 후 흐름은 다음이다.

```text
백테스트 통과
→ paper/simulated order 기록
→ 모의 계좌 또는 DB paper ledger 검증
→ 실전 shadow mode
→ 100만원 미만 소액 real pilot
→ 체결/미체결/슬리피지/가격충격 보고서
```

모의테스트와 실전테스트를 같은 모드 전환으로 처리하지 않는다.

이유:

```text
모의는 체결이 잘 된 것처럼 보여도 실제 호가 충격이 없다.
실전은 소액이라도 내 주문이 얇은 호가를 밀 수 있다.
따라서 실전 테스트의 목적은 수익률보다 체결 품질/가격충격 검증이다.
```

---

## 5. 계좌 예산 정책

### 5.1 실전 계좌

사용자 기준:

```text
실전 계좌 < 1,000,000원
```

초기 실전 테스트 권장 제한:

```text
real_pilot_total_budget <= 100,000원
per_order_budget <= 20,000~30,000원
max_real_orders_per_day <= 1~3건
시장가 금지, 지정가 우선
거래대금 얇은 종목 제외
```

실전 테스트에서 봐야 할 것:

```text
신호 발생 후 주문 전송 지연
지정가 미체결률
부분체결
진입 직후 가격 하락/호가 밀림
백테스트 entry price와 실제 체결가 차이
수수료/세금/슬리피지 반영 후 기대값
```

### 5.2 모의 계좌

모의 계좌 금액은 현재 모른다.

따라서 읽기 전용으로 확인한다.

```bash
python3 scripts/check_kiwoom_account_balance.py --trading-env mock
```

실전 계좌도 읽기 전용 확인만 한다.

```bash
python3 scripts/check_kiwoom_account_balance.py --trading-env prod
```

계좌번호/토큰은 출력하지 않는다.

---

## 6. 현재 코드 반영 사항

추가/수정:

```text
core/trading_mode.py
scripts/collect_intraday_90d.py
scripts/collect_current_session_snapshots.py
scripts/check_kiwoom_account_balance.py
scripts/simulate_approved_orders.py
scripts/run_daily_workflow_stage.py
```

실행 목적별 모드:

```text
collect_intraday_90d           -> --trading-env mock
collect_current_session_snapshots -> --trading-env prod
simulate_approved_orders       -> paper_only, Kiwoom 실주문 API 호출 없음
check_kiwoom_account_balance   -> mock/prod 읽기 전용
```

실전 주문 API를 부를 수 있는 조건은 현재 false다.

`core/trading_mode.py` 기준:

```text
REAL_ORDER_ENABLED=true
USER_CONFIRMED_REAL_ORDER=true
READINESS_REAL_ORDER_GATE=true
kiwoom_env=prod
```

위 3개가 모두 켜지기 전에는 실전 주문 API 호출 불가로 설계한다.

---

## 7. 크론잡 영향 해결

현재 Hermes cron:

```text
trading-snapshot-1m-collector-no-n8n: 장중 snapshot 수집
trading-backtest-readiness-daily-report: 장후 readiness 보고
```

해결 원칙:

```text
1. cron이 .env의 TRADING_ENV를 바꾸지 않는다.
2. cron이 실행하는 stage가 --trading-env를 명시한다.
3. data collection cron은 주문 API를 호출하지 않는다.
4. readiness cron은 읽기/보고만 한다.
5. 실전 주문 cron은 만들지 않는다. 사용자가 명시 승인하기 전까지 금지한다.
```

현재 확인:

```text
등록된 cron 2개 모두 주문 API 호출 없음.
```

---

## 8. 다음 개발 순서

1. `ka10080` 수집 완전성 보강
   - next-key 또는 base_dt 촘촘한 이동
   - 09:00~09:30 누락 날짜 재수집

2. 백테스트 eligible-day 필터
   - opening coverage 없는 날짜 제외
   - partial day 제외

3. 전략 개선
   - OR10/OR30 score_details replay
   - 손절/익절/수수료/슬리피지 반영

4. paper/simulated ledger
   - 모의 계좌 예수금 확인
   - DB paper ledger로 체결 가정 기록
   - Kiwoom 모의 주문 API 사용 여부는 별도 결정

5. real pilot 설계
   - 100만원 미만 계좌 기준
   - 1일 1~3건, 종목당 2~3만원 수준
   - 실전 체결 품질 리포트

---

## 9. 현재 최종 정책

```text
백테스트 데이터 수집 = mock/ka10080 전용
장중 실시간 관찰 = prod/ka10006 가능, 주문 없음
모의테스트 = DB simulated/paper 우선, Kiwoom 실주문 없음
실전테스트 = 별도 승인형 real pilot, 현재는 금지
자동 시간별 mock/prod 전환 = 금지
```
