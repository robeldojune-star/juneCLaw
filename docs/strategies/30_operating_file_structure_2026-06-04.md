# 30. 현재 운영 파일 구조 및 RSI/CCI Master Plan 반영 확인

상태: 운영 구조 정리 / 반영 확인  
작성 기준: 2026-06-04 KST  
작업 공간: `/home/june/trading`  
상위 기준 문서: `docs/strategies/00_master_trading_plan.md`  
첨부 원문: `/home/june/.hermes/webui/attachments/20260604_000552_5d569e/master_plan.md`

---

## 1. 첨부 master_plan.md 내용 확인

첨부 파일은 다음 문서다.

```text
Master Plan: RSI/CCI Disparity Strategy with Mock/Prod Separation
```

핵심 내용은 다음과 같다.

| 항목 | 첨부 원문 내용 |
|---|---|
| 전략 | RSI/CCI disparity20 전략 |
| 구조 | `shared/`, `envs/mock/`, `envs/prod/`, `scripts/run_strategy.py` |
| 공통 모듈 | `shared/strategy.py`, `shared/order.py`, `shared/notify.py` |
| 실행 방식 | `scripts/run_strategy.py --env mock|prod --stock ...` |
| 안전장치 | mock/prod credential 분리, `--execute` 없이는 주문 없음 |
| 확장 과제 | stop-loss/trailing, position sizing, 다종목 처리, CSV/SQLite 기록, n8n 연동 |

---

## 2. 현재 공식 마스터 플랜 반영 여부

결론: **반영되어 있다. 단, 원문 전체를 붙인 것이 아니라 보조 전략 요약과 안전 기준으로 반영되어 있다.**

공식 기준 문서:

```text
docs/strategies/00_master_trading_plan.md
```

반영 위치:

```text
## 13. 보조 전략·실험 노트 통합 요약
### 13.2 RSI/CCI Disparity 전략 상태
```

현재 공식 마스터 플랜의 해석:

| 첨부 원문 항목 | 현재 반영 상태 | 판단 |
|---|---|---|
| `shared/` 공통 모듈 | 반영됨 | 실제 파일 존재 |
| `envs/mock`, `envs/prod` 분리 | 반영됨 | 실제 폴더/환경 파일 존재 |
| `scripts/run_strategy.py` 실행 구조 | 반영됨 | 실제 파일 존재 |
| RSI/CCI 조건 | 반영됨 | 보조 전략 후보로 요약 |
| mock/prod 주문 안전장치 | 반영됨 | `--execute` 없이는 주문 금지로 요약 |
| prod execute 예시 | **그대로 반영하지 않음** | 현재 공식 주문 상태가 blocked이므로 실주문 실행 예시는 운영 기준으로 승격하지 않음 |
| n8n pre-market 연동 | 부분 반영 | n8n은 장전/보조 오케스트레이션 후보로 유지 |

중요한 차이:

```text
첨부 원문은 RSI/CCI 전략 개발 계획이다.
현재 공식 마스터 플랜은 전체 운영 기준이다.
따라서 RSI/CCI는 핵심 전략이 아니라 보조/실험 후보로 반영되어 있다.
```

---

## 3. 실제 파일 존재 확인

확인 결과:

```text
shared/strategy.py: OK
shared/order.py: OK
shared/notify.py: OK
envs/mock/.env: OK
envs/prod/.env: OK
scripts/run_strategy.py: OK
docs/archive/legacy_markdown_2026-06-04/docs_strategies/master_plan.md: OK
docs/strategies/00_master_trading_plan.md: OK
```

즉, 첨부 원문에서 요구한 기본 구조는 현재 프로젝트에 존재한다.

---

## 4. 현재 운영되는 파일 구조

아래 구조가 현재 `/home/june/trading`의 운영 기준 구조다.

