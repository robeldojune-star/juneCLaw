# 10분/30분 오프닝 레인지 백테스트 설계 v1

연결 전략: `opening_multi_factor_v1`  
상태: 설계 완료 / 구현 대기. 현재 기준은 `docs/strategies/current_trading_execution_plan.md`를 우선한다.  
전제: 실제 Kiwoom 데이터만 사용. 가짜·랜덤 데이터 금지. `ka10005` date-only 응답은 분봉으로 사용하지 않고, 장중 데이터는 `ka10006` 기반 `snapshot_1m` 누적을 사용한다.

---

## 1. 목적

장초반 첫 10분과 30분의 오프닝 레인지가 당일 양봉/추세 지속/수익 가능성에 얼마나 유효한지 검증한다.

비교 대상:

```text
A. 10분 오프닝 레인지: 공격형
B. 30분 오프닝 레인지: 보수형
```

---

## 2. 검증 질문

1. 첫 10분 고가 돌파 후 종가가 상승 마감할 확률은?
2. 첫 30분 고가 돌파가 10분보다 노이즈를 줄이는가?
3. 거래량 급증이 동반될 때 성과가 개선되는가?
4. 90일 유사 패턴 점수를 추가하면 false positive가 줄어드는가?
5. 후지모토식 보조 필터, 즉 재무 필터/RSI/거래대금 조건이 성과를 개선하는가?

---

## 3. 필요 데이터

| 데이터 | 테이블/출처 | 필수 여부 |
|---|---|---:|
| KOSPI TOP50 유니버스 | `kospi_top50` | 필수 |
| 90일 이상 일봉 | `daily_prices` / Kiwoom `ka10081` | 필수 |
| 장초반 snapshot_1m | `intraday_prices` / Kiwoom `ka10006` snapshot 누적 | 필수 |
| 현재가/당일 OHLCV | Kiwoom `ka10006`/`ka10007` 후보 | 필수 |
| 재무 필터 | OpenDART / `financial_scores` 예정 | 선택, 후지모토 보조 필터 |
| RSI/기술지표 | `technical_indicators` 또는 분봉 계산 | 선택 |

---

## 4. 데이터 품질 조건

백테스트 전 다음 조건을 만족해야 한다.

```text
- 종목코드 6자리 정규화
- timestamp 중복 없음
- OHLC 관계: high >= max(open, close), low <= min(open, close)
- volume >= 0
- 첫 10분/30분 bar 수 충분
- 당일 시가/종가/고가/저가 스케일 정상
```

---

## 5. 전략 규칙 후보

### 5.1 10분 공격형

```text
opening_high_10 = first_10m_high
opening_low_10 = first_10m_low
entry = opening_high_10 상향 돌파
filter = volume_spike_ratio >= 1.10
exit = 당일 종가 또는 손절/익절 후보
```

### 5.2 30분 보수형

```text
opening_high_30 = first_30m_high
opening_low_30 = first_30m_low
entry = opening_high_30 상향 돌파
filter = volume_spike_ratio >= 1.10
exit = 당일 종가 또는 손절/익절 후보
```

### 5.3 래리 윌리엄스 변동성 돌파 조합

```text
larry_entry = today_open + k * (yesterday_high - yesterday_low)
k 후보 = 0.25, 0.35, 0.50
entry = current_price > larry_entry AND opening_range_breakout
```

---

## 6. 성과 지표

```text
- 거래 수
- 승률
- 평균 수익률
- 중앙값 수익률
- 최대 낙폭
- profit factor
- 종목별 편중도
- 일별 거래 빈도
- 미체결/데이터 누락 비율
```

사용자 선호상 거래 빈도가 지나치게 낮으면 전략이 좋은 것이 아니라 임계값/데이터/포지션 규칙 문제로 진단한다.

---

## 7. 출력 JSON 표준

백테스트 스크립트는 n8n/Hermes가 읽을 수 있게 마지막에 JSON을 출력한다.

```json
{
  "ok": true,
  "workflow": "backtest_opening_range",
  "strategy_id": "opening_multi_factor_v1",
  "period": {
    "lookback_days": 90
  },
  "variants": {
    "opening_10m": {
      "trades": 0,
      "win_rate": null,
      "avg_return_pct": null,
      "max_drawdown_pct": null
    },
    "opening_30m": {
      "trades": 0,
      "win_rate": null,
      "avg_return_pct": null,
      "max_drawdown_pct": null
    }
  },
  "blocking_conditions": []
}
```

---

## 8. 구현 순서

```text
1. ka10005를 분봉 소스로 사용하지 않도록 차단 조건 유지
2. ka10006 current-session snapshot을 `intraday_prices.time_frame=snapshot_1m`으로 누적
3. 90일치 snapshot_1m 누적 또는 검증된 별도 minute-history API 확보 전까지 백테스트/주문 blocked 유지
4. 10분/30분 오프닝 레인지 feature 생성
5. 단일 종목 삼성전자 백테스트 smoke
6. KOSPI TOP50 확장
7. 후지모토 보조 필터 ON/OFF 비교
```
