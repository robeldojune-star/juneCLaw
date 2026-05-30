# 후지모토 보조 필터 v1 명세서 (코드 반영형)

- 작성일: 2026-05-29
- 워크스페이스: `/home/june/trading`
- 적용 대상 전략: `opening_multi_factor_v1`
- 적용 방식: **독립 전략 아님**, 기존 오프닝 멀티팩터에 보조 필터로 결합
- 주문 정책: readiness 게이트 통과 전까지 `alert_only/paper_only` 유지

---

## 1) 목적

후지모토 시게루 공개 근거(증수/증익/증배, 테크니컬+유동성 중시, 1:2:6 자금관리 관점)를
한국 장초반 단타 파이프라인에 맞춰 **정량 점수 + 블로킹 규칙**으로 정의한다.

핵심 원칙:
1. 실데이터 우선 (OpenDART + Kiwoom snapshot_1m)
2. 과열 추격 금지
3. 1:2:6은 물타기 규칙이 아닌 **단계 진입 가중치 규칙**
4. 기존 `opening_multi_factor_v1` 구조를 깨지 않고 확장

---

## 2) 통합 점수 구조 (v1)

기존 총점은 유지:

```text
total_score = volatility_score(0~30)
            + flow_score(0~30)
            + pattern_score(0~25)
            + risk_adjustment(0~15)
```

후지모토 보조 필터는 2가지 모드 중 택1:

### 모드 A (권장, 보수)
- `total_score`는 기존 그대로 유지
- `fujimoto_aux_score(0~15)`는 **게이트/가산 참조용**으로만 사용
- BUY 최종 승인 조건에 `fujimoto_aux_score >= 8`을 추가

### 모드 B (실험)
- `effective_score = total_score + fujimoto_aux_score - fujimoto_risk_penalty`
- 단, max cap은 100

> 현재 운영은 **모드 A** 권장 (기존 백테스트 일관성 보존)

---

## 3) 후지모토 보조 필터 세부 점수 (0~15)

### 3.1 재무 필터 (최대 5)
- +5: 최근 분기 기준 영업이익 흑자 && 전년동기 대비 악화 아님
- +3: 영업이익 흑자만 충족
- +0: 데이터 없음/미충족

입력 소스:
- OpenDART 파이프라인 산출 컬럼 (예: `financial_filter_passed`, `operating_income_positive`, `earnings_trend_ok`)

### 3.2 RSI 상태 (최대 4)
- +4: `45 <= rsi < 70` (추세 추종 적정)
- +2: `30 <= rsi < 45` (과매도 반등 후보)
- +0: `rsi` 없음
- 블록: `rsi >= 80` 이면 신규 진입 금지

### 3.3 유동성/수급 (최대 3)
- +3: `volume_spike_ratio >= 1.30` && 거래대금 하한 충족
- +2: `volume_spike_ratio >= 1.10`
- +0: 미충족

### 3.4 단계 진입 가능성 (최대 3)
- +3: `stage_entry_ready=true`
  - 정의: 1차 진입 후 가격이 유리한 방향으로 진행했고, 2차 조건 충족 시에만 true
- +1: 1차 진입만 가능
- +0: 단계 진입 구조 미확보

---

## 4) 최종 시그널 판정 규칙 (모드 A)

```text
if financial_filter_failed: HOLD (block)
elif any(critical_block): HOLD (block)
elif total_score >= 70 and fujimoto_aux_score >= 8: BUY
elif total_score >= 55: WATCH
else: HOLD
```

`critical_block` 예:
- `fujimoto_financial_filter_failed`
- `fujimoto_rsi_overheated`
- `fujimoto_gap_overheated`
- `snapshot_1m_bars_not_accumulated`
- `pattern_model_not_ready` (현재 auto order 금지 정책과 정합)

---

## 5) blocking_conditions 표준 ENUM

### 5.1 fujimoto 전용
- `fujimoto_financial_data_missing`
- `fujimoto_financial_filter_failed`
- `fujimoto_rsi_missing`
- `fujimoto_rsi_overheated`
- `fujimoto_volume_insufficient`
- `fujimoto_turnover_insufficient`
- `fujimoto_stage_entry_not_ready`
- `fujimoto_gap_overheated`

### 5.2 기존과 공통 사용
- `snapshot_1m_bars_not_accumulated`
- `pattern_model_not_ready`
- `insufficient_intraday_rows_for_backtest`
- `insufficient_backtest_trade_count`

---

## 6) score_details JSON 스키마 (코드 반영형)

기존 `core/opening_strategy.py`의 `score_details` 구조를 유지하며 필드만 확장한다.

