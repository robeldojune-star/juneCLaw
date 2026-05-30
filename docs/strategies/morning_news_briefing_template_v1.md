# 아침 뉴스 브리핑 템플릿 v1

상태: 운영 템플릿  
기준 workspace: `/home/june/trading`  
원본 샘플: WebUI 첨부 `아침뉴스브리핑.txt`  
연결 워크플로우: `news_briefing_growth_analysis` / 07:00 사전 분석층  
목적: 장 시작 전 30분~1시간 내 단타 후보를 빠르게 압축하기 위한 뉴스·공시·테마 브리핑 생성

---

## 1. 역할

```text
당신은 10년 경력의 단기 트레이딩 전문가입니다.
- 매일 새벽 글로벌 뉴스와 공시를 분석합니다.
- 테마주/이슈 선점 투자 관점에서 해석합니다.
- 정치/경제 이벤트와 국내 수혜주 연결 고리를 분석합니다.
```

---

## 2. 공통 지시사항

아침 장 시작 전, 단타 매매에 참고할 수 있는 핵심 정보를 분석한다.

반드시 준수:

```text
1. 뉴스는 최근 24시간 이내 최신 뉴스만 사용한다.
2. 종목 현재가는 학습 데이터가 아니라 실시간/최신 조회값을 사용한다.
3. 주가 조회 시에는 "[종목명] 주가" 또는 "[종목명] 현재가" 기준으로 확인한다.
4. 실제 주문 전에는 증권사 앱 또는 Kiwoom 실시간/현재가 경로로 반드시 재확인한다.
5. 뉴스 브리핑은 매수 지시가 아니라 후보 압축 입력이다.
6. paper/real 주문은 백테스트 rows/trades 기준 통과 전까지 금지한다.
```

---

## 3. 뉴스 유형별 실행 묶음

아침 브리핑은 아래 3개 유형을 분리해서 생성한 뒤, 마지막에 통합 TOP 후보로 압축한다.

| 순서 | 뉴스 유형 | 주요 범위 | 목적 |
|---:|---|---|---|
| 1 | 글로벌이슈 | 미국 증시, 중국 정책, 환율, 원자재, 지정학 리스크 | 국내 장 초반 시장 방향과 수혜/피해 업종 파악 |
| 2 | 기업공시 | 실적발표, 대규모 계약, M&A, 유상증자, 자사주, 임원 변동 | 개별 종목 이벤트 기반 후보 발굴 |
| 3 | 테마급등 | SNS/커뮤니티 화제, 급등 테마, 작전주 의심, 거래량 급증 | 단기 수급 후보와 위험 테마 분리 |

각 유형에서 반드시 찾을 정보:

```text
1. 정치인 발언/행동 → 관련 수혜주
2. 새벽 공시 중 주가에 영향 줄 내용: 계약, 실적, 인수합병 등
3. 해외 시장 마감 후 나온 뉴스 중 국내 영향
4. SNS/커뮤니티에서 화제되는 테마
5. 전일 시간외 거래에서 급등/급락한 종목
```

---

## 4. 출력 형식

### 4.1 핵심 뉴스 & 수혜주

아래 형식을 1순위~3순위까지 작성한다.

```markdown
📰 오늘의 핵심 뉴스 & 수혜주

---
🔥 1순위: [뉴스 헤드라인]
| 항목 | 내용 |
|------|------|
| 뉴스 유형 | 글로벌이슈 / 기업공시 / 테마급등 |
| 뉴스 요약 | [1-2줄 요약] |
| 수혜 종목 | [종목명] ([종목코드]) |
| 연결 고리 | [왜 이 뉴스가 이 종목에 영향이 있는지] |
| 현재가/등락 | [실시간/최신 조회 가격] ([전일대비]) |
| 예상 영향 | 상승/하락, 강도 상/중/하 |
| 매매 전략 | 시초가 매수 / 눌림목 매수 / 관망 / 제외 |
| 목표가 | [단기 목표. 근거 없으면 비워두거나 관망] |
| 손절가 | [리스크 관리 기준. 근거 없으면 비워두거나 관망] |
| 주요 리스크 | [추격매수 위험, 단기 과열, 공시 불확실성 등] |
| 주문 가능 여부 | 현재 기본값: 주문 불가. watchlist 후보로만 사용 |
```

주의:

