# 시간순 전체 트레이딩 워크플로우 보고서

상태: 운영 보고서  
작성 기준: 2026-05-29 18:39 KST  
기준 workspace: `/home/june/trading`  
우선 기준 문서: `docs/strategies/current_trading_execution_plan.md`  
보조 기준 문서: `docs/strategies/daily_multi_ai_n8n_workflow_v1.md`, `docs/strategies/next_trading_day_intraday_operational_gate.md`, `docs/strategies/morning_news_briefing_template_v1.md`

---

## 0. 현재 운영 결론

현재 시스템은 **`ka10080` 과거 1분봉으로 OR10/OR30 백테스트를 수행하고, `ka10006 snapshot_1m`은 장중 실시간 감시/운영 품질 확인에 사용하는 단계**다. 실주문/모의주문 실행은 백테스트와 paper 검증 전까지 계속 차단한다.

핵심 결론은 다음과 같다.

```text
1. 장중 반복 수집의 1차 경로는 n8n이 아니라 Hermes cron + trading-runner다.
2. 과거 백테스트 데이터 기준은 `kiwoom_ka10080_minute / 1min`이다.
3. 장중 실시간 감시 데이터 기준은 `kiwoom_ka10006_snapshot / snapshot_1m`이다.
4. `ka10005` date-only 응답은 1분봉처럼 저장하거나 백테스트에 사용하지 않는다.
5. OR10/OR30은 후보별 score_details와 blocking_conditions를 출력하는 후보 평가 루프다.
6. rows_used와 total_variant_trades가 기준을 넘기 전까지 paper/real 주문은 모두 금지한다.
7. daily_pnl_feedback_report는 장후 피드백과 전략 수정 후보를 만들되, 즉시 전략 수치를 바꾸지 않는다.
```

---

## 1. 전체 시간순 운영 흐름 요약

| 시간대 | 단계 | 주 담당 | 현재 운영 경로 | 핵심 출력 | 현재 주문 상태 |
|---|---|---|---|---|---|
| 06:50 | 시스템/환경 점검 | Monitoring AI / Hermes | runner/CLI 후보 | API, DB, 컨테이너, `.env` 점검 | 주문 없음 |
| 07:00 | 뉴스·공시·테마 브리핑 | Research AI | 향후 n8n/Hermes 병행 후보 | 아침 브리핑, 위험 뉴스, 테마 | 주문 없음 |
| 07:30 | 장전 신호 생성 | Research AI | Python stage 후보 | BUY/WATCH/NO_TRADE, score breakdown | 주문 없음 |
| 08:00 | 일일 준비 워크플로우 | Hermes/trading-runner + Python | n8n은 orchestration/alert 보조 | ETL, 지표, 신호, 주문 후보 점검 | 주문 없음 |
| 08:30 | 계좌·리스크 확인 | Monitoring AI | Kiwoom kt00004 계좌 조회 패턴 | 예수금, 보유, 위험 이벤트 | 주문 없음 |
| 08:45 | 후보 압축 | Leader AI | `today_watchlist` stage | TOP 5~10 watchlist | 주문 없음 |
| 09:00~09:05 | 장 시작 안정화 | Leader/Monitoring | snapshot 관찰 | 장초반 데이터 안정화 | 즉시 매수 금지 |
| 09:05~09:10 | 장중 smoke/snapshot 확인 | Monitoring | `snapshot_1m` 품질 확인 | lag, rows, active_codes, 중복/품질 오류 | 주문 금지 |
| 09:10 | OR10 공격형 후보 루프 | Research/Leader | `opening_10m_aggressive_layer` | 후보별 score_details, blocking_conditions | `order_execution_enabled=false` |
| 09:30 | OR30 표준형 후보 루프 | Research/Leader | `opening_30m_standard_layer` | 후보별 score_details, blocking_conditions | `order_execution_enabled=false` |
| 10:00 | 장초반 모니터링 | Monitoring AI | timing alert/read-only 평가 | 미진입, 탈락, 차단 원인 | 주문 금지 |
| 11:30 | 중간 포지션/리스크 점검 | Monitoring AI | 향후 stage 후보 | 보유/감시 리포트 | 현재 보유/주문 없음 |
| 14:30 | 마감 전 리스크 점검 | Monitoring AI | 향후 stage 후보 | 손절/익절/청산 후보 | 현재 실주문 없음 |
| 15:00 | 장후/마감 청산 레이어 | Leader/Monitoring | 초기에는 리포트 중심 | 청산 후보, 위험 축소 | real 주문 금지 |
| 15:20 | 장후 멀티타임프레임 수집 | Python core | runner/collector | intraday/daily 데이터 누적 | 주문 없음 |
| 15:40~15:45 | 백테스트 readiness 리포트 | Hermes cron + runner | `check_backtest_readiness.py` | rows/trades/품질 gate | 기준 미달 시 blocked |
| 16:10 | 일일 PnL 피드백 | Monitoring AI | `daily_pnl_feedback_report` | 손익, 신호 대비 실행, 실패 원인 | 주문 없음 |
| 20:00 이후 | 전략 리뷰 | Hermes/Research AI | 필요 시 수동/문서화 | strategy_change_candidate | 사용자 승인 전 코드 변경 금지 |

