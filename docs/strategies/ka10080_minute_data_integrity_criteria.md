# ka10080 과거 1분봉 수집 무결성 판단 기준

상태: 운영 기준 초안  
작성 기준: 2026-05-29  
기준 workspace: `/home/june/trading`  
관련 데이터: `intraday_prices`, `source=kiwoom_ka10080_minute`, `time_frame=1min`

---

## 1. 결론

과거 1분봉 수집이 잘 되었는지는 숫자 검사만으로 부족하다. 다음 3단계를 모두 통과해야 한다.

```text
1. 구조 검사: source/time_frame/timestamp/OHLCV/중복
2. 시간축 검사: 날짜별 09:00~09:30 및 정규 체결 구간 coverage
3. 시각 검사: 캔들 차트 + minute coverage heatmap
```

현재 구현 파일:

```text
scripts/inspect_ka10080_minute_integrity.py
scripts/create_ka10080_minute_quality_chart.py
reports/ka10080_minute_quality_005930.html
```

---

## 2. Kiwoom 1분봉 운영 해석

Kiwoom HTS 차트에서 과거 1분봉이 보이는 것은 맞다. REST에서는 `ka10080 주식분봉차트조회요청`으로 조회한다.

```text
endpoint = /api/dostk/chart
api-id = ka10080
body.stk_cd = 종목코드
body.tic_scope = 1  # 1분봉
body.upd_stkpc_tp = 1
body.base_dt = 기준일자 YYYYMMDD
response list = stk_min_pole_chart_qry
minute timestamp = cntr_tm
```

운영 방식은 보통 다음과 같이 이해해야 한다.

```text
1. base_dt 기준으로 과거 방향의 분봉 묶음을 받는다.
2. 한 번 호출로 전체 90일이 아니라 일정 row 수가 내려온다.
3. 더 과거가 필요하면 연속조회 next-key 또는 base_dt를 과거로 이동하며 반복 조회한다.
4. 받은 데이터는 최신→과거 또는 과거→최신 순서가 혼재될 수 있으므로 timestamp 기준 정렬/중복 제거가 필수다.
5. HTS 차트는 내부적으로 이런 연속조회/캐시/차트 보정 처리를 사용자에게 숨긴다.
```

즉, 우리도 HTS처럼 보려면 단발 조회가 아니라 **연속조회 + 날짜별 coverage 검증**을 해야 한다.

---

## 3. 반드시 확인해야 하는 품질 기준

### 3.1 구조 기준

| 기준 | 통과 조건 |
|---|---|
| source | `kiwoom_ka10080_minute` |
| time_frame | `1min` |
| timestamp | KST 기준 분 단위로 해석 가능 |
| OHLC | `high >= open/close`, `low <= open/close`, 모두 양수 |
| volume | 음수 아님 |
| 중복 | `(stock_code, timestamp)` 중복 0 |
| 외부 row | 예상 세션 밖 timestamp는 별도 집계 |

### 3.2 시간축 기준

OR10/OR30 전략에서는 전체 장보다 **장초반 coverage**가 가장 중요하다.

| 구간 | 중요도 | 기준 |
|---|---:|---|
| 09:00~09:10 | 매우 높음 | OR10 계산에 필수 |
| 09:00~09:30 | 매우 높음 | OR30 계산에 필수 |
| 09:31~15:20 | 중간 | 이후 돌파/청산 검증에 필요 |
| 15:21~15:29 | 낮음/특수 | 장마감 동시호가 구간. 1분 체결봉이 없을 수 있음 |
| 15:30 | 높음 | 종가/동시호가 체결 기준 |
| 15:31~15:35 | 별도 | Kiwoom 차트 특성상 after/closing row로 들어올 수 있음 |

따라서 일반적인 expected regular definition은 다음으로 둔다.

```text
09:00~15:20 + 15:30
```

`15:21~15:29`가 비었다고 곧바로 오류로 보지 않는다.

### 3.3 OR 전략용 최소 통과 기준

종목×날짜 단위로:

```text
opening_09_00_09_30_complete = true
regular_unique_minutes >= 300
duplicate_regular_minutes = 0
quality_error_counts = {}
```

백테스트 전체 기준:

```text
rows_used >= 300
trades >= 5
avg_return_pct > 0
```

단, 이 기준은 최소 안전 게이트다. paper 전환은 별도의 성과/리스크 조건이 필요하다.

---

## 4. 현재 저장 데이터 점검 결과

실행:

```bash
python3 scripts/inspect_ka10080_minute_integrity.py
```

요약:

```text
rows = 15000
stock_rows = 각 3000 rows × 5종목
stock_day_count = 50
duplicate_stock_timestamp_keys = 0
quality_error_counts = {}
outside_regular_rows = 0
closing_call_auction_gap_rows = 0
closing_or_after_session_rows = 45
```

즉, 구조상 가격/중복 오류는 없다.

다만 alerts가 존재한다.

```text
alerts_count = 60
```

주된 원인:

```text
일부 날짜가 10:22 또는 13:05/13:06부터 시작해 09:00~09:30이 비어 있음.
```

대표 예:

```text
005930_2026-05-18_opening_09_00_09_30_missing:31
005930_2026-05-21_opening_09_00_09_30_missing:31
005930_2026-05-27_opening_09_00_09_30_missing:31
```

해석:

```text
이번 수집은 max_requests_per_stock=4, max_rows_per_stock=3000 제한으로 인해 전체 날짜가 완전하지 않다.
ka10080 데이터가 잘못된 것이 아니라, backfill 깊이가 아직 부족하다.
```

---

## 5. 시각 검증

대표 종목 삼성전자 차트 파일:

```text
reports/ka10080_minute_quality_005930.html
```

WebUI에서 보기:

```text
MEDIA:/home/june/trading/reports/ka10080_minute_quality_005930.html
```

차트 구성:

```text
1. 캔들 + 거래량
2. 날짜×분 coverage heatmap
3. 날짜별 rows/regular minutes 요약 카드
```

판단법:

```text
캔들 차트: 가격 급점프/비정상 긴 공백/거래량 이상 확인
heatmap: 09:00~09:30이 빨간색이면 OR10/OR30 백테스트에 부적합
날짜 카드: regular_minutes가 너무 낮으면 partial day로 분류
```

---

## 6. 운영 개선 방향

현재 필요한 개선은 다음이다.

```text
1. ka10080 연속조회 next-key 지원 여부 확인
2. next-key가 없다면 base_dt를 더 촘촘히 이동하면서 backfill
3. 종목×날짜별 opening coverage가 완전한 날짜만 백테스트에 사용
4. partial day는 DB에는 저장하되 backtest eligibility에서 제외
5. chart QA를 종목별로 자동 생성
```

백테스트 입력 조건은 다음처럼 바꾸는 것이 좋다.

```text
eligible trading day =
  source == kiwoom_ka10080_minute
  time_frame == 1min
  09:00~09:30 all present
  duplicate_regular_minutes == 0
  OHLC quality errors == 0
```

---

## 7. 권장 다음 명령

숫자 점검:

```bash
python3 scripts/inspect_ka10080_minute_integrity.py
```

차트 생성:

```bash
python3 scripts/create_ka10080_minute_quality_chart.py \
  --stock-code 005930 \
  --limit 3000 \
  --out reports/ka10080_minute_quality_005930.html
```

백테스트 전 조건:

```text
alerts 중 opening_09_00_09_30_missing이 있는 날짜는 OR10/OR30 백테스트에서 제외하거나 재수집한다.
```
