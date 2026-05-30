# 트레이딩 워크플로우 방향성 검토 결과보고서

작성 시각: 2026-05-29 12:07 KST  
대상 workspace: `/home/june/trading`  
기준 문서: `docs/strategies/current_trading_execution_plan.md`  
검토 목적: 지금까지의 운영 전환, 아침 브리핑부터 장중 타이밍 포착, 승인형 paper 주문, 장후 전략 개선 루프까지의 전체 방향이 사용자 목표와 맞는지 점검한다.

---

## 1. 결론 요약

현재 방향은 **데이터 안정화와 주문 안전장치 측면에서는 올바르다.**  
다만 사용자 목표는 단순 분석 보고서가 아니라, 아래와 같은 **운영형 매매 보조 시스템**이다.

```text
아침 분석
→ 오늘 매매 후보 확정
→ 장중 타이밍 감시
→ 신호/알림/승인형 실행
→ 장후 결과 분석
→ 전략 수정 후보 도출
→ 검증 후 전략 반영
```

따라서 현재 계획은 유지하되, 다음 두 축을 명시적으로 보강해야 한다.

1. **장중 타이밍 알림 레이어**  
   분석 결과가 실제 진입 타이밍 포착으로 연결되어야 한다.

2. **분석 기반 전략 수정 루프**  
   daily report가 단순 손익 보고서가 아니라 전략 수정 후보를 만드는 입력 데이터가 되어야 한다.

즉, 최종 목표는 단순 자동매매가 아니라 **학습하는 매매 운영 시스템**이다.

---

## 2. 현재 운영 상태 평가

### 2.1 데이터 수집 구조

현재 운영 구조는 다음과 같다.

```text
Hermes cron, no_agent=true
  -> ~/.hermes/scripts/trading_snapshot_collector.py
      -> trading-runner
          -> collect_current_session_snapshots
          -> inspect_snapshot_1m_status
```

저장 기준:

```text
source = kiwoom_ka10006_snapshot
time_frame = snapshot_1m
```

평가:

| 항목 | 상태 | 평가 |
|---|---:|---|
| ka10005 분봉 사용 | 폐기 | 올바름 |
| ka10006 snapshot 누적 | 운영 중 | 올바름 |
| Hermes cron 직접 호출 | 운영 중 | n8n 복잡도 감소 측면에서 적합 |
| n8n active workflow | false | 중복 호출 방지 측면에서 적합 |
| 품질 watchdog | 연결 완료 | 운영 안정성 향상 |

현재 확인값:

```text
cron last_status = ok
rows = 111~141+
active_codes = 10
duplicate = 0
quality_error_counts = {}
latest_lag_minutes = 약 3~6분
```

판단:

> Phase 1 수집 안정화는 운영 가능한 상태로 진입했다. 단, 백테스트/주문 검증에는 아직 누적 기간이 부족하다.

---

## 3. 기존 방향의 장점

현재까지 진행한 방향에는 다음 장점이 있다.

### 3.1 오염된 데이터 전제 제거

`ka10005`를 분봉처럼 사용하는 전제를 버린 것은 핵심적으로 올바른 결정이다.  
잘못된 분봉 데이터로 백테스트를 돌리면 전략 성과가 왜곡되고, 이후 주문 판단까지 오염될 수 있다.

현재는 `ka10006 snapshot_1m`만 공식 장중 데이터 소스로 인정한다.

### 3.2 주문 안전장치 유지

현재 OR10/OR30은 다음 조건을 유지한다.

```text
order_execution_enabled = false
auto_order_guard 유지
snapshot_1m_accumulation_and_backtest_required 유지
```

이는 실주문 리스크를 막는 데 필수적이다.

### 3.3 n8n 의존도 축소

n8n은 백업/승인 UI 후보로 남기고, 단순 반복 작업은 Hermes cron + trading-runner로 직접 호출한다.  
사용자 선호인 CLI/Hermes 중심 운영과 맞다.

### 3.4 daily report에 데이터 품질 포함

`daily_pnl_feedback_report`에 `snapshot_1m_accumulation`이 포함되었다.  
이는 장후 피드백에서 손익뿐 아니라 입력 데이터의 품질까지 함께 평가할 수 있게 만든다.

---

## 4. 현재 계획의 한계

현재 계획은 안전하지만, 사용자 목표 전체를 만족하기에는 아직 부족하다.

### 4.1 분석과 실행 사이의 간격

현재 구조는 다음에 가깝다.