---

## 2. 사전 준비 구간: 06:50~08:45

### 2.1 06:50 — 시스템/환경 점검

목적은 장 시작 전 운영 장애를 먼저 제거하는 것이다.

확인 항목:

| 항목 | 목적 | 실패 시 처리 |
|---|---|---|
| Docker 컨테이너 | `n8n`, `worker`, `postgres`, `redis`, `trading-runner` 실행 여부 | 장중 collector 실행 전 복구 |
| `.env` | Supabase/Kiwoom/OpenDART 설정 존재 여부 | 값 출력 없이 존재/형식만 점검 |
| Supabase 연결 | `intraday_prices`, signals, reports 저장 가능 여부 | 수집/신호 stage 차단 |
| Kiwoom 연결 | 실데이터 조회 가능 여부 | mock/random 대체 금지, stage blocked |
| Hermes cron | snapshot collector, readiness report schedule 확인 | system crontab이 아니라 Hermes cron으로 관리 |

현재 상태 메모:

```text
마지막 확인 기준 주요 Docker 서비스는 running.
Hermes snapshot collector cron은 enabled, */5 * * * *.
weekday readiness report cron은 월~금 15:45 실행.
```

### 2.2 07:00 — 뉴스·공시·테마 브리핑

목적은 장중 실시간 루프가 무거운 리서치 때문에 늦어지지 않도록, 뉴스/공시/테마 분석을 장 시작 전에 끝내는 것이다.

템플릿 문서:

```text
docs/strategies/morning_news_briefing_template_v1.md
```

브리핑은 아래 3개 묶음을 분리 생성한 뒤 통합 TOP 후보로 압축한다.

| 뉴스 유형 | 범위 | 목적 |
|---|---|---|
| 글로벌이슈 | 미국 증시, 중국 정책, 환율, 원자재, 지정학 리스크 | 국내 장 초반 시장 방향과 수혜/피해 업종 파악 |
| 기업공시 | 실적발표, 계약, M&A, 유상증자, 자사주, 임원 변동 | 개별 종목 이벤트 후보 발굴 |
| 테마급등 | SNS/커뮤니티 화제, 급등 테마, 거래량 급증, 작전주 의심 | 단기 수급 후보와 위험 테마 분리 |

출력:

```text
- 성장 테마/업종 브리핑
- 위험 뉴스 및 거래 제외 후보
- OpenDART/공시 기반 체크포인트
- 후보 종목별 긍정/부정 플래그
- 뉴스 → 종목 연결 고리
- 현재가/등락 최신 확인값
- 단타 관점 전략: 시초가 매수 / 눌림목 매수 / 관망 / 제외
```

운영 원칙:

```text
뉴스·공시 분석은 09:00 이후 OR10/OR30 루프에 넣지 않는다.
장중에는 이미 압축된 후보와 snapshot_1m만 사용한다.
브리핑은 주문 지시가 아니라 today_watchlist와 OR10/OR30 평가 입력이다.
rows/trades 기준 통과 전까지 paper/real 주문은 계속 금지한다.
```

### 2.3 07:30 — 장전 신호 생성

목적은 전일 확정 데이터와 사전 리서치를 바탕으로 장전 후보군을 생성하는 것이다.

