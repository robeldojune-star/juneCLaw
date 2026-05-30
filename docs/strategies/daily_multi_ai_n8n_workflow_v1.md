# 시간대별 멀티 AI 운영 워크플로우 v1

작성 목적: 사용자가 제안한 시간대별 자동매매 운영 순서를 보존하고, 실제 운영에 맞게 조정 가능한 권장안을 정리한다.  
연결 전략: `opening_multi_factor_v1`, 향후 신규 전략 registry  
상태: 운영 설계안 / 현재 기준은 `docs/strategies/current_trading_execution_plan.md`를 우선한다. n8n은 1차 운영 경로가 아니라 비활성 백업/승인 UI 후보로 둔다.

---

## 0. 운영 철학

실제 100만 원 예산으로 약 1주일 운영한 경험을 전제로 한다.

핵심 교훈:

```text
1. 한 번에 완벽한 결과가 나오지 않는다.
2. 매일 손익 분석 보고를 만들고, 보고 내용을 기반으로 알고리즘을 수정한다.
3. 반복 가능한 교훈은 memory 또는 skill에 저장한다.
4. 새로운 전략이 필요하면 다시 등록하고 반복한다.
5. 분석 준비와 실시간 매수 판단을 분리하지 않으면 매수 타이밍을 놓친다.
6. 단타에서는 V팩터/밸류에이션 비중을 낮추고, 가격·수급·패턴·리스크 비중을 높인다.
7. 전략 수립에는 상위 모델, 일상 운영에는 저비용 모델을 사용해 API 비용을 관리한다.
```

---

## 1. 사용자 제안 샘플 시간표

아래는 사용자가 제안한 샘플이며, 운영 결과에 따라 조정 가능하다.

| 시간 | 워크플로우 | 목적 |
|---|---|---|
| 07:00 | `news_briefing_growth_analysis` | 아침 브리핑: 뉴스 수집 → 텔레그램 전송 |
| 07:30 | `stock-morning-signals` | 장 전 매매 신호 생성 |
| 08:00 | `stock_trading_daily_workflow` | 메인 거래 워크플로우: ETL → 지표 → 신호 → 주문 체크 → 텔레그램 보고 |
| 09:00 | `morning_investment_layer` | 실전 투자 아침 실행 |
| 09:30 | `stock_trading_workflow` | 추가 거래 워크플로우 테스트 |
| 15:00 | `evening_selloff_layer` + `aftermarket_multi_timeframe_collection` | 장후 매도 및 멀티타임프레임 수집 |
| 15:40 | `stock-nightly-collection` | 야간 OHLCV 수집 |

---

## 2. 권장 조정안 — 분석 준비와 실시간 실행 분리

사용자 피드백 중 가장 중요한 부분은 다음이다.

```text
데이터 분석을 사전에 완료하지 않으면, 스냅샷 데이터까지 함께 분석하느라 실제 매수 타이밍을 놓친다.
```

따라서 아침 운영을 세 층으로 분리한다.

| 층 | 시간 | 역할 | 무거운 작업 허용 여부 |
|---|---|---|---|
| 사전 분석층 | 07:00~08:30 | 뉴스, 재무, 전일 OHLCV, 지표, 후보군 선정 | 허용 |
| 실행 준비층 | 08:30~09:00 | API smoke, 계좌, 주문 가능 금액, 후보 압축 | 제한적 허용 |
| 실시간 실행층 | 09:00~10:00 | 스냅샷/분봉 기반 진입 판단, 알림/모의 주문 | 무거운 분석 금지 |

---

## 3. 권장 시간표 v1