```text
수집
→ 검증
→ OR10/OR30 평가
→ blocked
→ daily report
```

하지만 사용자가 원하는 구조는 다음이다.

```text
아침 브리핑
→ 오늘 후보 확정
→ 장중 타이밍 포착
→ 즉시 알림
→ 승인형 paper 실행
→ 장후 복기
```

따라서 단순히 분석 결과를 만드는 것만으로는 부족하다.

### 4.2 장중 타이밍 감시가 아직 약함

사용자 문제의 핵심은 다음이다.

```text
분석은 되었지만 실제 장중 매매 타이밍을 놓친다.
```

이는 백테스트 이전에도 해결해야 할 운영 문제다.  
즉, 장중에는 무거운 리서치가 아니라 빠른 타이밍 감시가 필요하다.

필요한 감시 항목:

- OR10 상단 돌파
- OR30 상단 돌파
- 거래량 급증
- 시초가 회복
- 전일 고가 돌파
- 급등 후 추격매수 위험
- 데이터 지연 여부
- 리스크 차단 조건

### 4.3 전략 수정 루프가 아직 명시적이지 않음

현재 daily report는 수집 상태와 손익/신호 상태를 보고하지만, 최종적으로는 다음으로 이어져야 한다.

```text
daily report
→ 실패/성공 원인 분석
→ strategy_change_candidate 생성
→ 검증
→ 전략 registry/code 반영
```

전략은 고정된 것이 아니라, 분석 결과에 의해 수정되어야 한다.

---

## 5. 목표 운영 구조

향후 전체 시스템은 다음 네 개 AI/레이어 역할로 정리하는 것이 적합하다.

### 5.1 Research AI — 장 시작 전 분석

역할:

```text
뉴스/공시/시장 분위기 분석
전일 OHLCV/지표 분석
오늘 후보 종목 5~10개 선정
후보별 진입 시나리오 작성
```

산출물:

```text
today_watchlist
morning_reason
candidate_score
entry_scenario
risk_blocking_conditions
```

---

### 5.2 Monitoring AI — 장중 감시

역할:

```text
snapshot_1m 감시
OR10/OR30 계산
거래량/돌파/눌림 감지
타이밍 알림 발생
놓친 타이밍 기록
```

장중에는 무거운 분석을 하지 않는다.  
목표는 빠른 판단과 기록이다.

---

### 5.3 Leader AI — 승인형 실행 판단

역할:

```text
진입 후보 품질 판단
리스크 체크
주문 크기/손절/익절 제안
사용자 승인 요청
paper 주문 실행 또는 기록
```

초기 단계에서는 실주문이 아니라 paper-only가 맞다.

---

### 5.4 Daily Review AI — 장후 복기와 전략 수정 후보

역할:

```text
오늘 후보 대비 실제 신호 분석
알림 발생/미발생/놓친 타이밍 분석
paper 결과 분석
실패 원인 분류
전략 수정 후보 도출
```

수정 후보는 바로 코드에 반영하지 않고, 먼저 `strategy_change_candidate`로 기록한다.

---

## 6. 수정된 Phase 제안

기존 Phase는 유지하되, 사용자 목표를 반영하여 다음처럼 확장한다.

### Phase 1 — snapshot_1m 수집 안정화

상태: **운영 중 / 정상**

목표:

```text
ka10006 snapshot_1m을 장중 안정적으로 누적한다.
```

현재 정상 기준:

```text
cron last_status=ok
quality_error_counts={}
duplicate=0
latest_lag가 수집 주기 대비 과도하지 않음
```

---

### Phase 2 — 아침 후보군 생성/압축 강화

목표:

```text
아침 브리핑 결과를 오늘 감시할 종목 5~10개로 압축한다.
```

필요 산출물:

| 필드 | 설명 |
|---|---|
| stock_code | 종목 코드 |
| candidate_score | 아침 기준 후보 점수 |
| morning_reason | 뉴스/지표/수급 등 선정 이유 |
| entry_scenario | 오늘 진입 시나리오 |
| invalidation_condition | 진입하면 안 되는 조건 |
| watch_priority | 장중 감시 우선순위 |

---

### Phase 2.5 — 장중 타이밍 알림 레이어

신규 추가가 필요한 핵심 단계다.

목표:

```text
today_watchlist를 대상으로 OR10/OR30/거래량/돌파 조건을 감시하고, 조건 충족 시 즉시 알림을 보낸다.
```

초기 상태는 alert-only가 적절하다.