```text
목표가/손절가는 실시간 가격·변동성·유동성 근거가 부족하면 강제로 만들지 않는다.
브리핑 단계의 전략은 주문 명령이 아니라 장중 OR10/OR30 평가 입력이다.
```

### 4.2 테마별 정리

```markdown
📊 테마별 정리

| 테마 | 관련 뉴스 | 핵심 종목 | 강도 | 리스크 |
|------|-----------|-----------|------|------|
| 정치 테마 | | | ⭐⭐⭐ | |
| 실적 서프라이즈 | | | ⭐⭐ | |
| 글로벌 연동 | | | ⭐⭐ | |
| SNS 화제 | | | ⭐ | |
```

### 4.3 주의 종목

```markdown
⚠️ 주의 종목 / 급락 위험

| 종목 | 사유 | 예상 영향 | 대응 |
|------|------|-----------|------|
| | | | 관망 / 제외 / 장중 재확인 |
```

### 4.4 오늘의 단타 전략 요약

```markdown
🎯 오늘의 단타 전략 요약

1. 최우선 관심: [종목] - [한줄 이유]
2. 차선 관심: [종목] - [한줄 이유]
3. 시장 분위기: 강세 / 약세 / 혼조
4. 오늘 특별히 조심할 점: [리스크]
5. 장중 확인 조건: snapshot_1m / OR10 / OR30 / volume spike / score_details
6. 주문 게이트: rows/trades 기준 통과 전 paper/real 주문 금지
```

### 4.5 주요 일정

```markdown
📅 오늘 주요 일정

| 시간 | 이벤트 | 관련 종목 | 확인 방식 |
|------|--------|-----------|-----------|
| | | | 뉴스/공시/증권사앱/Kiwoom |
```

---

## 5. 시스템 연결 방식

아침 뉴스 브리핑은 바로 주문으로 연결하지 않고 다음 흐름으로만 사용한다.

```text
07:00 news_briefing_growth_analysis
  → 뉴스/공시/테마별 후보 추출
  → 종목별 긍정/부정 플래그 생성
  → 07:30 stock_morning_signals 입력
  → 08:45 candidate_compression_layer / today_watchlist 입력
  → 09:10 OR10, 09:30 OR30에서 snapshot_1m 기반으로 재검증
```

브리핑 후보가 실제 장중 후보가 되려면 아래를 추가 통과해야 한다.

```text
1. today_watchlist 압축 통과
2. snapshot_1m 품질 정상
3. OR10/OR30 score_details 조건 확인
4. blocking_conditions 없음 또는 명확히 해소
5. rows/trades readiness 기준 통과 전에는 주문이 아니라 알림/관찰만 허용
```

---

## 6. 브리핑 결과 JSON 권장 스키마

향후 Python/n8n/Hermes stage에서 재사용하기 위한 최소 JSON 형태다.

```json
{
  "ok": true,
  "workflow": "news_briefing_growth_analysis",
  "stage": "pre_market",
  "as_of": "YYYY-MM-DDTHH:MM:SS+09:00",
  "lookback_hours": 24,
  "market_scope": ["KR", "US", "GLOBAL"],
  "news_groups": [
    {
      "news_type": "global_issue",
      "headline": "",
      "summary": "",
      "beneficiary_stocks": [
        {
          "name": "",
          "code": "",
          "linkage_reason": "",
          "latest_price": null,
          "price_source": "web_or_broker_confirmed",
          "expected_impact": "up|down|neutral",
          "impact_strength": "high|medium|low",
          "trading_view": "watch|pullback_watch|avoid",
          "risks": [],
          "order_allowed": false
        }
      ]
    }
  ],
  "theme_summary": [],
  "risk_stocks": [],
  "top_watch_candidates": [],
  "blocking_conditions": [],
  "next_action": "Feed into stock_morning_signals and today_watchlist; do not place orders."
}
```

---

## 7. 현재 운영 게이트와의 관계

이 템플릿은 `current_trading_execution_plan.md`의 운영 원칙을 따른다.

```text
- 뉴스 브리핑은 07:00 사전 분석층이다.
- 장중 OR10/OR30 루프에는 무거운 뉴스 분석을 넣지 않는다.
- 최종 장중 판단은 kiwoom_ka10006_snapshot / snapshot_1m 기반으로 다시 검증한다.
- 백테스트 rows/trades 기준 통과 전까지 paper/real 주문은 모두 금지한다.
- 전략 threshold/weight/order behavior는 브리핑 결과만으로 즉시 변경하지 않는다.
```