| 시간 | 권장 워크플로우 | 담당 | 작업 내용 | 출력 | 모델 등급 |
|---|---|---|---|---|---|
| 06:50 | `system_health_check` | Monitoring AI / Hermes cron 또는 runner | 서버, .env 존재, Supabase/Kiwoom/OpenDART 최소 연결 확인 | health JSON | 저비용 |
| 07:00 | `news_briefing_growth_analysis` | Research AI | 뉴스/공시/성장 테마 수집, 위험 뉴스 제외 | 텔레그램 브리핑, `research_notes` | 중~상위 |
| 07:30 | `stock_morning_signals` | Research AI | 전일 데이터 기준 후보 종목, score breakdown 생성 | `trading_signals`, 후보 TOP N | 중간 |
| 08:00 | `stock_trading_daily_workflow` | Hermes/trading-runner + Python core | ETL 점검 → 지표 → 신호 → 주문 후보 점검 → 보고 | 일일 준비 리포트 | 저~중간 |
| 08:30 | `premarket_account_risk_check` | Monitoring AI | kt00004 계좌/예수금/보유종목/위험 이벤트 확인 | 거래 가능 여부 | 저비용 |
| 08:45 | `candidate_compression_layer` | Leader AI | 오늘 실제 감시할 종목을 TOP 5~10으로 압축 | `order_candidates` 후보 | 중간 |
| 09:00 | `morning_investment_layer` | Leader AI | 장 시작 직후 스냅샷 확인, 즉시 매수 금지/관찰 시작 | 장초반 상태 | 저비용 |
| 09:10 | `opening_10m_aggressive_layer` | Research/Leader AI | OR10 돌파, volume spike, score ≥ 70 확인 | 알림/모의 후보 | 저비용 |
| 09:30 | `opening_30m_standard_layer` | Research/Leader AI | OR30 표준형 진입 판단, score ≥ 70 확인 | 기본 BUY 후보 | 저비용 |
| 10:00 | `post_opening_monitoring` | Monitoring AI | 진입 실패/미체결/후보 탈락 이유 기록 | blocking report | 저비용 |
| 11:30 | `midday_position_review` | Monitoring AI | 보유종목 손익, 리스크, 점심장 유동성 둔화 확인 | 보유/감시 리포트 | 저비용 |
| 14:30 | `pre_close_risk_review` | Monitoring AI | 손절/익절/당일 청산 후보 점검 | 청산 후보 | 저비용 |
| 15:00 | `evening_selloff_layer` | Leader/Monitoring AI | 당일 청산, 매도 후보, 리스크 축소 | 청산 결과 | 저비용 |
| 15:20 | `aftermarket_multi_timeframe_collection` | Python core | snapshot_1m 누적 상태 확인 + 일봉/멀티타임프레임 데이터 수집 | `intraday_prices`, `daily_prices` | 저비용 |
| 15:40 | `stock_nightly_collection` | Python core / trading-runner | OHLCV 확정 수집, 지표 재계산 준비 | 수집 리포트 | 저비용 |
| 16:10 | `daily_pnl_feedback_report` | Monitoring AI | 당일 손익, 신호 대비 실행, 실패 원인 분석 | 텔레그램/문서 리포트 | 중간 |
| 20:00 | `strategy_review_if_needed` | Hermes / Research AI | 손익 리포트 기반 전략 개선안 작성. 매일 실행하지 않고 필요 시 실행 | 전략 수정 제안 | 상위 |

---

## 4. 각 워크플로우 상세

### 4.1 `news_briefing_growth_analysis` — 07:00

목적:

```text
장 시작 전 성장 테마, 주요 뉴스, 위험 뉴스, 공시 이슈를 파악한다.
```

입력:

```text
뉴스, 공시, OpenDART, 전일 후보 종목
```

출력:

```text
- 텔레그램 아침 브리핑
- 종목별 긍정/부정 플래그
- 당일 거래 제외 위험 이벤트
```

주의:

```text
뉴스 분석은 시간이 걸리므로 09:00 이후 실시간 매수 루프에 넣지 않는다.
```

---

### 4.2 `stock_morning_signals` — 07:30

목적:

```text
전일 확정 데이터와 사전 리서치를 바탕으로 장전 후보군을 만든다.
```

출력 예:

```text
TOP BUY 후보 5~10개
WATCH 후보
NO_TRADE / 위험 제외 종목
각 후보의 score breakdown 및 blocking conditions
```

---

### 4.3 `stock_trading_daily_workflow` — 08:00

역할:

```text
ETL → 지표 → 신호 → 주문 체크 → 텔레그램 보고를 하나의 일일 준비 파이프라인으로 실행한다.
```

단, 08:00에는 무거운 작업이 가능하지만, 09:00 이후에는 무거운 재계산을 금지한다.

---

### 4.4 `morning_investment_layer` — 09:00

목적:

```text
실전 투자 아침 실행 레이어. 단, 09:00 즉시 매수보다 스냅샷 안정화와 관찰 시작이 우선이다.
```

추천 규칙:

```text
09:00~09:05: 주문 금지, 데이터 안정화
09:05~09:10: smoke + snapshot 확인
09:10 이후: OR10 공격형 후보만 알림/모의
09:30 이후: OR30 표준형 후보를 기본 후보로 사용
```

---

### 4.5 `stock_trading_workflow` — 09:30

기존 샘플의 “추가 거래 워크플로우 테스트”는 아래처럼 목적을 명확히 둔다.

```text
opening_30m_standard_layer
```

이 레이어에서 `opening_multi_factor_v1`의 표준형 30분 진입 조건을 확인한다.

연결 기준:

```text
entry = max(OR30_high × 1.001, today_open + 0.35 × yesterday_range)
volume_spike_ratio >= 1.30
score >= 70
pattern_model_not_ready이면 자동 주문 금지
```

---

### 4.6 `evening_selloff_layer` — 15:00

목적:

```text
당일 청산, 손절/익절, 위험 축소를 수행한다.
```

초기 운영에서는 실제 주문보다 아래를 우선한다.

```text
- 보유 포지션 손익률 확인
- 당일 신호와 실제 실행 비교
- 청산 후보 알림
- 모의/승인형 매도 처리
```

---

### 4.7 `aftermarket_multi_timeframe_collection` / `stock_nightly_collection`

목적:

```text
장후 확정 데이터를 수집해 다음 날 아침 분석을 미리 끝낸다.
```

수집 대상:

