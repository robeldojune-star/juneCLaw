# 00. 트레이딩 문서·보고서 기준 및 시간순 인덱스

상태: **문서 기준 / 신규 보고서 저장 규칙**  
작성 기준: 2026-05-30 07:35 KST  
작업 공간: `/home/june/trading`  
목적: 사용자가 전체 진행 흐름을 빠르게 파악할 수 있도록, `/home/june/trading/docs`의 전략 문서와 운영 보고서를 시간순으로 정리하고 앞으로 작성할 보고서 저장 기준을 고정한다.

---

## 1. 기준 원칙

앞으로 트레이딩 관련 마크다운 문서는 아래 원칙을 따른다.

```text
1. 모든 기준 문서는 /home/june/trading/docs/strategies 아래에 둔다.
2. 사용자가 흐름을 볼 때는 00, 01, 02... 순서로 읽는다.
3. 기존 파일명은 링크 파손을 막기 위해 즉시 변경하지 않는다.
4. 대신 이 문서를 공식 시간순 인덱스로 두고, 새 보고서는 번호 prefix를 붙인다.
5. 마스터 플랜은 항상 00_master_trading_plan.md를 최신 기준으로 업데이트한다.
6. 실험/백테스트 산출물은 reports/에 생성해도, 의사결정용 요약본은 docs/strategies에 번호형 보고서로 남긴다.
```

---

## 2. 파일명 규칙

### 2.1 기준 문서

```text
docs/strategies/00_master_trading_plan.md
docs/strategies/00_report_standards_and_index.md
```

`00_` 문서는 최신 기준과 문서 체계를 나타낸다. 사용자가 가장 먼저 읽어야 한다.

### 2.2 신규 보고서

새 보고서는 아래 형식을 사용한다.

```text
docs/strategies/NN_short_topic_YYYY-MM-DD.md
```

예시:

```text
docs/strategies/27_entry_variant_comparison_2026-05-30.md
docs/strategies/28_ka10080_backfill_result_2026-05-30.md
docs/strategies/29_paper_validation_gate_review_2026-05-31.md
```

### 2.3 번호 부여 기준

| 번호대 | 용도 |
|---:|---|
| 00 | 마스터 플랜, 문서 기준, 전체 인덱스 |
| 01~09 | 최초 전략 등록, 원본 전략 해석, 기본 설계 |
| 10~19 | 운영 워크플로우, n8n/Hermes, 백테스트 설계 |
| 20~29 | 데이터 무결성, 모드 분리, 신호 활용, 진입 변형 검증 |
| 30~39 | 표본 확대, ka10080 backfill, 누적 성과 비교 |
| 40~49 | paper 검증, 승인형 주문, 실전 파일럿 |
| 50+ | 장기 운영, 성과 개선, 전략 변경 승인 이력 |

---

## 3. 보고서 공통 형식

새 보고서는 가능한 한 아래 형식을 따른다.

```markdown
# NN. 보고서 제목

상태: 초안 / 검증중 / 기준 확정 / 폐기  
작성 기준: YYYY-MM-DD HH:MM KST  
작업 공간: `/home/june/trading`  
상위 기준 문서: `docs/strategies/00_master_trading_plan.md`  
관련 산출물: `reports/...` 또는 `scripts/...`

---

## 1. 결론 요약

## 2. 배경 / 왜 이 보고서를 만들었는가

## 3. 사용 데이터와 전제

## 4. 검증 결과 / 표

## 5. 운영 판단

## 6. 다음 작업

## 7. 차단 조건 / 주의사항
```

트레이딩 보고서는 항상 다음을 명시한다.

- 실데이터 여부: Kiwoom / OpenDART / Supabase 실제 데이터인지
- 주문 영향 여부: read-only인지, paper인지, real인지
- 데이터 소스: `ka10080 1min`, `ka10006 snapshot_1m`, `daily_prices` 등
- 차단 조건: 주문 금지, 표본 부족, 분봉 누락, 성과 미달 등
- 결론: 지금 운영에 반영 가능한지, 추가 검증이 필요한지

---

## 4. 현재 문서 시간순 인덱스

> 기준: 파일 수정 시각 + 문서 제목 기준. 기존 문서는 원본 파일명을 유지한다.

