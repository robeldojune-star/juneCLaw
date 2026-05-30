# 00. 트레이딩 마스터 플랜 — 최초 전략 등록 기반 최신 운영 기준

상태: **마스터 플랜 / 현재 기준**  
작성 기준: 2026-05-30 07:35 KST  
작업 공간: `/home/june/trading`  
최초 기반 보고서: `docs/strategies/investment_strategy_registry_v1.md`  
현재 실행 기준: `docs/strategies/current_trading_execution_plan.md`  
문서 인덱스: `docs/strategies/00_report_standards_and_index.md`

---

## 1. 이 문서의 역할

이 문서는 사용자가 트레이딩 시스템의 전체 방향을 빠르게 파악하기 위한 **마스터 플랜 보고서**다.

초기 전략 등록 보고서인 `investment_strategy_registry_v1.md`의 전략 목적을 유지하되, 이후 실제 운영 점검에서 확정된 내용을 반영해 현재 기준을 정리한다.

```text
초기 전략 목적
→ 장초반 변동성·수급·90일 패턴·후지모토 관심 전략을 결합해 매매 후보를 선별한다.

현재 운영 기준
→ ka10080 과거 1분봉으로 백테스트하고, ka10006 snapshot_1m으로 장중 감시하며,
   성과 gate 통과 전까지 paper/real 주문은 차단한다.
```

---

## 2. 최종 목표

최종 목표는 단순 자동매매가 아니라 **학습하는 매매 운영 보조 시스템**이다.

```text
장전 분석
→ 오늘 후보 압축
→ 장중 타이밍 감시
→ 신호/차단 원인 기록
→ paper 검증
→ 장후 손익/실패 원인 분석
→ 전략 수정 후보 생성
→ 백테스트/사용자 승인 후 반영
```

사용자 문제의식:

| 문제 | 시스템 대응 방향 |
|---|---|
| 공포 때문에 진입을 놓침 | 사전 기준과 장중 신호로 감정 개입 축소 |
| 욕심 때문에 청산을 놓침 | 손절/익절/시간청산 rule과 장후 피드백 |
| 여러 차트를 동시에 못 봄 | AI/cron/runner가 후보와 타이밍을 계속 감시 |
| 근거 없는 자동매매 위험 | backtest → paper → real pilot gate를 분리 |

---

## 3. 전략군 구조

최초 전략 등록 기준의 전략군은 유지한다.

| 전략 모듈 | 역할 | 현재 상태 |
|---|---|---|
| S1. 장초반 가격 변동성 / OR 돌파 | 장 시작 후 방향성과 힘 측정 | 핵심 검증 대상. OR10/OR30 및 진입 변형 비교 중 |
| S2. 수급 상관관계 / 거래량 | 돌파 신뢰도와 수급 강도 확인 | 돌파봉 거래량 조건으로 부분 검증 시작 |
| S3. 90일 시계열 패턴 | 과거 유사 패턴 기반 기대값 판단 | 표본 확대/백필 후 검증 필요 |
| S4. 후지모토 시게루/1-2-6 | 보조 필터/분할 관점 | 보조 전략. 주 전략으로 단독 채택 금지 |
| Risk/Human Guard | 행동 편향 차단 | 주문 차단/승인 gate의 철학적 기준 |

현재 운영명:

```text
opening_multi_factor_v1
```

단, 현재 이 이름은 **전략 후보군 이름**이며, 실주문 가능한 완성 전략을 의미하지 않는다.

---

## 4. 데이터 소스 기준

현재 확정된 데이터 소스 기준은 다음과 같다.

| 목적 | 공식 소스 | source/time_frame | 상태 |
|---|---|---|---|
| 과거 1분봉 백테스트 | Kiwoom REST `ka10080` | `kiwoom_ka10080_minute / 1min` | 공식 백테스트 기준 |
| 장중 실시간 감시 | Kiwoom `ka10006` snapshot 누적 | `kiwoom_ka10006_snapshot / snapshot_1m` | Hermes cron으로 운영 |
| 일봉/후속 수익률 | `daily_prices` | 일봉 종가 | after_1d/after_3d 계산에 필요 |
| 공시/재무 | OpenDART | 별도 API | 장전 리서치/필터 후보 |
| 계좌 상태 | Kiwoom kt00004 패턴 | 실계좌 조회 | 주문 전 리스크 확인용 |

