# 투자 전략 등록 v1 — 장초반 변동성·수급·90일 패턴 + 후지모토 시게루 관심 전략

작성 목적: 사용자가 준비한 Word 전략보고서를 바탕으로, 향후 Research AI/Monitoring AI/Leader AI 및 운영 워크플로우에 연결할 **투자 전략 등록 초안**을 만든다.  
작업 공간: `/home/june/trading`  
상태: 초안 / 구현 전 검토용. 현재 실행 기준은 `docs/strategies/current_trading_execution_plan.md`를 우선한다. n8n은 비활성 백업/승인 UI 후보이며, 장중 수집은 Hermes cron + trading-runner + ka10006 snapshot_1m 누적으로 수행한다.  

> 주의: 본 문서는 투자 자문이 아니라 시스템 설계·전략 구현을 위한 내부 등록 문서다. 실제 주문 전에는 반드시 실데이터 검증, 백테스트, 모의투자, 리스크 통제 검증이 필요하다.

---

## 1. 원본 자료 등록

`/home/june/trading`에 있는 Word 전략보고서 중 관련도가 높은 문서를 Markdown 참조본으로 추출했다.

| 구분 | 원본 Word | 추출 참조본 | 역할 |
|---|---|---|---|
| 핵심 전략보고서 | `export__1_.docx` | `docs/strategy_sources/export__1_.md` | 가격 변동성, 수급 상관관계, 90일 시계열 패턴을 종합한 매수 스코어링 시스템 |
| 진입 수치/실전 조건 | `export.docx` | `docs/strategy_sources/export.md` | 래리 윌리엄스 변동성 돌파, VPIN, 장초반 모멘텀, 거래량 급증 기준 |
| 공식/정교화 로직 | `export__2_.docx` | `docs/strategy_sources/export__2_.md` | 진입 가격 공식, VPIN 공식, 패턴 매칭 로직 |
| 90일 패턴/DTW | `export__3_.docx` | `docs/strategy_sources/export__3_.md` | Dynamic Time Warping 기반 시계열 유사도 분석 |
| 오프닝 레인지 | `export__5_.docx` | `docs/strategy_sources/export__5_.md` | 10분/30분 관찰 구간 비교, 장초반 진입 타이밍 |
| 후지모토 시게루 | 미확인 | 별도 리서치 필요 | 사용자 관심 전략. 현재 Word 문서에서는 키워드 직접 발견 안 됨 |

---

## 2. 전략군 개요

이번 등록 대상은 하나의 단일 전략이 아니라, 아래 4개 전략 모듈을 묶은 **복합 스코어링 전략군**으로 본다.

```text
S1. 장초반 가격 변동성 / 시가 대비 이격도
S2. 수급 상관관계 / 거래량-가격 변동 상관
S3. 90일 시계열 패턴 / 과거 유사 패턴 탐색
S4. 후지모토 시게루 매매법 / 별도 리서치 후 편입
```

초기 운영명:

```text
opening_multi_factor_v1
```

전략 목적:

```text
KOSPI/KOSPI200 주요 종목에서 장초반 당일 양봉 마감 가능성 또는 장중 추세 지속 가능성이 높은 종목을 선별한다.
```

---

## 3. S1 — 가격 변동성 / 장초반 시가 대비 이격도

### 3.1 핵심 아이디어

장 시작 직후에는 하루 변동폭의 큰 부분이 집중된다. 따라서 시가 대비 현재가 이격, 전일 변동폭, 오프닝 레인지 돌파 여부를 이용해 장초반 힘의 방향을 판단한다.

원본 문서 근거:

- 장 시작 직후 10분은 공격적 진입 구간
- 30분 관찰은 노이즈를 줄이는 보수적 진입 구간
- 래리 윌리엄스 변동성 돌파 공식 사용 가능

### 3.2 기본 공식 후보

#### 래리 윌리엄스 변동성 돌파

```text
entry_price = today_open + k * (yesterday_high - yesterday_low)
```

초기 k 후보:

```text
k = 0.25 ~ 0.50
```

#### 시가 대비 이격도

```text
open_gap_pct = (current_price - today_open) / today_open * 100
```

#### 오프닝 레인지 돌파