```text
/home/june/trading
├── core/
│   ├── kiwoom_client.py              # Kiwoom REST client
│   ├── market_data_service.py        # 시장 데이터 조회 계층
│   ├── account_service.py            # 계좌 조회/정규화
│   ├── opening_strategy.py           # 장초반 전략 핵심 로직
│   ├── fujimoto_126_filter.py        # 후지모토 1-2-6 보조 필터
│   ├── trading_mode.py               # backtest/paper/real 모드 구분
│   ├── workflow_result.py            # workflow 결과 구조
│   └── supabase_rest.py              # Supabase REST 접근
│
├── shared/
│   ├── strategy.py                   # RSI/CCI/disparity 공통 전략 함수
│   ├── order.py                      # 주문 wrapper 후보
│   └── notify.py                     # Telegram/Hermes 알림
│
├── scripts/
│   ├── run_strategy.py               # RSI/CCI runner, mock/prod env 로딩
│   ├── run_daily_workflow_stage.py   # 일일 workflow stage 실행
│   ├── collect_current_session_snapshots.py
│   ├── inspect_snapshot_1m_status.py
│   ├── collect_intraday_90d.py
│   ├── collect_daily_prices_kiwoom.py
│   ├── collect_dart_disclosures.py
│   ├── backtest_opening_strategy.py
│   ├── backtest_entry_variant_comparison.py
│   ├── backtest_fujimoto_126.py
│   └── ...                           # 수집/백테스트/검증 스크립트
│
├── dash-kiwoom/
│   ├── app.py                        # 현재 외부 서비스 중인 Flask/Socket.IO 대시보드
│   ├── templates/
│   │   └── index.html                # 대시보드 UI
│   ├── static/                       # CSS/JS/font assets
│   ├── data/
│   │   └── signals.csv               # 대시보드가 읽는 신호 파일
│   └── dashboard.log
│
├── docs/
│   ├── strategies/
│   │   ├── 00_master_trading_plan.md # 최상위 공식 마스터 플랜
│   │   ├── 00_report_standards_and_index.md
│   │   ├── current_trading_execution_plan.md
│   │   ├── 29_legacy_markdown_consolidation_2026-06-04.md
│   │   ├── 30_operating_file_structure_2026-06-04.md
│   │   └── ...                       # 전략/운영 numbered reports
│   ├── archive/
│   │   └── legacy_markdown_2026-06-04/
│   │       └── ...                   # 중복/레거시 Markdown 원문 보관
│   └── strategy_sources/
│       ├── README.md
│       └── export*.md                # 원본 전략 추출 자료
│
├── data/
│   ├── intraday/                     # 로컬 intraday CSV/검증 데이터
│   ├── review/                       # 리뷰용 산출물
│   └── kospi_top50_*.csv             # KOSPI top50 universe 자료
│
├── envs/
│   ├── mock/.env                     # mock Kiwoom credentials
│   └── prod/.env                     # production Kiwoom credentials
│
├── workflows/
│   └── n8n/
│       ├── daily_multi_ai_workflow_v1.json
│       ├── daily_trading_workflow_v1.import.json
│       ├── leader_approval_order_workflow.template.json
│       └── opening_strategy_workflow.md
│
├── config/
│   ├── mock.json
│   ├── prod.json
│   └── news_sources.json
│
├── references/
│   └── disclosure_weights.yaml
│
├── tests/
│   ├── test_entry_variant_comparison.py
│   └── test_fujimoto_126_filter.py
│
└── 루트의 다수 실험 스크립트
    ├── backtest_*.py
    ├── debug_*.py
    ├── grid_search_*.py
    ├── optimize_*.py
    └── test_*.py
```

---

## 5. 실제 운영 중인 서비스 구조

현재 외부에서 운영 중인 대시보드는 다음 서비스다.

```text
systemd user service: dash-kiwoom.service
WorkingDirectory: /home/june/trading/dash-kiwoom
ExecStart: /home/june/trading/dash-kiwoom/.venv/bin/python /home/june/trading/dash-kiwoom/app.py
Port: 3000
External URL: https://dash-kiwoom.duckdns.org/
```

역할:

| 파일/폴더 | 운영 역할 |
|---|---|
| `dash-kiwoom/app.py` | Flask + Socket.IO API 서버 |
| `dash-kiwoom/templates/index.html` | 대시보드 화면 |
| `dash-kiwoom/data/signals.csv` | 현재 신호 표시 데이터 |
| `docs/strategies/00_master_trading_plan.md` | 대시보드와 운영 판단의 기준 문서 |
| `scripts/run_strategy.py` | RSI/CCI 전략 runner |
| `core/*` | Kiwoom/API/전략 공통 계층 |
| `shared/*` | RSI/CCI 관련 공통 모듈 |

---

## 6. 현재 정리 판단

현재 구조는 크게 두 층으로 보는 것이 맞다.

### 6.1 운영 핵심

```text
core/
shared/
scripts/
dash-kiwoom/
docs/strategies/
envs/
workflows/n8n/
data/
config/
```

### 6.2 정리/아카이브 대상

```text
루트의 backtest_*.py
루트의 debug_*.py
루트의 grid_search_*.py
루트의 optimize_*.py
루트의 test_*.py 중 pytest가 아닌 임시 실행 파일
```

권장 다음 정리 구조:

```text
experiments/
├── backtests/
├── grid_search/
├── debug/
└── legacy_tests/
```

단, 다음 단계에서 루트 스크립트를 이동하기 전에는 import 경로와 실행 커맨드가 깨질 수 있으므로, 먼저 사용 중인 스크립트 목록을 분류해야 한다.

---

## 7. 최종 결론

첨부된 RSI/CCI `/home/june/.hermes/webui/attachments/20260604_000552_5d569e/master_plan.md`는 현재 공식 마스터 플랜에 반영되어 있다.

다만 현재 운영 기준상:

```text
RSI/CCI disparity = 보조 전략 후보
mock/prod 분리 구조 = 유효한 안전 구조
prod execute 예시 = 현재 blocked 상태이므로 공식 운영 명령으로 승격하지 않음
```

현재 공식 운영 구조는 `dash-kiwoom`, `core`, `shared`, `scripts`, `docs/strategies`, `envs`, `workflows`, `data`를 중심으로 유지한다.