폐기된 전제:

```text
ka10005 date-only 응답을 1분봉처럼 저장하거나 OR 백테스트에 쓰지 않는다.
n8n이 장중 snapshot 반복 수집의 1차 경로가 아니다.
성과 검증 전 BUY 신호를 자동 주문으로 연결하지 않는다.
```

---

## 5. 현재 운영 구조

현재 장중 수집/감시의 1차 경로는 아래와 같다.

```text
Hermes cron, no_agent=true
  -> ~/.hermes/scripts/trading_snapshot_collector.py
      -> docker compose -f /home/june/n8n/docker-compose.yml exec -T trading-runner
          -> python scripts/run_daily_workflow_stage.py --stage collect_current_session_snapshots
          -> python scripts/inspect_snapshot_1m_status.py
```

n8n의 현재 위치:

```text
n8n은 일일 오케스트레이션/알림/향후 승인 UI 후보로 유지한다.
장중 snapshot_1m 반복 수집의 1차 경로는 Hermes cron이다.
사용자가 n8n UI 운영에 불편함을 느끼므로, 복잡한 운영은 CLI/Hermes/trading-runner 직접 자동화를 우선한다.
```

---

## 6. 현재 주문 상태

현재 주문 상태는 명확히 **blocked**다.

| 주문 종류 | 현재 상태 | 이유 |
|---|---|---|
| real 주문 | 차단 | 백테스트/paper gate 미통과 |
| paper 주문 | 차단 | OR 진입 성과 미달 및 표본 부족 |
| 신호 기록 | 허용 | `signal_events` 등 read-only/분석용 기록 |
| 백테스트 | 허용 | `ka10080`/DB read-only 기반 |
| 전략 변경 | 사용자 승인 전 차단 | 장후 분석 → 후보 → 검증 → 승인 순서 필요 |

주문 차단의 현재 핵심 근거:

```text
1. OR10/OR30 실제 진입 후보가 비용 반영 후 손실.
2. BLOCKED_ENTRY_SIGNAL의 proxy 성과가 오히려 더 양호했던 샘플 존재.
3. after_1d/after_3d 후속 수익률은 daily_prices 추가 수집 전까지 완성 불가.
4. trading_signals의 signal_date 표본이 아직 작다.
5. ka10080 다음 거래일 분봉 누락 종목이 많다.
```

---

## 7. 최근 진입 전략 검증 반영

| 6 | `reports/entry_variant_comparison_latest.md` / `reports/documents/entry_variant_comparison_2026-05-30.md` | 최신 진입 변형 검증 결과 |

| 비교 항목 | 구현/해석 |
|---|---|
| OR 돌파 직후 즉시 진입 | `immediate_breakout` |
| pullback/rebreak 진입 | `pullback_rebreak` |
| 09:10~10:00 진입 제한 | `entry_window` |
| 돌파봉 거래량 조건 | `volume_confirmed_breakout` |
| 진입 후 3~5분 내 급락 필터 | `early_drop_filtered_breakout` |
| 10:00 확인 진입 | `ten_oclock_confirmation` |

현재 작은 표본 기준 결론:

```text
- 즉시 돌파 진입은 손절로 끝남.
- 09:10~10:00 제한만으로는 개선이 확인되지 않음.
- pullback/rebreak와 거래량 조건은 진입 수를 줄였지만 수익성 개선 근거는 부족.
- early_drop_filter는 현재 OR10 손실 진입 2건을 차단했으나 진입 0건이라 표본 확대 필요.
- 10:00 확인 진입은 전부 차단되어 보수적 필터로만 관찰.
```

운영 반영:

```text
현재 어떤 진입 변형도 paper/real 주문 허용 근거가 아니다.
early_drop_filter와 10:00 confirmation은 손실 방어 후보로 남기되, 표본 확대 후 판단한다.
```

---

## 8. 단계별 마스터 로드맵

### Phase 1 — 데이터 수집 안정화

상태: **부분 완료 / 운영 감시 중**

완료/유지:

