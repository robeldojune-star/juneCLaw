# 후지모토 1-2-6 독립 전략 검증 가이드

## 목적
후지모토 시게루 1-2-6 전략을 보조 필터가 아닌 **독립 전략**으로 검증하고, paper 거래 승인 게이트를 통과시키기 위한 절차를 정의합니다.

## 검증 흐름
1. **데이터 충분성 확인**
   - `ka10080` 1분봉 데이터로 최근 90거래일 이상 확보
   - `scripts/check_backtest_readiness.py` 실행 → `rows_used` 및 `total_variant_trades` 게이트 통과
2. **신호 생성 규칙 확정**
   - 진입: `evaluate_fujimoto_126(window)` 가 `signal == "HIGH_CONFIDENCE_CANDIDATE"`かつ `position_stage == "STAGE3"`
   - 포지션 사이징: 1 unit per entry (1:2:6 분할은 시뮬레이션에서 적용)
   - 재진입 가능: 포지션 청산 후 같은 날 새로운 신호에 다시 진입
3. **청산 규칙 (시뮬레이션에 반영)**
   - 손절: 진입가 –2% (저가가 해당 수준에 도달하면 남은 포지션 전량 청산)
   - 목표수익:
     - 진입가 +3% 달성 시 보유 포지션의 50% 청산
     - 남은 50%에 대해 손절가를 진입가(break‑even)로 이동
     - 남은 50%가 진입가 +5%에 도달하면 전량 청산 (추가 강제 청산)
   - 시간 기반 청산: 당일 15:20에 잔여 포지션 전량 청산
4. **백테스트 실행 및 성과 지표 검증**
   - 스크립트: `scripts/backtest_fujimoto_126.py` (또는 `generate_fujimoto_signals.py` + `backtest_fujimoto.py`)
   - 필수 지표:
     - 승률 > 52%
     - 수익 팩터 > 1.3
     - 최대 낙폭 < 18%
   - 최소 거래 수: 5 variant trades 이상
5. **차트 시각화 검증**
   - `scripts/create_fujimoto_126_charts.py` 실행 → 진입·청산 포인트가 포함된 PNG 차트 생성
   - 시각적으로 확인 사항:
     - 신호 형성 이전에 진입하지 않았는가?
     - 일목 구름대 계산에 충분한 캔들(≥52) 사용했는가?
     - 도지/긴 윗꼬리 돌파를 무조건 매수하지 않았는가?
6. **문서 업데이트**
   - 위 단계를 모두 통과한 경우:
     - `docs/strategies/investment_strategy_registry_v1.md` 에서 전략 ID `fujimoto_shigeru_v1`의 `status` 를 `validated_for_paper` 로 변경
     - `docs/strategies/fujimoto_shigeru_strategy_report.md` 에 성과 요약 및 차트 링크 추가
   - 아직 미달이라면 `research_note_ready_not_implemented` 또는 `independent_strategy_candidate` 상태 유지

## 안전 결론
- 검증 완료 전까지 `paper_order_allowed=false`, `real_order_allowed=false`, `order_execution_enabled=false` 를 유지해야 함.
- Leader 승인형 paper 주문 단계는 위의 검증 게이트를 모두 통과한 후에만 고려한다.

## 참고 파일
- `core/fujimoto_126_filter.py` – `simulate_fujimoto_126_trade` 함수에 위의 규칙 구현
- `scripts/generate_fujimoto_signals.py` (예정) – 신호 생성 스크립트
- `scripts/backtest_fujimoto_126.py` (예정) – 백테스트 및 성과 지표 계산 스크립트
- `scripts/create_fujimoto_126_charts.py` – 차트 시각화