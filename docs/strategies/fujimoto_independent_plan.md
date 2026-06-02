# 후지모토 시게루 독립 전략 구체적 실행 계획

## 1. 목표
- 후지모토 시게루 매매법을 기반으로 한 **독립 전략** `fujimoto_shigeru_v1` 을 정의하고,
- ka10080 과거 1분봉 데이터를 이용한 백테스트를 수행하여 paper 거래 검증까지 진행한다.
- 최종 목표: Leader 승인형 paper 주문 단계 진입.

## 2. 현재 상태 (Completed)
| 항목 | 상태 | 증거 |
|------|------|------|
| 연구 노트 작성 | 완료 | `docs/strategies/fujimoto_shigeru_research_note.md` |
| 핵심 지표 구현 (RSI, MACD, Ichimoku) | 완료 | `core/fujimoto_126_filter.py` |
| 전략 등록 (독립 후보) | 완료 | `docs/strategies/investment_strategy_registry_v1.md` (status: independent_strategy_candidate) |
| 데이터 수집 파이프라인 확인 (ka10006 snapshot_1m) | 완료 | Hermes cron logs show `last_status=ok`, quality errors 0 |
| 기본 백테스트 프레임워크 존재 | 완료 | `scripts/backtest_opening_strategy.py`, `scripts/run_daily_workflow_stage.py` |

## 3. 보류 사항 (Pending) 및 세부 작업

### 3.1 데이터 충분성 검증
- **목표**: ka10080 1분봉 데이터 최소 90 거래일 확보
- **작업**:
  1. `scripts/collect_intraday_90d.py` 실행 확인 및 로그 점검
  2. `inspect_snapshot_1m_status.py` 로 최근 90일치 row count 확인
  3. 결손일 보완 또는 휴일 제외 로직 검증
- **임계값**: 총 rows >= 90 * 390 (약 35,100 rows) 혹은 거래일 수 90 이상
- **책임자**: [자동화] Hermes cron + trading-runner
- **예상 완료**: 다음 거래일 종료 시

### 3.2 전략 파라미터 확정 (한국 시장 최적화)
- **목표**: 한국 주식 시장에 맞는 RSI 기간, 과매수/과매도 임계값, MACD 파라미터 검토
- **작업**:
  1. 백테스트 스크립트에 파라미터 스위블 추가 (예: `--rsi-period 14 --rsi-buy 30 --rsi-sell 70`)
  2. 샘플 종목 (예: 삼성전자 005930, SK하이닉스 000660) 로 격자 검색
  3. 평가 지표: 승률, 수익 팩터, 최대 낙폭, Sharpe ratio
- **임계값**:
  - 승률 > 55%
  - 수익 팩터 > 1.2
  - 최대 낙폭 < 20%
- **책임자**: Research AI (시뮬레이션)
- **예상 완료**: 데이터 확보 후 2일 내

### 3.3 1:2:6 분할 진입 로직 구현
- **목표**: 전략 신호 발생 시 총 투자금을 1:2:6 비율로 분할 진입하는 주문 생성 로직 추가
- **작업**:
  1. `core/fujimoto_126_filter.py` 에서 신호 생성 시 `position_stage` 와 `position_units` 반환 유지
  2. 주문 생성 레이어 (예: `scripts/generate_order_candidates.py`) 에서 해당 비율에 따라 주문 수량 계산
  3. 각 단계는 독립된 주문으로 기록 (order_id에 STAGE1/2/3 태그)
  4. 단계 간 조건: 이전 단계 진입 후 가격이一定程度 유리하게 움직였을 때만 다음 단계 허용 (예: +0.5% 상승 시 STAGE2 진입)
- **임계값**: 각 단계 간 최소 가격 변동 0.3% 이상
- **책임자**: Monitoring AI (주문 생성 검증)
- **예상 완료**: 파라미터 확정 후 1일 내

### 3.4 청산 규칙 정의 및 구현
- **목표**: RSI 과열(≥80), 목표수익, 손절, 당일 강제 청산 규칙 구현
- **작업**:
  1. 청산 조건을 `evaluate_fujimoto_126` 혹은 별도 청산 모듈에 추가
  2. 목표수익: 평균 수익의 1.5배 또는 고정 3%
  3. 손절: 고정 -2% 또는 ATR 기반 변동성
  4. 당일 강제 청산 시각: 15:20
- **임계값**:
  - 손절 트리거 시 포지션 전량 청산
  - 목표 도달 시 50% 청산 후 나머지 트레일링 스탑
- **책임자**: Research AI
- **예상 완료**: 진입 로직 후 동일한 날

