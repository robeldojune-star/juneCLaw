# 00. 트레이딩 마스터 플랜 — 최신 운영 기준

상태: **마스터 플랜 / 현재 기준**
최종 갱신: 2026-06-04 13:30 KST
작업 공간: `/home/june/trading`

---

## 1. 이 문서의 역할

트레이딩 시스템 전체 방향과 현재 상태를 한눈에 파악하기 위한 마스터 플랜.
초기 전략 등록 이후 실제 운영·검증에서 확정된 내용을 반영한다.

```text
초기 전략 목적
→ 장초반 변동성·수급·90일 패턴·후지모토 관심 전략을 결합해 매매 후보를 선별한다.

현재 운영 기준
→ ka10080 과거 1분봉으로 백테스트, ka10006 snapshot_1m으로 장중 감시,
   RSI/CCI profit-target 전략으로 신호 생성, profit-taking 크론으로 실전 청산,
   성과 gate 통과 전까지 paper/real 주문은 차단.
```

---

## 2. 최종 목표

학습하는 매매 운영 보조 시스템.

```text
장전 분석 → 후보 압축 → 장중 타이밍 감시 → 신호/차단 기록
→ paper 검증 → 장후 분석 → 전략 수정 후보 → 백테스트 → 사용자 승인
```

---

## 3. 전략군 구조 (2026-06-04 갱신)

| 전략 모듈 | 역할 | 현재 상태 |
|---|---|---|
| **S1. RSI/CCI Profit-Target** | 주 전략 후보 | ✅ 검증 완료 (승률 100%, +0.84% net). signal cron 적용 완료 |
| S2. 장초반 OR 돌파 (OR10/OR30) | 방향성/힘 측정 | ❌ 백테스트 평균 수익 음수. paper/real 차단 |
| S3. 후지모토 1-2-6 | 보조 필터 | ⚠️ 분봉만으로 평가 불가. 일봉 MACD/일목/시장국면 데이터 필요 |
| S4. 공시·거래량 | 장전 리서치 | ⚠️ 공시-거래량 상관관계 미약. 유형 가중치/유동성 필터 필요 |
| Risk/Human Guard | 행동 편향 차단 | ✅ 주문 gate BLOCKED, profit-taking +5% 강제청산 크론 운영 중 |

현재 주력 전략: **RSI/CCI Profit-Target (+1.5%)**
```
진입: disparity20 ≤ 100, CCI -100 상향 돌파, 거래량 ≥ MA20
청산: +1.5% 목표가 도달 (RSI 기반 청산 폐기)
백테스트: 16 trades, 승률 100%, 평균 순수익 +0.84%
```

---

## 4. 데이터 소스 기준

| 목적 | 소스 | 상태 |
|---|---|---|
| 과거 1분봉 백테스트 | Kiwoom ka10080 → intraday_prices | ✅ 5종목 25,000행 backfill 완료 |
| 장중 실시간 감시 | Kiwoom ka10006 snapshot_1m | ✅ Hermes cron 운영 중 |
| 일봉/후속 수익률 | daily_prices | ⚠️ 추가 수집 필요 |
| 공시/재무 | OpenDART | 후보 |
| 계좌 상태 | Kiwoom kt00004 | ✅ 대시보드 연동 완료 |

---

## 5. 현재 운영 인프라

| 구성요소 | 상태 |
|---|---|
| **dash-kiwoom** (Flask, port 3000) | ✅ user systemd 활성. `dash-kiwoom.duckdns.org` |
| **signal dry-run cron** | ✅ 5분 간격, RSI/CCI profit-target 신호 생성 |
| **snapshot collector cron** | ✅ 5분 간격, ka10006 장중 수집 |
| **profit-taking cron** | ✅ 2분 간격, 실전 +5% 강제청산 (prod) |
| **n8n** (Docker, port 5678) | ✅ 복원 완료. `n8n-june.duckdns.org` |
| **Caddy** | ✅ reverse proxy (dash-kiwoom, n8n, hermes, code-server) |
| **Hermes WebUI** | ✅ `hermes-june.duckdns.org` |
| **code-server** | ✅ `code-june.duckdns.org` |
| **GitHub** | ✅ `robeldojune-star/juneCLaw` |

---

## 6. 현재 주문 상태

| 주문 종류 | 상태 | 이유 |
|---|---|---|
| **real 주문** | 차단 | paper gate 미통과 |
| **paper 주문** | 차단 | OR10/OR30 평균 수익 음수, 표본 부족 |
| **profit-taking 청산** | ✅ **활성** | prod 계좌, +5% 도달 시 시장가 매도 (손절 무시) |
| **RSI/CCI 신호** | ✅ 허용 | dry-run dashboard 신호 생성만 |
| **백테스트** | ✅ 허용 | ka10080/DB read-only |