| 순서 | 문서 | 역할 | 현재 해석 |
|---:|---|---|---|
| 01 | `docs/strategies/opening_range_backtest_design.md` | OR10/OR30 백테스트 설계 | 초기 OR 전략 설계 문서 |
| 02 | `docs/strategies/leader_ai_approval_order_workflow_v1.md` | Leader AI 승인형 주문 설계 | 향후 paper/real 승인형 실행 후보 |
| 03 | `docs/strategies/workflow_json_schema_v1.md` | n8n/Python 공통 JSON schema | 워크플로우 출력 표준 후보 |
| 04 | `docs/strategies/n8n_docker_setup_note_v1.md` | n8n Docker 운영 노트 | n8n 운영 참고. 현재는 보조 역할 |
| 05 | `docs/strategies/n8n_import_telegram_connection_guide.md` | n8n import/Telegram 연결 | n8n 연결 참고. 현재는 보조 역할 |
| 06 | `docs/strategies/research_ai_score_breakdown_v1.md` | Research AI 점수 breakdown | 후보별 점수 설명 표준 |
| 07 | `docs/strategies/deep_research_v2_entry_thresholds.md` | 진입 수치/통합 스코어링 | 초기 threshold 후보. 실데이터 검증 필요 |
| 08 | `docs/strategies/fujimoto_shigeru_research_note.md` | 후지모토 리서치 노트 | 보조 전략 아이디어 |
| 09 | `docs/strategies/investment_strategy_registry_v1.md` | 최초 투자 전략 등록 | **최초 수립 보고서**. 마스터 플랜의 출발점 |
| 10 | `docs/strategies/daily_multi_ai_n8n_workflow_v1.md` | 시간대별 멀티 AI 운영 | n8n 중심 초안. 현재는 Hermes 중심으로 보정 |
| 11 | `docs/strategies/trading_workflow_direction_review_2026-05-29.md` | 워크플로우 방향성 검토 | 운영형 매매 보조 시스템 방향 확정 |
| 12 | `docs/strategies/today_watchlist_intraday_timing_alert_design_v1.md` | watchlist/timing alert 설계 | 장중 알림 레이어 후보 |
| 13 | `docs/strategies/fujimoto_aux_filter_v1_spec.md` | 후지모토 보조 필터 | 보조 필터 명세. 주 전략 아님 |
| 14 | `docs/strategies/backtest_preparation_execution_plan_2026-05-29.md` | 백테스트 준비 실행계획 | snapshot_1m 기준 계획. 이후 ka10080로 보정됨 |
| 15 | `docs/strategies/next_trading_day_intraday_operational_gate.md` | 다음 거래일 장중 게이트 | 장중 운영 gate 기준 |
| 16 | `docs/strategies/morning_news_briefing_template_v1.md` | 아침 뉴스 브리핑 템플릿 | 장전 리서치 출력 형식 |
| 17 | `docs/strategies/time_ordered_trading_workflow_report.md` | 시간순 전체 워크플로우 | 사용자가 하루 흐름을 보기 위한 핵심 보고서 |
| 18 | `docs/strategies/ka10080_minute_backtest_pipeline_report_2026-05-29.md` | ka10080 백테스트 파이프라인 | 과거 1분봉 기준 소스 확정 |
| 19 | `docs/strategies/ka10080_minute_data_integrity_criteria.md` | ka10080 데이터 무결성 기준 | 분봉 품질 판단 기준 |
| 20 | `docs/strategies/trading_mode_separation_policy.md` | backtest/paper/real 모드 분리 | 안전 운영 기준 |
| 21 | `docs/strategies/real_pilot_test_design_no_executor.md` | executor 미구현 기준 real pilot | 실주문 전 파일럿 설계 |
| 22 | `docs/strategies/human_behavior_guard_trading_principles.md` | 인간 행동 편향 차단 원칙 | 시스템 목적/리스크 철학 |
| 23 | `docs/strategies/current_trading_execution_plan.md` | 현재 운영 실행 계획 | **현재 실행 기준 문서** |
| 24 | `docs/strategies/signal_utilization_gap_report_2026-05-29.md` | 신호 활용 누락 진단 | 신호 생성과 주문 차단 간 gap 분석 |
| 25 | `docs/strategies/current_session_handoff_2026-05-29_signal_strategy.md` | 세션 이어가기 보고서 | 신호 기반 단타+스윙 자동화 handoff |
| 26 | `docs/strategies/fujimoto_126_video_strategy_v1.md` | 1-2-6 분할매매 초안 | 보조/관찰 전략 후보 |
| 27 | `docs/strategies/27_entry_variant_comparison_2026-05-30.md` | OR 진입 변형 비교 결과 | 즉시돌파/pullback/거래량/급락/10:00 확인 비교. 표본 부족으로 주문 반영 보류 |

---

## 5. 마스터 플랜 업데이트 규칙

`docs/strategies/00_master_trading_plan.md`는 아래 문서를 기반으로 계속 업데이트한다.

| 우선순위 | 문서 | 반영 방식 |
|---:|---|---|
| 1 | `investment_strategy_registry_v1.md` | 최초 전략 목적과 전략군 구조 |
| 2 | `current_trading_execution_plan.md` | 현재 실제 운영 기준 |
| 3 | `time_ordered_trading_workflow_report.md` | 하루 시간순 운영 흐름 |
| 4 | `ka10080_minute_backtest_pipeline_report_2026-05-29.md` | 백테스트 데이터 기준 |
| 5 | `signal_utilization_gap_report_2026-05-29.md` | 신호 활용 문제와 개선 과제 |
| 6 | `reports/entry_variant_comparison_latest.md` | 최신 진입 변형 검증 결과 |

업데이트 원칙:

```text
새 실험/보고서가 생기면:
1. reports/ 또는 scripts/ 산출물을 확인한다.
2. 의사결정에 필요한 요약본을 docs/strategies/NN_*.md로 저장한다.
3. 이 인덱스에 번호를 추가한다.
4. 00_master_trading_plan.md의 현재 상태/다음 작업/차단 조건만 갱신한다.
5. 과거 보고서는 삭제하지 않고, 현재 해석을 인덱스에 적는다.
|| 28 | `docs/strategies/28_중복방지_마스터_보고서_2026-06-01.md` | 워크플로우 중복 분석 및 방지 방안 | 현재 운영 워크플로우와 제안된 n8n 기반 아침 분석 워크플로우 간 중복 방지 및 역할 분담 원칙 제시 |
```

---

## 6. 현재 사용자가 먼저 읽을 순서

사용자가 전체 내용을 빠르게 파악하려면 아래 순서로 읽는다.

```text
00_report_standards_and_index.md
00_master_trading_plan.md
09 investment_strategy_registry_v1.md
17 time_ordered_trading_workflow_report.md
23 current_trading_execution_plan.md
24 signal_utilization_gap_report_2026-05-29.md
27 entry_variant_comparison_latest.md 또는 향후 docs 요약본
```