```json
{
  "volatility": {
    "max_score": 30,
    "score": 0,
    "k": 0.35,
    "opening_window": 10,
    "entry_price": 0,
    "open_gap_pct": 0,
    "opening_range": {
      "window": 10,
      "high": 0,
      "low": 0,
      "last_close": 0,
      "volume_sum": 0,
      "bar_count": 0
    },
    "breakout": false,
    "no_rebreak": false
  },
  "flow": {
    "max_score": 30,
    "score": 0,
    "volume_spike_ratio": 0,
    "price_up_with_volume": false,
    "high_break_with_volume": false
  },
  "pattern": {
    "max_score": 25,
    "score": 0,
    "status": "requires_90d_intraday_backtest"
  },
  "risk_adjustment": {
    "max_score": 15,
    "score": 0,
    "financial_filter_passed": null,
    "rsi": null
  },
  "fujimoto_aux_filter": {
    "max_score": 15,
    "score": 0,
    "financial": {
      "score": 0,
      "operating_income_positive": null,
      "earnings_trend_ok": null,
      "source": "opendart"
    },
    "rsi": {
      "score": 0,
      "value": null,
      "band": "unknown"
    },
    "liquidity": {
      "score": 0,
      "volume_spike_ratio": null,
      "turnover_ok": null
    },
    "stage_entry": {
      "score": 0,
      "stage_entry_ready": null,
      "mode": "1:2:6_risk_budget"
    }
  },
  "thresholds": {
    "buy_candidate": 70,
    "watch_min": 55,
    "fujimoto_aux_min": 8,
    "note": "candidate thresholds pending backtest"
  }
}
```

---

## 7) 코드 반영 지점 (파일 단위)

### 7.1 `core/opening_strategy.py`

1. `OpeningStrategyInput` 확장
- `turnover: float | None = None`
- `operating_income_positive: bool | None = None`
- `earnings_trend_ok: bool | None = None`
- `stage_entry_ready: bool | None = None`

2. `fujimoto_aux_filter_score(inp)` 신규 함수 추가
- 반환: `(score, details, blocks)`
- 위 3장 규칙 그대로 구현

3. `score_opening_multi_factor(inp)`에서 통합
- `fa_score, fa_details, fa_blocks = fujimoto_aux_filter_score(inp)`
- `score_details["fujimoto_aux_filter"] = fa_details`
- `thresholds["fujimoto_aux_min"] = 8`
- 시그널 판정 시 `fa_score >= 8` 조건 추가 (모드 A)

### 7.2 `scripts/run_opening_strategy_research.py`

- `OpeningStrategyInput(...)` 생성 시 신규 필드 주입
- OpenDART/사전 계산값이 없으면 `None`으로 두고 `fujimoto_*_missing` block 유도
- 출력 JSON의 `score_details` 구조는 위 스키마 준수

### 7.3 `scripts/run_opening_strategy_candidate_loop.py`

- BUY 후보 계산식 강화:
  - `signal_type == "BUY"`
  - `blocking_conditions` 비어 있음
  - `score_details.thresholds.fujimoto_aux_min` 충족 여부 확인(안전 재검증)

---

## 8) 리스크/가드레일

1. **자동주문 금지 유지**
- readiness gate(`rows>=300`, `trades>=5`) 미충족 시 강제 block

2. **과열 추격 금지**
- `rsi >= 80` 또는 `gap >= +3%`면 BUY 차단

3. **1:2:6 오해 방지**
- 손실 구간 추가매수 금지
- 이익 진행 + 재검증 조건 만족 시에만 단계 확장

---

## 9) 검증 체크리스트

1. 단위 계산 검증
- `fujimoto_aux_filter.score`가 0~15 범위인지
- 임계값 경계(`7.9/8.0`)에서 BUY 판정이 의도대로인지

2. JSON 스키마 검증
- `score_details.fujimoto_aux_filter` 누락 없는지
- `blocking_conditions`가 문자열 배열인지

3. 운영 검증
- 하루치 shadow run 후 BUY 후보 수 변동 점검
- `candidate_count`, `buy_candidate_count`, `no_opening_buy_candidates` 변화 추적

---

## 10) 권장 롤아웃

1. Day 1~3: Shadow mode (점수 기록만)
2. Day 4~10: 모의 BUY 후보 게이트 적용
3. Day 11+: ON/OFF 성과 비교 보고서 후 기준 고정

---

## 11) 현재 결론

- 후지모토 보조 필터 v1은 **즉시 코드 반영 가능한 수준**으로 정의됨.
- 단, 실주문은 readiness gate 충족 전까지 금지.
- 다음 구현 단계는 `core/opening_strategy.py` 함수 추가 + 리서치 스크립트 입력 확장이다.