확인해야 할 출력:

| 출력 | 설명 |
|---|---|
| BUY 후보 | 실제 감시 후보의 원천. 현재는 주문이 아니라 후보 생성 의미 |
| WATCH 후보 | 조건 일부 충족, 장중 관찰 필요 |
| NO_TRADE/제외 | 리스크, 뉴스, 유동성, 점수 미달 등 |
| score breakdown | 가격/수급/패턴/리스크/보조 V-factor 등 세부 점수 |
| blocking_conditions | BUY가 아닌 이유를 명확히 남김 |

`signal=0`이 발생하면 바로 전략 임계값을 바꾸지 않고 아래 네 가지로 분리한다.

```text
1. 데이터 부재: daily_prices, technical_indicators 최신 거래일 존재 여부
2. 날짜 필터: UTC/KST 경계, latest batch 조회 문제
3. 임계값: BUY threshold가 과도한지. 단, 즉시 변경 금지
4. 시장 조건: 실제로 조건을 만족한 종목이 없었는지
```

### 2.4 08:00 — 일일 준비 워크플로우

역할은 ETL, 지표, 신호, 주문 후보 점검, 리포트를 하나의 일일 준비 파이프라인으로 묶는 것이다.

현재 구조상 n8n은 다음 역할로 제한한다.

```text
- daily orchestration
- 알림/리포트 라우팅
- 향후 승인 UI 후보
```

장중 `snapshot_1m` 반복 수집의 1차 경로는 n8n이 아니라 Hermes cron이다.

### 2.5 08:30 — 계좌·리스크 확인

목적은 장 시작 전 주문 가능성과 위험 상태를 확인하는 것이다.

확인 항목:

| 항목 | 설명 |
|---|---|
| 예수금/주문 가능 금액 | Kiwoom `kt00004` 계좌 조회 패턴 재사용 |
| 보유 종목 | 기존 포지션 리스크 확인 |
| 미체결/위험 이벤트 | 중복 주문, 미체결, 거래 제한 이벤트 방지 |
| 주문 모드 | 현재는 paper/real 모두 차단 유지 |

현재 단계에서는 계좌 조회가 가능하더라도 주문 활성화 조건으로 해석하지 않는다.

### 2.6 08:45 — 후보 압축 / today_watchlist

목적은 장중 실시간 루프가 너무 많은 종목을 분석하지 않도록 TOP 5~10 watchlist로 압축하는 것이다.

출력 기준:

```text
- today_watchlist
- 후보별 score_details
- 후보별 blocking/risk flags
- paper_order_allowed=false
- real_order_allowed=false
```

---

## 3. 장중 실행 구간: 09:00~10:00

### 3.1 09:00~09:05 — 장 시작 안정화

장 시작 직후에는 호가/체결/스냅샷이 불안정할 수 있으므로 즉시 매수하지 않는다.

원칙:

```text
09:00~09:05: 주문 금지, snapshot 안정화 관찰
09:05~09:10: smoke + snapshot 품질 확인
09:10 이후: OR10 공격형 후보 평가
09:30 이후: OR30 표준형 후보 평가
```

### 3.2 09:05~09:10 — snapshot_1m 품질 확인

현재 장중 데이터의 기준은 다음으로 고정한다.

```text
source = kiwoom_ka10006_snapshot
time_frame = snapshot_1m
```

실행 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/inspect_snapshot_1m_status.py --days 2 --min-rows 20
```

정상 기준:

| 항목 | 정상 기준 |
|---|---|
| source | `kiwoom_ka10006_snapshot` |
| time_frame | `snapshot_1m` |
| rows | 장중 지속 증가 |
| active_codes | 최소 5, 가능하면 10개 이상 |
| latest_lag_minutes | 장중 수집 주기 대비 과도하게 벌어지지 않음 |
| duplicate_stock_timestamp_keys | `0` |
| quality_error_counts | `{}` |

해석 기준:

```text
장중 lag가 계속 증가하면 collector/runner/API 경로 점검.
장외/휴장/주말 latest_timestamp_stale은 장애로 보지 않음.
품질 오류 또는 중복이 있으면 백테스트와 주문 단계는 계속 blocked.
```

최근 확인값:

```text
rows=601
active_codes=14
duplicate_stock_timestamp_keys=0
quality_error_counts={}
장후 latest_lag_minutes 증가는 정상적인 안전 차단으로 해석
```

### 3.3 09:10 — OR10 공격형 후보 루프

실행 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_10m_aggressive_layer --pretty
```