```text
주문 실행 없음
paper 후보 생성 가능
real order blocked
```

알림 예시:

```text
[OR10 진입 후보]
종목: 005930
현재가: 73,200
OR10 상단: 72,900
돌파율: +0.41%
거래량: 최근 평균 대비 2.3x
점수: 74
차단 조건: 없음
제안: paper 승인 대기
```

---

### Phase 3 — 백테스트 준비도 게이트

상태: **blocked 정상**

현재 확인값:

```text
rows_used=43
min_rows_required=300
total_variant_trades=0
min_trades_required=5
```

판단:

> 데이터가 부족하므로 백테스트가 blocked인 것이 정상이다. 이 상태에서 paper/real 주문으로 넘어가면 안 된다.

---

### Phase 4 — daily feedback report 강화

현재 반영됨:

```text
snapshot_1m_accumulation 포함
```

추가로 강화해야 할 항목:

- 오늘 watchlist 대비 실제 타이밍 발생 여부
- 알림 발생 종목
- 알림 미발생이었지만 상승한 종목
- 알림이 늦었는지 여부
- 승인/거절/paper 결과
- 실패 원인 분류

---

### Phase 4.5 — 전략 수정 후보 리포트

신규 추가가 필요한 단계다.

목표:

```text
하루 또는 주간 분석 결과를 바탕으로 전략 수정 후보를 만든다.
```

수정 후보 예시:

| 관찰 결과 | 수정 후보 |
|---|---|
| BUY 후보가 계속 0개 | 후보 압축 기준/점수 임계값 검토 |
| 신호가 너무 늦음 | OR10 조건 또는 알림 주기 조정 |
| 돌파 후 자주 실패 | false breakout 필터 추가 |
| 거래 수가 너무 적음 | 임계값 과도 보수 여부 검토 |
| 손실 변동성이 큼 | 손절/포지션 크기 조정 |
| 특정 테마만 성과 좋음 | morning briefing 테마 가중치 조정 |

중요 원칙:

```text
수정 후보와 실제 전략 반영은 분리한다.
```

---

### Phase 5 — Leader 승인형 paper 주문

목표:

```text
장중 타이밍 알림이 발생하면 Leader가 요약/리스크 체크 후 사용자 승인형 paper 주문을 제안한다.
```

진행 조건:

- today_watchlist 존재
- 장중 타이밍 조건 충족
- 데이터 품질 정상
- 리스크 차단 없음
- 사용자 승인
- paper-only

---

### Phase 6 — Real 주문 검토

현 상태: **진행 금지**

필수 조건:

```text
충분한 snapshot_1m 누적
백테스트 통과
paper 검증 통과
리스크 한도 명확화
사용자 명시 승인
```

---

## 7. 전략 수정 원칙

전략은 분석에 의해 수정되어야 하지만, 즉흥적으로 수정하면 안 된다.

### 7.1 수정 가능한 영역

| 영역 | 수정 예시 |
|---|---|
| 후보 선정 | 뉴스/거래대금/전일 신호 가중치 조정 |
| 진입 타이밍 | OR10/OR30, 거래량 급증, 시초가 회복 조건 조정 |
| 차단 조건 | 갭 과대, 과열, 데이터 지연, 거래량 부족 차단 |
| 점수/가중치 | 가격/수급/패턴/밸류/리스크 비중 조정 |
| 주문/리스크 | 종목당 예산, 손절/익절, 총 노출 한도 |
| 알림/승인 | WATCH/ENTRY 알림 분리, 알림 임계값 조정 |

### 7.2 전략 수정 절차

```text
1. daily/weekly report에서 반복 패턴 확인
2. strategy_change_candidate 작성
3. 백테스트 또는 paper 검증
4. 결과 보고
5. 사용자 승인
6. strategy_registry와 code 반영
```

### 7.3 금지 사항

```text
하루 결과만 보고 즉시 전략 변경 금지
백테스트 없이 임계값/가중치 변경 금지
실주문 로직 직접 변경 금지
sample/mock 데이터로 전략 통과 처리 금지
```

---

## 8. 시간대별 목표 운영안