```text
opening_range_high = max(high during first N minutes)
opening_range_low  = min(low during first N minutes)

bullish_breakout = current_price > opening_range_high
bearish_breakdown = current_price < opening_range_low
```

N 후보:

```text
10분 = 공격형
30분 = 보수형
```

### 3.3 필요한 데이터

| 데이터 | 출처 | 현재 준비 상태 |
|---|---|---|
| 당일 시가 | ka10006 snapshot_1m 또는 검증된 intraday source | snapshot 누적으로 확인 |
| 현재가 | Kiwoom 현재가 API | core 확장 필요 |
| 전일 고가/저가 | `daily_prices` | 준비 가능 |
| 1분/5분 상당 장중 데이터 | ka10006 snapshot_1m 누적 또는 검증된 minute-history API | snapshot_1m 누적 진행 중 |
| 오프닝 고가/저가 | snapshot_1m 집계 | 누적 데이터 기반 구현 |

### 3.4 초기 점수화 후보

```text
volatility_score = 0~30점

+10: 현재가 > 변동성 돌파 entry_price
+8 : 시가 대비 이격도 양수이며 일정 임계값 이상
+7 : 10분 또는 30분 오프닝 레인지 상향 돌파
+5 : 돌파 후 재이탈 없음
```

---

## 4. S2 — 수급 상관관계 / 거래량과 가격 변동의 상관

### 4.1 핵심 아이디어

가격 상승이 거래량 증가를 동반하면 신호 신뢰도가 높다. 반대로 가격 상승이 거래량 없이 발생하면 가짜 돌파 가능성이 높다.

원본 문서 근거:

- VPIN은 정보성 거래 비중과 유동성 독성을 평가하는 지표
- 거래량 급증 조건은 진입 신뢰도를 높이는 필터
- 거래량 가중 bar 패턴과 주체별 매매 동향을 고려할 수 있음

### 4.2 기본 지표 후보

#### 거래량 급증률

```text
volume_spike_ratio = current_volume / average_volume_recent_bars
```

초기 후보:

```text
volume_spike_ratio >= 1.10
```

#### 가격-거래량 상관

```text
corr_price_volume = corr(price_return_series, volume_change_series)
```

#### VPIN 후보

```text
VPIN = sum(abs(sell_volume_bucket - buy_volume_bucket)) / (n * bucket_volume)
```

단, 실제 체결 방향 분류가 필요하므로 초기 구현에서는 단순 거래량/가격 상관을 먼저 쓰고, VPIN은 2차 구현으로 둔다.

### 4.3 필요한 데이터

| 데이터 | 출처 | 현재 준비 상태 |
|---|---|---|
| 장중 거래량 | ka10006 snapshot_1m 누적 | 누적 데이터 기반 구현 |
| 현재가 변화율 | ka10006 snapshot_1m | 누적 데이터 기반 구현 |
| 투자자별 매매동향 | Kiwoom/거래소 | 추가 조사 필요 |
| 체결강도/매수매도 잔량 | Kiwoom 실시간/호가 | 2차 구현 |

### 4.4 초기 점수화 후보

```text
flow_score = 0~30점

+10: 거래량 급증률 >= 1.10
+8 : 가격 상승률과 거래량 변화율의 상관이 양수
+7 : 상승 구간에서 거래량 증가, 하락 구간에서 거래량 감소
+5 : 직전 고점 돌파 시 거래량 동반
```

---

## 5. S3 — 90일 시계열 패턴 / 과거 데이터 기반 패턴 분석

### 5.1 핵심 아이디어

최근 장초반 가격·거래량 패턴을 과거 90일 유사 패턴과 비교하고, 유사한 과거 사례의 당일 종가 방향을 이용해 확률 점수를 만든다.

원본 문서 근거:

- 90일 이상 시계열 데이터 활용
- 캔들스틱 이미지/CNN 또는 SVM/유전 알고리즘 가능
- DTW는 시간축이 늘어나거나 줄어든 유사 패턴 탐지에 적합

### 5.2 초기 구현 후보

1차는 복잡한 CNN보다 DTW 또는 단순 정규화 거리 기반으로 시작한다.

```text
lookback_days = 90
pattern_window = first 10m or first 30m
features = [return, volume_ratio, high_low_range, open_gap]
```