---

## 7. 2026-06-03~04 완료 작업

### 데이터
- ka10080 continuation header (`cont-yn`/`next-key`) 발견 및 수정
- 5종목 25,000행 backfill → readiness rows_used 11,454→24,443

### 전략 검증
- RSI/CCI profit-target (+1.5%): 승률 100%, 16 trades, +0.84% net
- RSI/CCI RSI-exit: 승률 30%, 평균 수익 음수 → 폐기
- Fujimoto 1-2-6: 분봉만으로 평가 불가 확인 (일봉 데이터 필요)

### 대시보드
- 종목명 표시 (STOCK_NAME_MAP, 44종목)
- 보유 0개 계좌에서 예수금 표시
- mock 계좌 갱신 (812***84, 1,000만원)
- backtest readiness JSON 소스 연동

### n8n
- PostgreSQL DB에서 workflow 복원 (workflow_entity + workflow_history)
- ExecuteCommand → Code 노드 변환 (17개)
- daily_trading_workflow_v1 활성화

### 운영
- Profit-taking cron 등록: `*/2 0-6 * * 1-5` (평일 09:00~15:30 KST)
- RSI/CCI signal cron에 profit-target 전략 적용

### 인프라 정리
- hermes/ 4.8GB 중복 삭제 (→ skills만 보존)
- 루트 .py 101개 → experiments/로 이동
- .gitignore 보강, GitHub push 완료

---

## 8. 단계별 로드맵 (2026-06-04 갱신)

### Phase 1 — 데이터 수집 안정화 ✅ (90%)
- ka10006 snapshot_1m 수집: ✅
- ka10080 1분봉 backfill: ✅ (25,000행)
- 품질 watchdog: ✅
- **[남은 과제]** ka10080 종목·기간 확대, daily_prices 추가 수집

### Phase 2 — 전략 검증 ✅ (진행 중)
- RSI/CCI profit-target: ✅ 검증 완료, cron 적용
- OR10/OR30: ❌ 평균 수익 음수
- Fujimoto 1-2-6: ⚠️ 일봉 파이프라인 필요
- **[남은 과제]** RSI/CCI 종목 확대 (042660 → Top 10), walk-forward 검증

### Phase 3 — Paper 검증 (진입 조건)
- RSI/CCI profit-target: ✅ 16 trades, 승률 100%
- 표본 확대 필요: 50~100 trades 목표
- 종목 다양화: 042660 단일 → Top 10 이상

### Phase 4 — Real Pilot (미시작)
- paper 성과 3개월 이상 유지
- 리스크 한도 설정
- 사용자 승인

### Phase 5 — 워크플로우 운영
- n8n: 복원 완료, 장전/장중/장후 역할 분리 정의됨

---

## 9. 다음 단계 (우선순위)

| # | 작업 | 목적 | 예상 효과 |
|---|---|---|---|
| **1** | **RSI/CCI signal 종목 확대** | 042660 → Top 10+ | 거래 기회 증가, 표본 확대 |
| **2** | **ka10080 종목·기간 확대** | 5종목 2주 → 20종목 90일 | 백테스트 신뢰도 향상 |
| **3** | **daily_prices 수집 재개** | after_1d/after_3d 계산 | 신호 후속 수익률 검증 |
| **4** | **RSI/CCI walk-forward 검증** | 3일 훈련 → 1일 테스트 | 파라미터 안정성 확인 |
| **5** | **paper ledger 자동화** | RSI/CCI 신호→paper 주문 기록 | paper gate 데이터 축적 |
| **6** | **Fujimoto 필터 파이프라인** | 일봉 MACD/일목/시장국면 주입 | 보조 필터로 활용 가능성 재평가 |
| **7** | **센티멘트 필터** | 공시 유형 가중치, 외국인/기관 순매수 | 진입 품질 향상 |

---

## 10. 한 줄 요약

```text
RSI/CCI profit-target(+1.5%)이 현재 유일하게 검증된 전략이다.
신호 cron에 적용 완료, 실전 +5% 청산 크론 운영 중.
다음은 종목·기간 확대로 표본을 늘리고 paper gate를 열 준비를 하는 단계다.
```

---

## 11. 업데이트 규칙

```text
1. scripts/ 또는 reports/에서 raw 산출물 생성
2. docs/strategies/NN_topic_YYYY-MM-DD.md로 요약 보고서 작성
3. docs/strategies/00_report_standards_and_index.md에 번호 추가
4. 이 문서(00_master_trading_plan.md)의 상태/우선순위만 갱신
5. 원문은 archive에 보관, 마스터 플랜에는 요약만 반영
```