| 시간 | 레이어 | 목표 | 산출물 |
|---|---|---|---|
| 06:50 | Monitoring | 시스템/API/env 확인 | health status |
| 07:00 | Research | 뉴스/공시/시장 브리핑 | morning briefing |
| 07:30 | Research | 전일 데이터 기반 신호 | daily signals |
| 08:30 | Monitoring | 계좌/리스크 확인 | risk status |
| 08:45 | Leader | 후보 5~10개 압축 | today_watchlist |
| 09:00 | Monitoring | 장 시작 관찰 | no blind buy guard |
| 09:10 | Monitoring/Leader | OR10 감시 | timing alert |
| 09:30 | Monitoring/Leader | OR30 감시 | timing alert |
| 10:00~14:30 | Monitoring | 포지션/놓친 타이밍/리스크 감시 | intraday event log |
| 15:00 | Leader/Monitoring | 종가 전 위험 점검 | close/risk review |
| 16:10 | Daily Review | 손익/신호/실패/데이터 품질 분석 | daily feedback report |
| 20:00+ | Strategy Review | 전략 수정 후보 검토 | strategy_change_candidate |

---

## 9. 우선순위 실행 과제

### 1순위 — today_watchlist 구조화

아침 브리핑과 후보 압축 결과를 장중 감시 대상으로 명확히 넘겨야 한다.

필요 작업:

```text
candidate_compression_layer 결과를 today_watchlist 형태로 표준화
today_watchlist 저장 위치/스키마 결정
각 후보별 entry_scenario와 invalidation_condition 포함
```

---

### 2순위 — intraday_timing_alert 설계

OR10/OR30이 단순 분석이 아니라 타이밍 알림으로 작동해야 한다.

필요 작업:

```text
snapshot_1m 기반 OR10/OR30 계산
거래량 급증/돌파율/데이터 lag 검사
알림 JSON envelope 정의
Telegram/WebUI 알림 포맷 정의
```

---

### 3순위 — missed_timing 기록

매매 타이밍을 놓치는 문제를 개선하려면 놓친 사건을 기록해야 한다.

필요 작업:

```text
알림 발생 여부
알림 시각
후속 가격 움직임
승인/거절 여부
진입 못 한 이유
```

---

### 4순위 — strategy_change_candidate 리포트

장후 report에서 바로 전략 변경하지 말고, 수정 후보로 분리한다.

필요 작업:

```text
daily_pnl_feedback_report에 strategy_change_candidates 섹션 추가
반복 발생한 문제만 주간 전략 리뷰 대상으로 승격
```

---

### 5순위 — Leader 승인형 paper 주문

타이밍 알림이 충분히 안정화된 뒤 paper-only 승인 흐름을 붙인다.

필요 작업:

```text
승인 카드 포맷 정의
paper order 기록 스크립트 검증
real order와 코드/스케줄 분리
```

---

## 10. 최종 판단

현재까지의 전환은 다음 측면에서 적절하다.

```text
데이터 오염 제거: 적절
수집 안정화: 적절
주문 차단: 적절
n8n 의존도 축소: 적절
daily report 데이터 품질 반영: 적절
```

그러나 사용자 목표에 완전히 맞추려면 다음 보완이 필요하다.

```text
아침 후보가 장중 감시로 이어져야 한다.
장중 타이밍을 놓치지 않도록 alert layer가 필요하다.
daily report는 전략 수정 후보를 만들어야 한다.
전략 변경은 분석 → 후보 → 검증 → 승인 → 반영 순서로 해야 한다.
```

따라서 다음 큰 방향은 다음과 같이 확정하는 것이 좋다.

```text
1. snapshot_1m 수집 안정화는 계속 유지한다.
2. morning briefing을 today_watchlist로 연결한다.
3. today_watchlist를 장중 OR10/OR30 타이밍 감시 대상으로 사용한다.
4. 타이밍 발생 시 alert-only 또는 paper-ready 후보로 알린다.
5. 장후에는 놓친 타이밍/실행 결과/실패 원인을 분석한다.
6. 분석 결과는 strategy_change_candidate로 남기고, 검증된 것만 전략에 반영한다.
7. real 주문은 paper 검증 이후 별도 승인 전까지 열지 않는다.
```

---

## 11. 보고서 기준 다음 액션

다음 구현 단계는 **Phase 2.5 — today_watchlist + intraday_timing_alert 설계**로 잡는 것이 타당하다.

구체적 산출물:

1. `today_watchlist` JSON/schema 설계
2. OR10/OR30 timing alert JSON envelope 설계
3. Telegram/WebUI 알림 메시지 템플릿 작성
4. daily report에 `missed_timing_events`와 `strategy_change_candidates` 추가
5. paper/real 주문은 계속 차단 유지

이 순서가 사용자 목표인 **분석 기반 전략 수정 + 장중 타이밍 포착 + 승인형 실행**에 가장 가깝다.
