# today_watchlist + intraday_timing_alert 설계 v1

작성 기준: 2026-05-29  
대상 workspace: `/home/june/trading`  
상위 보고서: `docs/strategies/trading_workflow_direction_review_2026-05-29.md`  
목적: 아침 브리핑/후보 압축 결과가 장중 매매 타이밍 포착과 승인형 paper 실행 후보로 이어지도록 표준 데이터 구조와 운영 흐름을 정의한다.

---

## 1. 배경

현재 운영은 `ka10006 snapshot_1m` 수집 안정화와 무결성 검증이 중심이다. 이 기반은 유지해야 하지만, 사용자 목표는 단순 분석 보고서가 아니라 다음 흐름이다.

```text
아침 분석
→ 오늘 후보 확정
→ 장중 타이밍 감시
→ 즉시 알림
→ Leader 승인형 paper 후보
→ 장후 복기
→ 전략 수정 후보 도출
```

따라서 기존 `candidate_compression_layer`와 `opening_10m/30m` 후보 루프 사이에 명시적인 `today_watchlist`와 `intraday_timing_alert` 레이어를 둔다.

---

## 2. 핵심 원칙

```text
1. 실제 Kiwoom/Supabase 데이터만 사용한다.
2. ka10005는 분봉 소스로 사용하지 않는다.
3. 장중 타이밍 감시는 snapshot_1m만 사용한다.
4. 초기 구현은 alert-only 또는 paper-ready candidate까지만 허용한다.
5. real 주문은 백테스트 + paper 검증 + 사용자 명시 승인 전까지 금지한다.
6. 전략 수정은 daily/weekly 분석 결과에 의해 후보화하고, 검증 전 code/threshold에 반영하지 않는다.
```

---

## 3. 전체 데이터 흐름

```text
07:00 news_briefing_growth_analysis
  → 시장/뉴스/공시/테마 요약

07:30 stock_morning_signals
  → 전일 데이터 기반 BUY/WATCH/HOLD 후보 생성

08:45 candidate_compression_layer
  → TOP 5~10 today_watchlist 생성

09:05~15:30 collect_current_session_snapshots
  → ka10006 snapshot_1m 누적

09:10 opening_10m_aggressive_layer
09:30 opening_30m_standard_layer
  → today_watchlist 대상 OR10/OR30 timing alert 평가

장중 Monitoring
  → alert 발생, missed timing 후보 기록

16:10 daily_pnl_feedback_report
  → 수집 상태 + 알림/미실행/놓친 타이밍 + 전략 수정 후보
```

---

## 4. today_watchlist 표준 구조

`today_watchlist`는 장 시작 전에 확정되는 **오늘 집중 감시 종목 목록**이다. 현재 `candidate_compression_layer`의 `candidates`를 확장해 생성한다.

### 4.1 Envelope

```json
{
  "ok": true,
  "workflow": "daily_trading_workflow_v1",
  "stage": "today_watchlist",
  "status": "completed",
  "generated_at": "2026-05-29T08:45:00+09:00",
  "trading_date": "2026-05-29",
  "summary": {
    "candidate_count": 7,
    "source_stages": ["news_briefing_growth_analysis", "stock_morning_signals", "candidate_compression_layer"],
    "order_execution_enabled": false,
    "paper_candidate_enabled": false
  },
  "watchlist": [],
  "blocking_conditions": [],
  "alerts": [],
  "next_actions": []
}
```

### 4.2 Watchlist item

```json
{
  "stock_code": "005930",
  "stock_name": "삼성전자",
  "sector": "반도체",
  "watch_priority": 1,
  "candidate_score": 74.5,
  "signal_type": "BUY",
  "strategy": "opening_multi_factor_v1",
  "morning_reason": [
    "전일 daily signal BUY",
    "반도체 업종 강세",
    "거래대금 상위권"
  ],
  "score_details": {
    "daily_signal_score": 68.0,
    "news_theme_score": 12.0,
    "liquidity_score": 8.0,
    "risk_penalty": -3.5
  },
  "entry_scenarios": [
    {
      "scenario_id": "or10_breakout",
      "label": "OR10 상단 돌파",
      "time_window": "09:10~10:00",
      "required_conditions": [
        "current_price > or10_high",
        "volume_ratio >= 1.5",
        "snapshot_lag_minutes <= 10"
      ],
      "invalidation_conditions": [
        "gap_up_too_large",
        "snapshot_1m_quality_error",
        "market_wide_risk_on"
      ]
    }
  ],
  "risk_controls": {
    "max_position_krw": 300000,
    "stop_loss_pct": -0.9,
    "take_profit_pct_1": 1.0,
    "take_profit_pct_2": 2.0,
    "real_order_allowed": false,
    "paper_order_allowed": false
  },
  "blocking_conditions": []
}
```

