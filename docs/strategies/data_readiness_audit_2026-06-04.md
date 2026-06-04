# 데이터 준비도 감사 — 2026-06-04

상태: read-only 감사 완료  
작업 공간: `/home/june/trading`  
주문 영향: 없음. 주문 API 미호출.

## 1. snapshot_1m 복구 결과

`snapshot_1m` stale 원인은 수집 API/DB 장애가 아니라 **정기 수집 스케줄 부재**였다.

조치:
- `/home/june/.hermes/scripts/trading_snapshot_collector.sh` 추가
- `~/.config/systemd/user/trading-snapshot-collector.service` 추가
- `~/.config/systemd/user/trading-snapshot-collector.timer` 추가
- KST 장중 월~금 09:00~15:00, 5분 간격 실행
- `scripts/collect_current_session_snapshots.py`에서 ka10006 조회 실패를 유발하는 비숫자 코드 후보를 건너뛰도록 필터 추가

검증:
- timer enabled/active
- 01:20 UTC 자동 tick 성공
- snapshot rows: 24
- active_codes: 8
- latest_timestamp: `2026-06-04T01:20:00+00:00`
- latest_lag_minutes: 약 0.68~1.39분
- duplicate_stock_timestamp_keys: 0
- quality_error_counts: `{}`
- 대시보드 chartMeta: `state=live`

## 2. 주요 데이터 보유량

| 데이터 | 테이블/필터 | rows | 기간 | 코드/표본 상태 |
|---|---|---:|---|---|
| ka10080 1분봉 | `intraday_prices`, `source=kiwoom_ka10080_minute`, `time_frame=1min` | 40,200 | 2026-05-15 ~ 2026-05-29 | 최근 sample 기준 28 codes |
| ka10006 snapshot_1m | `intraday_prices`, `source=kiwoom_ka10006_snapshot`, `time_frame=snapshot_1m` | 1,927 | 2026-05-29 ~ 2026-06-04 | 13 codes |
| signal_events | `signal_events` | 76 | 2026-05-28 ~ 2026-05-29 | 50 codes, 5 event types |
| trading_signals | `trading_signals` | 130 | 2026-05-28 ~ 2026-06-01 | 86 codes, BUY/HOLD/SELL |
| daily_prices | `daily_prices` | 50,213 | 2023-12-06 ~ 2026-06-02 | 최근 sample 기준 96 codes |

## 3. Backtest readiness 현재 결과

`python3 scripts/check_backtest_readiness.py --pretty` 기준:

- 상태: `blocked`
- snapshot quality: OK
- snapshot lag: OK
- snapshot volume: 미달
- backtest rows: OK
- backtest trades: OK
- backtest performance: 실패

주요 수치:
- backtest rows_used: 11,454
- raw_rows_before_eligibility_filter: 15,000
- total_variant_trades: 32
- opening_10m avg_return_pct: -1.0765
- opening_30m avg_return_pct: -1.2741

현재 blocking_conditions:
- `snapshot_rows_below_300`
- `snapshot_active_codes_below_10`
- `backtest_avg_return_not_positive`

## 4. 핵심 발견: OR 백테스트의 장초반 분봉 누락

readiness 결과에서 일부 종목-일자의 09:00~09:30 opening_required_minutes가 누락되어 eligibility에서 제외되고 있다.

예시:
- 000660 / 2026-05-15: rows 300, missing_opening_minutes 31
- 000660 / 2026-05-18: rows 136, missing_opening_minutes 31
- 005930 / 2026-05-15: rows 300, missing_opening_minutes 31
- 035420 / 2026-05-27: rows 139, missing_opening_minutes 31

해석:
- 데이터 row 수 자체는 일부 충분하지만 OR 전략에 필요한 09:00~09:30 구간이 빠져 있다.
- 다음 우선순위는 `collect_intraday_90d`/ka10080 수집 로직이 장초반 데이터를 누락하는 이유를 추적하는 것이다.

## 5. 다음 조치

1. `collect_intraday_90d` 및 ka10080 수집 스크립트의 요청 파라미터/시간 변환 확인
2. 누락 종목-일자에 대해 ka10080 재조회가 장초반 09:00~09:30을 반환하는지 수동 검증
3. 재조회 가능하면 targeted backfill 스크립트 작성
4. backtest readiness 재실행
5. 성과가 여전히 음수이면 OR 진입/청산 rule 후보를 재검토

Paper/real 주문은 계속 blocked 상태로 유지한다.