유사도 계산:

```text
normalized_pattern = zscore(feature_series)
similarity = 1 / (1 + distance(current_pattern, historical_pattern))
```

향후 고도화:

```text
DTW distance
CNN candlestick image classifier
SVM + genetic algorithm
```

### 5.3 필요한 데이터

| 데이터 | 출처 | 현재 준비 상태 |
|---|---|---|
| 90일 일봉 | Kiwoom daily_prices | 일부 준비 가능 |
| 90일 장중 패턴 | ka10006 snapshot_1m 누적 또는 검증된 minute-history API | 충분한 누적 전 blocked |
| 당일 첫 10/30분 패턴 | snapshot_1m 집계 | 누적 데이터 기반 구현 |
| 과거 유사일의 종가 방향 | daily_prices | 준비 가능 |

### 5.4 초기 점수화 후보

```text
pattern_score = 0~25점

+10: 유사 과거 패턴의 양봉 마감 확률 높음
+7 : 유사 과거 패턴의 평균 수익률 양수
+5 : 유사 패턴 중 하락 리스크 낮음
+3 : 최근 90일 추세 필터 양호
```

---

## 6. S4 — 후지모토 시게루 매매법

### 6.1 현재 상태

사용자의 관심 전략으로 등록한다. `/home/june/trading`의 Word 파일들에서는 `후지모토`, `시게루`, `Fujimoto` 키워드가 직접 발견되지 않았으므로, 공개 웹 자료 기반 1차 리서치 노트를 별도 작성했다.

참조 문서:

```text
docs/strategies/fujimoto_shigeru_research_note.md
```

### 6.2 1차 리서치 요약

공개 자료에서 확인한 핵심 후보는 아래와 같다. 단, 2차 자료 기반이므로 구현 규칙으로 확정하지 않는다.

```text
- 펀더멘털 기반 종목 선정: 실적/재무가 양호한 기업 우선
- 기술적 타이밍: RSI 30 이하 매수 후보, RSI 70 이상 매도/익절 후보
- 단기 차트: 1분/5분 차트로 진입·청산 타이밍 확인
- 수급 확인: 거래량/거래대금으로 시장 관심도 확인
- 자금관리: 1:2:6 분할 진입 후보
```

### 6.3 등록 상태

```text
strategy_id: fujimoto_shigeru_v1_candidate
status: research_note_ready_not_implemented
integration: opening_multi_factor_v1 auxiliary filter candidate
```

### 6.4 편입 방식 후보

초기에는 독립 전략이 아니라 `opening_multi_factor_v1`의 보조 필터로 편입하는 방식을 우선 검토한다.

```text
A. 재무 필터: OpenDART 기반 실적/재무 건전성 통과
B. 타이밍 필터: RSI/분봉/오프닝 레인지 확인
C. 수급 필터: 거래량/거래대금 충분성 확인
D. 자금관리: 모의투자에서만 1:2:6 분할 진입 후보 테스트
```

### 6.5 추가 확인 필요

1. 사용자 제공 원문 또는 신뢰 가능한 일본어 원자료
2. 후지모토식 전략을 독립 전략으로 볼지, 장초반 전략의 보조 필터로 볼지
3. 1:2:6 분할 진입을 실제 order_candidate에 반영할지
4. RSI 30/70을 그대로 쓸지, 한국 주식 데이터로 재최적화할지
5. 보유 기간을 당일 청산으로 제한할지, 수일 스윙까지 허용할지

---

## 7. 복합 스코어링 설계 초안

초기 총점은 100점 체계를 유지한다.

```text
Total Score = volatility_score + flow_score + pattern_score + risk_adjustment
```

초기 가중치 후보:

| 축 | 점수 | 설명 |
|---|---:|---|
| 가격 변동성 / 시가 이격 | 30 | 장초반 돌파와 이격도 |
| 수급 상관관계 | 30 | 거래량 급증, 가격-거래량 동행성 |
| 90일 패턴 | 25 | 과거 유사 패턴의 양봉/수익 확률 |
| 리스크 보정 | 15 | 과열, VI 근접, 변동성 과다, 데이터 품질 |
| 합계 | 100 |  |

초기 신호 기준은 확정하지 않는다. 백테스트 전에는 아래를 후보로만 둔다.

