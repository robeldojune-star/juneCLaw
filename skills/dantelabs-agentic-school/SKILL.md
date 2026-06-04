---
name: dantelabs-agentic-school
description: 다중 AI 트레이딩 시스템 (Dantelabs Agentic School 기반)
---

# 다중 AI 트레이딩 시스템

## 개요
Dantelabs Agentic School에서 영감을 받은 다중 AI 트레이딩 시스템입니다.

## 시스템 구조
1. **Leader AI (Hermes main)**: 전체 조정 및 최종 결정
2. **Monitoring AI**: 트레이딩 실패 원인 분석 및 문제 해결
3. **Financial/Research AI**: 재무 분석, 뉴스 리서치, 신호 생성

## 작업 폴더 구조
```
/home/june/trading_workspace/
├── core/                 # 핵심 API 및 DB 모듈
│   ├── kiwoom_api.py   # 키움 API 연동
│   ├── database.py      # DB 연결 및 쿼리
│   └── strategy.py     # 매매 전략 로직
├── .openclaw/skills/  # 스킬 폴더
├── charts/              # 차트 이미지
├── logs/                # 로그 파일
└── config/             # 환경 설정 (mock.json, prod.json)
```

## 환경 설정 (.env)
- `TRADING_ENV`: mock (모의투자) / prod (실전투자)
- `KIWOOM_REST_API_KEY`: 키움 REST API 키
- `KIWOOM_ACCOUNT_NO`: 계좌번호

## 주요 기능
1. **실제 데이터 수집**: 키움 API (ka10031, ka10081 등)
2. **기술적 분석**: 이동평균선, RSI, MACD 등
3. **매매 신호 생성**: 다중 팩터 전략
4. **리스크 관리**: 포지션 크기, 스톱로스

## 다음 단계
1. `.env` 파일 수정 (사용자님이 직접)
2. 키움 API EndPoint 확인 및 수정
3. 실제 데이터 수집 테스트
4. 전략 백테스트 및 최적화

---
*이 스킬은 Dantelabs Agentic School의 개념을 트레이딩 시스템에 적용한 것입니다.*