---

## 5. intraday_timing_alert 표준 구조

`intraday_timing_alert`는 장중 snapshot_1m 기반 조건이 충족되었을 때 발생하는 이벤트다. 초기에는 주문을 실행하지 않고 Telegram/WebUI 알림 또는 paper-ready 후보까지만 만든다.

### 5.1 Envelope

```json
{
  "ok": true,
  "workflow": "daily_trading_workflow_v1",
  "stage": "intraday_timing_alert",
  "status": "completed",
  "generated_at": "2026-05-29T09:12:00+09:00",
  "trading_date": "2026-05-29",
  "summary": {
    "window_minutes": 10,
    "watchlist_count": 7,
    "evaluated_count": 7,
    "alert_count": 1,
    "paper_candidate_count": 0,
    "order_execution_enabled": false
  },
  "alerts": [],
  "timing_events": [],
  "blocking_conditions": [],
  "next_actions": []
}
```

### 5.2 Timing event

```json
{
  "event_id": "20260529T091200_005930_or10_breakout",
  "stock_code": "005930",
  "stock_name": "삼성전자",
  "scenario_id": "or10_breakout",
  "window_minutes": 10,
  "event_type": "ENTRY_TIMING_CANDIDATE",
  "signal_type": "WATCH",
  "confidence_score": 72.0,
  "current_snapshot": {
    "timestamp": "2026-05-29T09:12:00+09:00",
    "current_price": 73200,
    "open": 72400,
    "high": 73300,
    "low": 72100,
    "close": 73200,
    "volume": 1234567,
    "snapshot_lag_minutes": 2.0
  },
  "opening_range": {
    "or_high": 72900,
    "or_low": 72100,
    "breakout_pct": 0.4115
  },
  "volume_context": {
    "volume_ratio": 2.3,
    "volume_reference": "recent_snapshot_average"
  },
  "score_details": {
    "watchlist_score": 74.5,
    "breakout_score": 20.0,
    "volume_score": 15.0,
    "risk_penalty": -5.0
  },
  "risk_controls": {
    "suggested_mode": "alert_only",
    "paper_order_allowed": false,
    "real_order_allowed": false,
    "suggested_budget_krw": 0,
    "stop_loss_pct": -0.9,
    "take_profit_pct_1": 1.0,
    "take_profit_pct_2": 2.0
  },
  "blocking_conditions": [
    "snapshot_1m_accumulation_and_backtest_required"
  ],
  "message": "005930 OR10 상단 돌파 후보. 현재는 alert-only; paper/real 주문 금지."
}
```

---

## 6. 알림 단계 구분

장중 이벤트는 바로 BUY가 아니다. 다음 단계로 구분한다.

| 단계 | 의미 | 주문 가능 여부 |
|---|---|---:|
| `WATCH` | 조건 일부 충족, 관찰 필요 | 불가 |
| `ENTRY_TIMING_CANDIDATE` | 진입 후보 조건 충족 | 초기에는 불가 |
| `PAPER_READY` | paper 검증 기준 통과 + 사용자 승인 대기 | paper만 가능 |
| `REAL_READY` | paper 검증 이후 별도 승인 통과 | 별도 승인 전 불가 |

초기 구현 기본값:

```text
signal_type = WATCH 또는 ENTRY_TIMING_CANDIDATE
paper_order_allowed = false
real_order_allowed = false
```

---

## 7. Telegram/WebUI 알림 템플릿

장중 알림은 길면 안 된다. 빠른 판단이 가능해야 한다.

