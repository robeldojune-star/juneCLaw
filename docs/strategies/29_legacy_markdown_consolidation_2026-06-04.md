# 29. 레거시 Markdown 정리 및 마스터 플랜 반영 보고서

상태: 기준 반영 / 문서 정리  
작성 기준: 2026-06-04 KST  
작업 공간: `/home/june/trading`  
상위 기준 문서: `docs/strategies/00_master_trading_plan.md`

---

## 1. 결론 요약

루트와 `docs/strategies`에 흩어져 있던 중복/실험성 Markdown을 검토했고, 운영 판단에 필요한 내용만 `00_master_trading_plan.md`에 요약 반영했다.

이번 정리의 핵심은 다음과 같다.

1. `00_master_trading_plan.md` 끝에 붙어 있던 RSI/CCI master plan 원문 덤프를 제거했다.
2. 루트 `docs/archive/legacy_markdown_2026-06-04/root/master_plan.md`의 후지모토 1-2-6 로드맵은 보조/독립 후보 전략으로 요약 반영했다.
3. 공시·거래량 분석은 “공시 건수 단독으로는 유의한 거래량/가격 판단 근거가 약하다”로 반영했다.
4. 동적 청산/RSI 단독 실험은 “진입 기대값 확보 전에는 paper/real gate 해제 근거가 아니다”로 반영했다.
5. 대시보드 기준에는 “실시간 지수 미연동, 가짜 시세 표시 금지, signals.csv freshness 표시”를 반영했다.

---

## 2. 검토한 레거시 문서

| 원문 | 처리 | 마스터 플랜 반영 |
|---|---|---|
| `docs/archive/legacy_markdown_2026-06-04/root/master_plan.md` | archive 후보 | 후지모토 1-2-6 독립 후보 전략 요약 |
| `docs/archive/legacy_markdown_2026-06-04/docs_strategies/master_plan.md` | archive 후보 | RSI/CCI disparity 보조 전략 요약 |
| `docs/archive/legacy_markdown_2026-06-04/root/README_rsi_cci.md` | archive 후보 | RSI/CCI 구현/운영 구조 참고 |
| `docs/archive/legacy_markdown_2026-06-04/root/DATA_PIPELINE_CHECK.md` | archive 후보 | OpenDART/daily_prices coverage 이슈 반영 |
| `docs/archive/legacy_markdown_2026-06-04/root/DISCLOSURE_VOLUME_CORRELATION.md` | archive 후보 | 공시 건수와 거래량 상관 약함 반영 |
| `docs/archive/legacy_markdown_2026-06-04/root/dynamic_exit_strategies.md` | archive 후보 | 동적 청산 후보와 제약 반영 |
| `docs/archive/legacy_markdown_2026-06-04/root/summary.md` | archive 후보 | 최근 실험 결과 요약 반영 |
| `workflows/n8n/opening_strategy_workflow.md` | archive 후보 또는 workflow 참고 | n8n은 장전/보조 오케스트레이션 위치로 유지 |
| `docs/strategies/fujimoto_independent_plan.md` | 유지/인덱스 편입 | 후지모토 독립 후보 전략의 세부 계획 |
| `docs/strategies/fujimoto_shigeru_strategy_report.md` | 유지/인덱스 편입 | 후지모토 전략 리포트 원문 |

---

## 3. 운영 판단

### 3.1 주문 상태

이번 정리로 주문 상태는 바뀌지 않는다.

```text
real 주문: blocked
paper 주문: blocked
신호 기록/read-only 분석: allowed
백테스트: allowed
```

### 3.2 전략 상태

| 전략/아이디어 | 현재 위치 | 판단 |
|---|---|---|
| opening_multi_factor_v1 | 주 검증축 | ka10080/ka10006 기준 표본 확대 필요 |
| 후지모토 1-2-6 | 보조/독립 후보 | 최근 신호 부족. 단독 주 전략 채택 금지 |
| RSI/CCI disparity | 보조 후보 | mock/prod 분리 구조는 유용하지만 gate 대체 불가 |
| 공시/거래량 | 장전 리서치 후보 | 공시 건수 단독 사용 금지, 유형 가중치 필요 |
| 동적 청산 | 청산 후보 | 진입 기대값 확보 후 비교 |

---

## 4. 앞으로의 문서 규칙

- 마스터 플랜에는 원문 전체를 붙이지 않는다.
- 새 실험은 `docs/strategies/NN_topic_YYYY-MM-DD.md`에 요약 보고서로 남긴다.
- 원문/초안/중복 문서는 `docs/archive/legacy_markdown_YYYY-MM-DD/`로 이동한다.
- 사용자가 먼저 보는 기준은 항상 다음 순서다.

```text
1. docs/strategies/00_master_trading_plan.md
2. docs/strategies/00_report_standards_and_index.md
3. docs/strategies/current_trading_execution_plan.md
4. 최신 numbered report
```

---

## 5. 다음 정리 후보

- `docs/strategy_sources/export*.md`: 원본 추출 자료이므로 `docs/strategy_sources/README.md`를 만들어 출처를 명확히 하는 것이 좋다.
- `docs/strategies`의 오래된 초안 문서: 삭제하지 않고 인덱스에서 “현재 해석”만 명확히 유지한다.
- 루트에 새 Markdown을 만들지 않고 `docs/strategies` 또는 `docs/archive`로 귀속한다.
