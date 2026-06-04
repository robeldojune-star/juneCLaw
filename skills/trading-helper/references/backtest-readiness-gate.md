# Backtest readiness gate (snapshot_1m)

목적: "수집은 정상인데 백테스트는 blocked" 상태를 빠르게 분리 진단한다.

## 1) 분리 관점

- **수집 품질**과 **백테스트 샘플량**은 별도 게이트다.
- 수집 품질이 정상이어도, 누적량/거래수 미달이면 백테스트는 계속 blocked가 정상이다.

## 2) 점검 스크립트

```bash
python3 scripts/check_backtest_readiness.py
```

출력 핵심:
- `summary.snapshot`
- `summary.backtest`
- `summary.readiness_gate`
- `blocking_conditions`

## 3) 해석 규칙

### A. snapshot_quality_ok=true, snapshot_lag_ok=true, snapshot_volume_ok=true
- 의미: 수집 파이프라인은 건강함.
- 다음 단계: 백테스트 게이트 확인.

### B. backtest_rows_ok=false
- 의미: `rows_used < min_rows_required`.
- 조치: 장중 snapshot_1m 누적 지속, 대상 종목 누적 편차 점검.

### C. backtest_trades_ok=false
- 의미: `total_variant_trades < min_trades_required`.
- 조치: 조건 과도 여부/종목 편차/평가 창(OR10/OR30) 적합성 점검.

## 4) 표준 차단 조건

- `backtest_rows_below_min_required`
- `backtest_trades_below_min_required`

(내부 stage에서 함께 관찰될 수 있는 값)
- `insufficient_intraday_rows_for_backtest`
- `insufficient_backtest_trade_count`

## 5) 운영 원칙

- 위 차단이 남아 있는 동안은 `alert_only`/`paper_only` 유지.
- 실주문 경로는 readiness gate 전체 통과 전까지 금지.
- 임계값 조정보다 데이터 누적/품질 확보를 우선한다.
