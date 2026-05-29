# 백테스트 준비 실행계획 (snapshot_1m 기준)

작성일: 2026-05-29  
기준 workspace: `/home/june/trading`

## 1) 목표

`opening_multi_factor_v1` 백테스트를 **실행 가능한 상태**로 만들고, 결과가 전략 수정으로 이어지도록 운영 루프를 고정한다.

---

## 2) 현재 상태 요약

- 데이터 소스: `ka10006 -> intraday_prices(time_frame=snapshot_1m, source=kiwoom_ka10006_snapshot)`
- 장중 수집: Hermes cron watchdog 정상 동작
- 백테스트 stage: 실행은 되지만 아래로 blocked
  - `insufficient_intraday_rows_for_backtest`
  - `insufficient_backtest_trade_count`
- 구조적 가드: 자동주문 차단 유지(`pattern_model_not_ready_for_auto_order` 등)

---

## 3) 백테스트 진입 게이트 (통과 조건)

아래를 모두 통과해야 "백테스트 준비 완료"로 본다.

1. **수집 품질 게이트**
   - `latest_lag_minutes <= 10`
   - `quality_error_counts == {}`
   - `duplicate_stock_timestamp_keys == 0`

2. **누적량 게이트**
   - `rows_used >= 300` (현재 backtest_opening_strategy 기준)
   - watchlist 핵심 종목(최소 10종목)에서 OR10/OR30 계산 가능한 row 확보

3. **샘플 거래 게이트**
   - `total_variant_trades >= 5`
   - 한 종목 편중이 과도하지 않을 것(리포트로 확인)

4. **안전 게이트**
   - 주문 경로는 계속 `alert_only`/`paper_only`
   - 실주문은 백테스트 + paper 검증 통과 전 금지

---

## 4) 실행 순서 (운영)

### Phase A. 데이터 누적 안정화

- 장중 `collect_current_session_snapshots` 반복 유지
- Hermes cron `trading-snapshot-1m-collector-no-n8n`가 5분마다 수집 + 품질검사 수행
- 장후 15:45 Hermes cron `trading-backtest-readiness-daily-report`가 readiness progress를 보고
- 부족 종목(행 수 낮은 종목) 발생 시 watchlist 고정 정책 점검

### Phase B. 백테스트 준비도 점검

- `scripts/check_backtest_readiness.py` 실행
- 출력:
  - snapshot 품질 상태
  - backtest stage 상태
  - 부족 게이트 목록
  - 다음 액션

### Phase C. 백테스트 실행/해석

- `run_daily_workflow_stage.py --stage backtest_opening_strategy_90d`
- blocked 해제 시:
  - 10분/30분 variant별 거래수·승률·평균수익·MDD 기록
  - 종목별 편중/누락 케이스 분리

### Phase D. 전략 수정 후보 생성

- 백테스트 결과를 즉시 코드 변경으로 반영하지 않고,
- `strategy_change_candidate` 형태로 문서화 후 검토
  - 임계치 문제인지
  - 패턴 점수 문제인지
  - 데이터 누락 문제인지 분리

---

## 5) 전략 수립 방향 (현재 권장)

1. **진입 판단은 2층 구조 유지**
   - 1층: 아침 후보 압축(`candidate_compression_layer`)
   - 2층: 장중 OR10/OR30 timing

2. **점수/임계치 조정보다 데이터 성숙 우선**
   - 현재는 row 부족과 패턴 미준비가 핵심 제약
   - 임계치 조정은 백테스트 분포 확인 후 검토

3. **패턴 미준비 상태 명시 유지**
   - `pattern_model_not_ready`를 해제하기 전까지는 BUY 전환 금지

4. **일일 피드백 루프 고정**
   - 장후 리포트에 반드시 포함:
     - rows/active_codes/lag/quality
     - OR10/OR30 미충족 종목
     - no-trade 원인 분류

---

## 6) 오늘 기준 즉시 액션

1. 장중 누적 유지 (cron 정상 감시)
2. 마감 전 `check_backtest_readiness.py` 1회 실행
3. 장후 `backtest_opening_strategy_90d` 재실행
4. 결과를 다음 문서에 반영
   - `docs/strategies/current_trading_execution_plan.md`
   - 전략 수정 후보 문서(신규)

---

## 7) 금지/주의

- `ka10005`를 분봉으로 재도입 금지
- 가짜/샘플 OHLCV로 백테스트 금지
- blocked 상태를 무시하고 주문 단계로 진행 금지
- 임계치/가중치 즉시 변경 금지 (결과 근거 없이 수정 금지)