- Hermes cron 기반 ka10006 snapshot_1m 수집
- snapshot 품질 watchdog
- source/time_frame 분리
- ka10005 분봉 전제 폐기

계속 확인:

- 장중 최신 lag
- 중복 timestamp
- active_codes 수
- quality_error_counts

### Phase 2 — ka10080 과거 1분봉 백테스트 기반 확립

상태: **진행 중**

필요:

- 과거 signal_date 확대
- BUY/HOLD/SELL 신호 backfill
- 다음 거래일 ka10080 분봉 누락 보완
- rows/trades/performance gate 설정

### Phase 3 — 신호 활용 gap 분석

상태: **진행 중**

핵심 질문:

```text
진입한 신호가 실제로 좋은가?
차단된 신호가 더 좋았는가?
장중 수익률과 1일/3일 후속 수익률이 어떻게 다른가?
```

필요 데이터:

- `signal_events`
- `intraday_prices` ka10080 1min
- `daily_prices` after_1d/after_3d

### Phase 4 — 진입 변형 누적 비교

상태: **초기 검증 완료 / 표본 부족**

비교 후보:

- immediate OR breakout
- pullback/rebreak
- 09:10~10:00 window
- breakout volume confirmation
- early drop filter
- 10:00 confirmation

통과 기준 후보:

```text
최소 표본: 종목-일자 기준 50~100 trades 이상
평균 net return > 0
positive_rate가 비용 반영 후 유의미하게 개선
특정 1일/1종목 편향 없음
손절 과다 발생 조건이 설명 가능
```

### Phase 5 — paper 검증

상태: **미시작 / blocked**

진입 조건:

```text
ka10080 누적 백테스트 gate 통과
signal_events 후속 수익률 검증 완료
early_drop / volume / 10:00 confirmation 등 후보 필터 비교 완료
사용자 승인
```

### Phase 6 — real pilot

상태: **미시작 / executor 없음 기준 설계만 존재**

전제:

- paper 성과 통과
- 계좌/리스크 확인 자동화
- 일일 손실 한도
- 종목별/총 노출 한도
- 사용자의 명시 승인

---

## 9. 현재 최우선 작업

| 우선순위 | 작업 | 목적 | 상태 |
|---:|---|---|---|
| 1 | 문서 번호 체계 정립 | 사용자가 전체 흐름 파악 가능 | 이번 문서에서 반영 |
| 2 | 최신 진입 변형 결과를 docs 보고서로 승격 | reports 산출물을 의사결정 문서화 | 다음 작업 후보 |
| 3 | ka10080 분봉 backfill 확대 | 표본 부족 해소 | 필요 |
| 4 | technical_score_v1 신호 backfill | 과거 signal_date 확대 | 필요 |
| 5 | BLOCKED vs INTRADAY 후속 수익률 재계산 | 신호 품질 판단 | daily_prices 필요 |
| 6 | paper gate 수치 확정 | 주문 차단 해제 판단 기준 마련 | 필요 |

---

## 10. 사용자가 현재 알아야 할 결론

```text
1. 최초 전략 방향은 유지한다.
2. 하지만 현재 실행 기준은 ka10080 백테스트 + ka10006 실시간 감시로 바뀌었다.
3. n8n은 중심 운영이 아니라 보조/승인 UI 후보로 낮아졌다.
4. paper/real 주문은 아직 차단 상태가 맞다.
5. 현재 문제는 시스템 고장이 아니라, 성과 검증과 표본 부족 문제다.
6. 보고서는 앞으로 00/01/02 순서와 마스터 플랜 중심으로 정리한다.
```

---

## 11. 다음 업데이트 규칙

새로운 검증을 수행할 때마다 아래 순서로 문서를 갱신한다.

```text
1. scripts/ 또는 reports/에서 raw 산출물 생성
2. docs/strategies/NN_topic_YYYY-MM-DD.md로 사용자용 요약 보고서 작성
3. docs/strategies/00_report_standards_and_index.md에 번호 추가
4. docs/strategies/00_master_trading_plan.md의 현재 상태/우선순위만 갱신
5. 주문 상태가 바뀌는 경우 current_trading_execution_plan.md도 함께 갱신
```

이 방식으로 최초 보고서의 전략 목적과 최신 운영 판단이 분리되지 않도록 유지한다.