목적:

```text
장초반 10분 구간에서 돌파/거래량/점수 조건을 만족하는 공격형 후보를 평가한다.
```

확인 항목:

| 항목 | 기준 |
|---|---|
| 데이터 소스 | 반드시 `snapshot_1m` |
| score_details | 후보별 출력 필수 |
| blocking_conditions | BUY가 아닌 이유 명확해야 함 |
| order_execution_enabled | 반드시 `false` |
| auto_order_guard | 반드시 blocked |

현재 상태:

```text
OR10 후보 루프는 score_details 출력 경로가 확인됨.
BUY 후보가 0이어도 blocking_conditions가 명확하고 주문 guard가 작동하면 정상.
```

### 3.4 09:30 — OR30 표준형 후보 루프

실행 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_30m_standard_layer --pretty
```

목적:

```text
30분 opening range를 기준으로 표준형 진입 후보를 평가한다.
OR30은 현재 기본 후보 루프로 취급한다.
```

확인 항목은 OR10과 동일하다.

```text
- snapshot_1m만 사용
- 후보별 score_details 출력
- BUY/NO_BUY 판단 사유 출력
- pattern_model_not_ready_for_auto_order 유지
- snapshot_1m_accumulation_and_backtest_required 유지
- order_execution_enabled=false
```

---

## 4. 장중 모니터링 구간: 10:00~15:00

### 4.1 10:00 — 장초반 결과 모니터링

목적은 OR10/OR30 평가 이후 실제 진입 후보가 왜 발생하지 않았는지 또는 왜 차단됐는지를 기록하는 것이다.

기록 항목:

| 항목 | 설명 |
|---|---|
| evaluated_count | 평가된 후보 수 |
| BUY 후보 수 | 현재는 0이어도 정상 가능 |
| 차단 조건 | 데이터 부족, 점수 미달, 패턴 미검증, 백테스트 미준비 등 |
| timing event | 돌파/거래량/조건 충족 후보 발생 여부 |
| missed timing | 늦은 신호, 후보 압축 누락 등 |

### 4.2 11:30 — 중간 포지션/리스크 리뷰

현재 실주문과 paper 주문이 차단되어 있으므로, 이 단계는 주로 관찰 리포트 성격이다.

확인 항목:

```text
- open_position_count
- today_order_count
- today_signal_count
- intraday timing event count
- 데이터 품질/lag 추세
```

### 4.3 14:30 — 마감 전 리스크 리뷰

향후 paper/real 단계에서는 손절/익절/청산 후보를 다루지만, 현재는 주문이 비활성화되어 있으므로 다음을 확인한다.

```text
- 장중 후보가 마감 전까지 어떻게 변했는지
- false breakout 후보가 있었는지
- 종가 부근 과열/급락 패턴이 있었는지
- 다음날 전략 리뷰 후보가 생겼는지
```

---

## 5. 장후 처리 구간: 15:00~16:30

### 5.1 15:00 — evening_selloff_layer

현재는 실청산/매도 주문 레이어가 아니라 장후 리스크 정리 후보 레이어로 해석한다.

초기 운영 기준:

```text
- 실제 주문보다 리포트 우선
- 보유 포지션이 있다면 손익률과 위험만 확인
- paper/real 주문은 rows/trades 기준 통과 전까지 금지
```

### 5.2 15:20 — 장후 멀티타임프레임 수집

목적은 다음 거래일 장전 분석에 필요한 확정 데이터를 수집하는 것이다.

수집/확인 대상:

```text
- snapshot_1m 누적 상태
- 일봉 OHLCV
- 기술지표
- 거래량/거래대금 ranking
- 신호 결과 및 후보 이력
```

### 5.3 15:40~15:45 — 백테스트 readiness 게이트

Hermes readiness report는 월~금 15:45 기준으로 운영한다.

실행 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/check_backtest_readiness.py
```