```text
BUY 후보: total_score >= 70
WATCH: 55 <= total_score < 70
HOLD/NO_TRADE: total_score < 55
SELL/EXIT: 별도 청산 전략에서 판단
```

주의:

- 사용자의 기존 원칙상 전략 임계값은 검토 없이 바로 코드에 반영하지 않는다.
- 백테스트 전에는 위 점수 기준을 확정하지 않는다.
- 거래 빈도가 너무 낮으면 threshold/포지션 규칙 버그로 보고 원인 분석한다.

---

## 8. 구현 전 필수 검증 조건

이 전략은 장초반/분봉/수급 데이터가 중요하므로, 구현 전 아래를 먼저 확인한다.

### 8.1 데이터 수집 검증

```text
1. ka10006 snapshot_1m 누적 품질과 누락 여부
2. 당일 시가/현재가/고가/저가/거래량 필드 검증
3. 10분/30분 오프닝 레인지 계산 가능 여부
4. 90일치 일봉 데이터 누락 여부
5. 90일치 분봉 데이터 확보 가능 여부
```

### 8.2 품질 검증

```text
- 중복 timestamp 없음
- OHLC 관계 오류 없음
- 거래량 음수/누락 없음
- 시가 대비 이격도 계산 가능
- 외부 기준 가격과 스케일 일치
```

### 8.3 백테스트 검증

```text
- 최소 90거래일 이상
- KOSPI TOP50 또는 KOSPI200 중 실제 데이터 있는 종목
- 거래 비용/슬리피지 반영
- 장초반 10분/30분 버전 비교
- 종목당 최대 비중 제한
- 하루 최대 거래 횟수 제한
```

---

## 9. Research AI/Monitoring AI/Leader AI 연결 방식

### Research AI

```text
- 전략 점수 계산
- 세부 점수 breakdown 생성
- BUY/WATCH/HOLD 후보 저장
- 후지모토 전략 리서치 추가 자료 정리
```

### Monitoring AI

```text
- 데이터 누락 감지
- 장초반 급등락/VI 근접 위험 감지
- 신호는 있는데 주문 후보가 생성되지 않은 원인 분석
- 백테스트 거래 빈도 이상 감지
```

### Leader AI

```text
- BUY 후보 중 risk check 통과 종목만 order_candidate 생성
- 초기에는 승인형 모의주문만 실행
- 전략 임계값/가중치 변경은 사용자 승인 후 반영
```

---

## 10. n8n 연결 후보

운영 오케스트레이션은 전략 계산을 직접 수행하지 않고, 아래 스크립트를 실행하고 JSON 결과를 읽어 분기한다. 현재 1차 경로는 Hermes cron + trading-runner이며, n8n은 백업/승인 UI 후보로 둔다.

```text
run_opening_strategy_research.py
run_intraday_opening_monitor.py
run_strategy_backtest.py
```

초기 운영 workflow 후보:

```text
09:00~09:30  장초반 데이터 수집
09:10        공격형 10분 전략 점수 계산
09:30        보수형 30분 전략 점수 계산
09:35        order_candidates 생성 또는 알림
15:40        당일 결과 평가 및 90일 패턴 DB 업데이트
```

---

## 11. 다음 구현 파일 후보

```text
core/opening_strategy.py
core/pattern_matching.py
core/volume_price_flow.py
scripts/run_opening_strategy_research.py
scripts/backtest_opening_strategy.py
docs/strategies/investment_strategy_registry_v1.md
```

---

## 12. 현재 결론

이번 Word 전략보고서는 다음 방향으로 등록한다.

```text
전략명: opening_multi_factor_v1
핵심축: 가격 변동성 + 수급 상관관계 + 90일 패턴
보류축: 후지모토 시게루 매매법, 별도 리서치 후 편입
초기 상태: 등록 완료 / 구현 전 검토
다음 단계: ka10006 snapshot_1m 누적 무결성 검증 → 백테스트 준비도 게이트 → 스코어링 후보 검증
```

실제 코드 구현은 바로 들어가지 않고, 먼저 사용자의 전체 워크플로우 설명과 후지모토 시게루 매매법 자료 확인 후 2차 등록 문서에서 확정한다.
