# Fujimoto Aux Filter 입력-검토 루프 (opening_multi_factor_v1)

## 언제 쓰는가
- 후지모토 보조필터(`fujimoto_aux_filter`)를 실제 점수에 반영하되, 재무/단계진입 판단은 사람 검토를 끼워 넣어야 할 때.
- "데이터 입력하면서 검토 필요" 요청이 있을 때.

## 핵심 원칙
1. 자동수집과 검토입력을 분리한다.
2. 자동수집 실패를 가짜값으로 대체하지 않는다.
3. 검토 미완료는 `review_required`로 명시하고 block으로 남긴다.

## 입력 소스 분리
- 자동 입력
  - `rsi`: `technical_indicators`의 최신 daily RSI
  - `turnover`: snapshot(`trde_prica`)에서 추출
- 수동(검토) 입력
  - 파일: `data/review/fujimoto_inputs.json`
  - 키: 종목코드
  - 필드:
    - `operating_income_positive` (bool)
    - `earnings_trend_ok` (bool)
    - `stage_entry_ready` (bool)
    - `review_note` (string)

## 권장 파일 형식
```json
{
  "005930": {
    "operating_income_positive": true,
    "earnings_trend_ok": true,
    "stage_entry_ready": false,
    "review_note": "OpenDART 검토 완료: 최근 분기 영업이익 흑자/추세 양호"
  }
}
```

## 구현 포인트
- `scripts/run_opening_strategy_research.py`
  - `_load_manual_fujimoto_inputs(stock_code)`로 수동 검토값 로드
  - `_load_latest_daily_rsi(stock_code)`로 자동 RSI 로드
  - snapshot에서 `turnover` 계산
  - `OpeningStrategyInput`에 주입
  - 출력 JSON `data_quality`에 다음을 포함:
    - `daily_rsi_meta`
    - `turnover_from_snapshot`
    - `manual_fujimoto_review`
    - `review_required`

## 해석 규칙
- `manual_fujimoto_review_missing`가 뜨면 실전 반영 전 검토입력부터 채운다.
- `fujimoto_volume_insufficient`는 유동성 조건 미달로 해석한다(임계값 조정은 백테스트 후).
- `pattern_model_not_ready`가 남아 있으면 auto/real order는 계속 금지.

## 빠른 운영 절차
1. `fujimoto_inputs.example.json`를 복사해 `fujimoto_inputs.json` 생성
2. candidate 상위 종목의 재무/단계진입 검토값 입력
3. `run_opening_strategy_research.py` 실행
4. `score_details.fujimoto_aux_filter`와 `data_quality.review_required` 확인
5. 미충족 block 원인을 분리(검토 누락 vs 데이터 부족 vs 정책 가드)

## 관련 파일
- `docs/strategies/fujimoto_aux_filter_v1_spec.md`
- `data/review/fujimoto_inputs.example.json`
- `scripts/run_opening_strategy_research.py`