```text
- 일봉 OHLCV
- 분봉/intraday bars
- 기술지표
- 거래대금/거래량 ranking
- 신호 결과
```

---

## 5. 피드백 루프 설계

매일 장후 다음 보고를 생성한다.

| 항목 | 설명 |
|---|---|
| 일일 손익 | 실현/평가 손익, 수익률, 수수료/슬리피지 추정 |
| 신호 품질 | BUY/WATCH/HOLD/NO_TRADE 개수, 실제 진입 여부 |
| 미실행 이유 | blocking conditions: 데이터 부족, 수급 부족, API 실패, 점수 미달 |
| 실패 원인 | 진입 후 손절, 미체결, 늦은 신호, 과열 진입 등 |
| 전략 피드백 | 임계값 조정 후보, 가중치 조정 후보, 신규 전략 필요성 |
| 다음 날 반영 | memory/skill/strategy registry 중 어디에 저장할지 결정 |

저장 원칙:

| 정보 | 저장 위치 |
|---|---|
| 당일 손익/실행 로그 | DB/reports/session, memory 금지 |
| 반복 교훈 | skill 또는 compact memory |
| 전략 변경 후보 | docs/strategies + strategy_registry |
| 확정 전략 수치 | JSON registry + 코드 |
| 민감정보 | `.env` only |

---

## 6. V팩터 편향 보완

사용자 피드백:

```text
단타 투자에서는 V팩터(밸류에이션)를 보는 것이 적합하지 않을 수 있다.
요소마다의 가중치를 조절하여 전략에 맞게 보완해야 한다.
```

권장:

| 전략 유형 | 가격/수급 | 패턴 | 재무/V팩터 | 리스크 |
|---|---:|---:|---:|---:|
| 데이트레이딩 | 55~65% | 15~25% | 5~10% | 15~20% |
| 스윙 | 35~45% | 20~25% | 20~30% | 10~15% |
| 중장기 | 20~30% | 10~20% | 40~50% | 10~20% |

`opening_multi_factor_v1`에서는 V팩터를 독립 매수 근거로 쓰지 않고, 위험 종목 제외 또는 보조 필터로만 사용한다.

---

## 7. 모델 그레이드 / API 비용 관리

| 단계 | 모델 등급 | 이유 |
|---|---|---|
| 전략 수립/딥리서치 | 상위 모델 | 정교한 분석, 오류 비용 큼 |
| 백테스트 해석 | 상위~중간 | 수치 해석과 전략 판단 필요 |
| 매일 뉴스 요약 | 중간 | 비용과 품질 균형 |
| 장중 모니터링 | 저비용 | 짧은 JSON 판정/알림 중심 |
| 단순 ETL/데이터 수집 | LLM 불필요 | Python/n8n만 사용 |
| 주문 실패 원인 분석 | 중간 | 오류 로그 해석 필요 |
| 주간 전략 리뷰 | 상위 모델 | 전략 변경 의사결정 |

비용 원칙:

```text
투자 수익이 API 비용을 상회해야 한다.
LLM은 판단/해석/리포트에 쓰고, 반복 계산은 Python으로 처리한다.
```

---

## 8. 운영 오케스트레이션 원칙

현재 1차 운영 경로는 Hermes cron + trading-runner이다. n8n은 비활성 백업/향후 승인 UI 후보로만 둔다.

오케스트레이션 계층이 담당:

```text
- 시간 스케줄
- Python stage 실행
- 성공/실패 분기
- 재시도 또는 alert
- 텔레그램/웹훅 알림
- 승인 게이트 후보
```

오케스트레이션 계층이 담당하지 않음:

```text
- 전략 수식 계산
- 주문 수량 계산
- Kiwoom 응답 파싱 복잡 로직
- 장기 memory 저장 판단
```

모든 Python 스크립트는 Hermes/n8n이 읽을 수 있도록 JSON stdout을 출력한다.

---

## 9. 단계별 적용 순서

| 단계 | 목표 | 상태 |
|---|---|---|
| 1 | 시간대별 운영 문서화 | 완료 |
| 2 | workflow JSON registry 작성 | 완료 |
| 3 | Hermes cron + trading-runner 직접 수집 경로 구축 | 완료 |
| 4 | ka10006 snapshot_1m 무결성 점검 | 진행 중 |
| 5 | 09:10/09:30 장초반 전략 실행 연결 | 대기 |
| 6 | 15:00/15:40 장후 수집 및 손익 리포트 연결 | 대기 |
| 7 | 충분한 백테스트 후 paper-only 피드백 루프 적용 | 대기 |

---

## 10. 다음 구현 후보

```text
1. docs/strategies/current_trading_execution_plan.md를 기준 계획으로 유지
2. scripts/inspect_snapshot_1m_status.py로 snapshot_1m 품질 점검
3. 각 시간대별 workflow가 같은 JSON 스키마를 출력하도록 통일
4. daily_pnl_feedback_report에 snapshot 누적 요약 반영
5. 필요 시 n8n은 백업/승인 UI 후보로만 연결
```