### 3.5 백테스트 실행 및 결과 분석
- **목표**: 확정된 파라미터와 로직으로 ka10080 데이터 전체에 대해 백테스트 수행
- **작업**:
  1. `scripts/backtest_opening_strategy.py` 에 전략 플래그 추가 (`--strategy fujimoto_shigeru_v1`)
  2. 전체 코스피/코스닥 대상 (상위 100종목) 혹은 사용자 지정 워치리스트 적용
  3. 결과 지표 accumation: 총 수익, 승률, 평균 보유 기간, 최대 연속 손실 일수
  4. 결과 시각화: 누적 수익 곡선, 드로다운 차트, 월별 수익 분포
- **임계값** (통과 조건):
  - 총 수익 > 10% (연간 기준 환산 시 15% 이상)
  - 승률 > 50%
  - 수익 팩터 > 1.3
  - 최대 연속 손실 일수 < 5 거래일
- **책임자**: Leader AI (최종 검토)
- **예상 완료**: 청산 규칙 구현 후 2일 내

### 3.6 paper 거래 시뮬레이션 (Leader 승인 전)
- **목표**: 백테스트 결과를 기반으로 한 달간 paper 거래 시뮬레이션 수행
- **작업**:
  1. 실시간 ka10006 snapshot_1m 스트림을 이용하여 당일 신호 생성
  2. 신호 발생 시 계산된 주문 사이즈 (1:2:6) 로 paper 주문 기록 (내부 DB 또는 CSV)
  3. 일일 포지션 리뷰 및 리스크 체크 (노출 한도, sector 중복)
  4. 주간 리포트 생성 (승률, 손익, 편차 분석)
- **임계값** (진출 조건):
  - 월간 승률 > 52%
  - 월간 수익 > 2%
  - 드로다운 < 5%
- **책임자**: Monitoring AI (실시간 감시)
- **예상 완료**: 백테스트 통과 후 즉시 (다음 달 시작)

## 4. 차단 조건 (Blockers)
| 차단 조건 | 현재 상태 | 해소 조건 |
|----------|-----------|-----------|
| ka10080 데이터 부족 | 데이터 수집 중, 현재 약 45 거래일 확보 | 최소 90 거래일 확보 |
| 전략 파라미터 미최적화 | 기본값 사용 중 | 한국 주식 백테스트 기반 최적값 도출 |
| 1:2:6 진입 로직 미구현 | 현재는 1:3:9 스테이징 (지표 기반) | 주문 생성 레이어에 1:2:6 비율 적용 |
| 청산 규칙 미정의 | 진입 로직만 존재 | 손절/목표수익/강제청산 규칙 구현 |
| 백테스트 통과 실패 | 미정의 | 위 임계값 만족 시 통과 |
| paper 거래 검증 미실시 | 백테스트 전 단계 | 백테스트 통과 후 1개월 시뮬레이션 |

## 5. 리소스 및 의존성
- **데이터 소스**: Kiwoom `ka10080` (과거 1분봉), `ka10006` (현재장 snapshot_1m)
- **외부 의존성**: 없음 (모든 지표 내부 구현)
- **컴퓨팅**: Hermes cron + trading-runner 컨테이너 (현재 운영 중)
- **스크립트 언어**: Python 3.11+, pandas, numpy, ta-lib (필요 시)

## 6. 성공 기준 및 다음 단계
### 6.1 1차 목표 (데이터 및 파라미터 확정)
- [ ] ka10080 90거래일 이상 확보
- [ ] 파라미터 최적화 완료 (RSI, MACD, Ichimoku)
- [ ] 1:2:6 분할 진입 로직 구현
- [ ] 청산 규칙 구현
- [ ] 백테스트 통과 (위 임계값 만족)
- [ ] бумажный 거래 1개월 시뮬레이션 성공
- [ ] Leader 승인 후 paper 주문 단계 진입

## 7. 승인 조건 (Leader AI)
- 백테스트 보고서 제출 (수익 곡선, 드로다운, 트레이드 분석)
- 리스크 분석 (포지션 크기, sector 집중도, 변동성 노출)
- 전략 설명서 업데이트 (`docs/strategies/fujimoto_shigeru_v1.md`)
- 운영 매뉴얼 추가 (주문 생성 및 모니터링 절차)

---

**작성일**: 2026-05-30  
**작성자**: Hermes Agent (사용자 지정 모델: nvidia/nemotron-3-super-120b-a12b:free)  
**참조**: 
- `docs/strategies/fujimoto_shigeru_research_note.md`
- `core/fujimoto_126_filter.py`
- `docs/strategies/investment_strategy_registry_v1.md`
- `docs/strategies/current_trading_execution_plan.md`