또는 직접 stage 실행:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage backtest_opening_strategy_90d --pretty
```

통과 기준:

| 항목 | 기준 |
|---|---:|
| rows_used | `>= min_rows_required` |
| total_variant_trades | `>= min_trades_required` |
| snapshot_quality_ok | `true` |
| backtest_rows_ok | `true` |
| backtest_trades_ok | `true` |

현재 차단 상태:

```text
rows_used=181 / min_rows_required=300
total_variant_trades=2 / min_trades_required=5
status=blocked
blocking_conditions=[insufficient_intraday_rows_for_backtest, insufficient_backtest_trade_count]
```

운영 판단:

```text
이 값들이 기준을 넘기 전까지 Phase 5 Leader 승인형 paper 주문과 real 주문은 모두 금지한다.
```

### 5.4 16:10 — daily_pnl_feedback_report

실행 명령:

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage daily_pnl_feedback_report --pretty
```

리포트 확인 항목:

| 항목 | 목적 |
|---|---|
| snapshot_1m_accumulation.rows | 장중 누적량 추세 확인 |
| active_codes | 감시 종목 수 확인 |
| latest_timestamp | 장중/장후 stale 해석 |
| quality_error_counts | 데이터 품질 확인 |
| today_signal_count | 장전/장중 신호 생성 여부 |
| today_order_count | 주문 발생 여부. 현재는 0이어야 안전 |
| intraday_timing_alert_summary | OR10/OR30 타이밍 후보 확인 |
| strategy_change_candidates | 전략 수정 후보 분리 |

최근 확인 상태:

```text
today_signal_count=0
today_order_count=0
open_position_count=0
today_executed_signal_count=0
snapshot rows=601
active_codes=14
duplicate keys=0
quality errors={}
strategy_change_candidate_count=1
status=blocked by no_today_signals_found
```

---

## 6. 야간/전략 리뷰 구간: 20:00 이후

### 6.1 전략 리뷰 원칙

전략 리뷰는 매일 무조건 코드를 바꾸는 단계가 아니다. daily/weekly feedback에서 반복 관찰된 문제를 `strategy_change_candidate`로 분리한 뒤 검증 절차를 거친다.

반영 절차:

```text
관찰
→ strategy_change_candidate 문서화
→ 백테스트/paper 검증
→ 사용자 승인
→ strategy_registry/code 반영
```

즉시 변경 금지 대상:

```text
- BUY threshold
- score weight
- order behavior
- risk limit
- paper/real order activation
```

### 6.2 전략 수정 후보 예시

| 관찰 결과 | 전략 수정 후보 | 즉시 변경 여부 |
|---|---|---|
| BUY 후보가 계속 0개 | 후보 압축 기준/점수 임계값 검토 | 금지 |
| 신호가 늦음 | OR10/OR30 조건 또는 alert 주기 검토 | 금지 |
| 돌파 후 실패 반복 | false breakout 필터 후보 | 금지 |
| 거래 수가 너무 적음 | threshold 과도 보수 여부 검토 | 금지 |
| 손실 변동성 큼 | 손절/포지션 크기 조정 후보 | 금지 |

---

## 7. 현재 데이터/게이트 상태

마지막 운영 점검 기준 상태는 다음과 같다.

### 7.1 snapshot_1m 상태

```text
source=kiwoom_ka10006_snapshot
time_frame=snapshot_1m
rows=601
active_codes=14
duplicate_stock_timestamp_keys=0
quality_error_counts={}
latest_lag_minutes는 장후 기준 증가 상태
```

해석:

```text
장후/휴장/주말 latest_timestamp_stale은 장애로 보지 않는다.
다음 실제 장중에 lag / rows / active_codes를 다시 확인한다.
```

### 7.2 OR10/OR30 상태

```text
score_details 출력 경로 정상
snapshot_1m 기반 사용
BUY 후보 0
order_execution_enabled=false
auto_order_guard blocked
```

대표 차단 조건:

```text
outside_market_hours_for_current_session_snapshot
pattern_model_not_ready_for_auto_order
snapshot_1m_accumulation_and_backtest_required
```

### 7.3 백테스트 readiness 상태

```text
rows_used=181 < 300
total_variant_trades=2 < 5
status=blocked
```

대표 차단 조건:

```text
insufficient_intraday_rows_for_backtest
insufficient_backtest_trade_count
```