```text
[장중 타이밍 후보: OR10]
종목: 005930 삼성전자
현재가: 73,200
OR10 상단: 72,900 / 돌파율: +0.41%
거래량: 2.3x
점수: 72.0
차단: snapshot_1m_accumulation_and_backtest_required
모드: alert-only

다음: 관찰 유지. paper/real 주문 금지.
```

paper 단계가 열린 뒤에는 다음 필드를 추가한다.

```text
제안 금액: 300,000원
손절: -0.9%
익절: +1.0% / +2.0%
승인: [승인] [거절] [관망]
```

---

## 8. missed_timing_event 구조

전략 개선을 위해 놓친 타이밍을 기록한다.

```json
{
  "event_id": "20260529_005930_missed_or10",
  "stock_code": "005930",
  "scenario_id": "or10_breakout",
  "missed_type": "late_alert",
  "expected_alert_time": "2026-05-29T09:12:00+09:00",
  "actual_alert_time": null,
  "price_at_expected_time": 73200,
  "price_after_30m": 74800,
  "estimated_missed_return_pct": 2.1858,
  "root_cause_candidates": [
    "snapshot_lag_too_high",
    "watchlist_missing",
    "alert_threshold_too_strict"
  ],
  "strategy_change_candidate": "OR10 volume threshold or alert schedule review"
}
```

---

## 9. strategy_change_candidate 구조

daily/weekly review에서 전략 수정 후보를 만든다.

```json
{
  "candidate_id": "20260529_or10_alert_late_review",
  "source": "daily_pnl_feedback_report",
  "strategy_id": "opening_multi_factor_v1",
  "problem_observed": "OR10 돌파 이후 알림이 늦어 진입 타이밍을 놓침",
  "evidence": {
    "missed_event_count": 3,
    "avg_missed_return_pct": 1.4,
    "affected_scenarios": ["or10_breakout"]
  },
  "proposed_change": {
    "change_type": "alert_rule_adjustment",
    "field": "volume_ratio_threshold",
    "current_value": 1.8,
    "proposed_value": 1.5
  },
  "validation_required": [
    "snapshot_1m backtest",
    "paper-only forward test"
  ],
  "status": "candidate_only",
  "approved_for_code_change": false
}
```

원칙:

```text
strategy_change_candidate는 전략 변경 제안이지, 즉시 반영 지시가 아니다.
```

---

## 10. 구현 순서

### Step 1 — schema/documentation

- `today_watchlist` schema 확정
- `intraday_timing_alert` schema 확정
- 알림 템플릿 확정

### Step 2 — candidate_compression_layer 확장

- 현재 `candidates`에 `entry_scenarios`, `risk_controls`, `watch_priority`, `morning_reason` 추가
- output stage는 기존 호환성을 위해 `candidate_compression_layer` 유지 가능
- 별도 `today_watchlist` stage 추가 가능

### Step 3 — intraday alert script 추가

예상 파일:

```text
scripts/run_intraday_timing_alerts.py
```

역할:

```text
candidate_compression_layer 실행 또는 저장된 today_watchlist 조회
snapshot_1m 최근 rows 조회
OR10/OR30 high/low 계산
alert 조건 평가
JSON 출력
주문 실행 없음
```

### Step 4 — daily report 확장

`daily_pnl_feedback_report`에 다음 섹션 추가:

```text
intraday_timing_alert_summary
missed_timing_events
strategy_change_candidates
```

### Step 5 — Leader approval paper-only

타이밍 알림이 안정화된 뒤 별도 구현한다.

---

## 11. 초기 blocking conditions

초기 단계에서는 다음 blocker를 유지한다.

```text
snapshot_1m_accumulation_and_backtest_required
pattern_model_not_ready_for_auto_order
paper_order_workflow_not_validated
real_order_disabled_until_user_approval
```

`intraday_timing_alert`는 blocker가 있어도 **알림은 낼 수 있다.**  
단, blocker가 있으면 주문 가능 상태로 해석하면 안 된다.

---

## 12. 완료 기준

Phase 2.5의 1차 완료 기준:

```text
1. today_watchlist schema 문서화 완료
2. intraday_timing_alert schema 문서화 완료
3. JSON schema 파일 유효성 통과
4. current_trading_execution_plan에 Phase 2.5/4.5 반영
5. 다음 구현 대상 스크립트가 명확함: scripts/run_intraday_timing_alerts.py
```