### 7.4 주문 게이트 상태

현재 기본값은 다음과 같아야 한다.

```json
{
  "paper_order_allowed": false,
  "real_order_allowed": false,
  "order_execution_enabled": false
}
```

---

## 8. 금지사항

아래 항목은 현재 단계에서 절대 금지한다.

```text
1. ka10005 date-only 응답을 1min으로 저장하거나 백테스트에 사용
2. sample/mock/random market data로 백테스트 통과 처리
3. rows/trades 기준 통과 전 paper 주문 활성화
4. rows/trades 기준 통과 전 real 주문 활성화
5. n8n과 Hermes cron의 중복 장중 수집 활성화
6. 전략 threshold/weight/order behavior 임의 변경
7. secrets/API key/account number 출력 또는 문서 저장
```

---

## 9. 다음 실제 거래일 실행 체크리스트

다음 실제 거래일에는 아래 순서로 확인한다.

### 9.1 장중 snapshot 품질 확인

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/inspect_snapshot_1m_status.py --days 2 --min-rows 20
```

통과 판단:

```text
rows 증가
active_codes 최소 5, 가능하면 10 이상
duplicate=0
quality_error_counts={}
장중 latest_lag_minutes 과도 증가 없음
```

### 9.2 OR10 후보 루프 확인

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_10m_aggressive_layer --pretty
```

확인:

```text
score_details 출력
blocking_conditions 명확
order_execution_enabled=false
```

### 9.3 OR30 후보 루프 확인

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage opening_30m_standard_layer --pretty
```

확인:

```text
score_details 출력
blocking_conditions 명확
order_execution_enabled=false
```

### 9.4 백테스트 readiness 확인

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/check_backtest_readiness.py
```

차단 유지 기준:

```text
rows_used < min_rows_required 이거나
total_variant_trades < min_trades_required 이면 blocked 유지
```

### 9.5 장후 daily feedback 확인

```bash
docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner \
  python scripts/run_daily_workflow_stage.py --stage daily_pnl_feedback_report --pretty
```

확인:

```text
snapshot 누적 추세
signal_count/order_count
intraday timing events
strategy_change_candidates
```

---

## 10. 단계별 진입/종료 조건

| 단계 | 진입 조건 | 종료/통과 조건 | 미통과 시 |
|---|---|---|---|
| Phase 1 수집 안정화 | Hermes collector enabled | snapshot 품질 정상, 장중 lag 정상 | collector/runner/API 점검 |
| Phase 2 OR10/OR30 후보 검증 | snapshot_1m 사용 가능 | score_details, blocking_conditions 정상 출력 | 주문 차단 유지 |
| Phase 2.5 today_watchlist/timing alert | 장전 후보 존재 | watchlist와 timing event 평가 정상 | signal=0 원인 분리 |
| Phase 3 백테스트 readiness | 충분한 snapshot rows 후보 | rows/trades 기준 통과 | blocked 유지 |
| Phase 4 daily report | 장후 데이터 존재 | PnL/신호/차단/전략후보 리포트 생성 | 리포트 blocker 원인 분리 |
| Phase 4.5 전략 수정 후보 | 반복 문제 관찰 | 후보 문서화 및 검증 계획 | 즉시 코드 변경 금지 |
| Phase 5 Leader 승인형 paper | Phase 3 통과 + 사용자 승인 | paper 성과/리스크 검증 | real 주문 금지 |
| Phase 6 real 주문 | paper 검증 통과 + 사용자 명시 승인 | 제한적 real 운영 | 조건 미달 시 금지 |

---

## 11. 최종 운영 방침

현재의 올바른 운영 방향은 다음 한 문장으로 요약된다.

```text
다음 실제 거래일 장중에는 snapshot_1m 누적 품질과 OR10/OR30 score breakdown을 확인하되, rows/trades 기준이 통과되기 전까지 paper/real 주문은 계속 차단한다.
```

따라서 지금 필요한 작업은 주문 활성화가 아니라 다음 세 가지다.

```text
1. snapshot_1m 누적 유지
2. 다음 실제 장중 OR10/OR30 후보 루프 검증
3. 장후 readiness/daily feedback으로 signal=0 및 trade count 부족 원인 분리
```
