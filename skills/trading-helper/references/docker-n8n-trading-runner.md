# Docker n8n + trading-runner 운영 패턴

세션에서 확인된 핵심 패턴:

## 1) 왜 Execute Command가 깨지는가
- n8n이 Docker 컨테이너에서 실행되면 컨테이너 안에 호스트 경로(`/home/june/trading`)와 `python3`가 없을 수 있다.
- 이 상태에서 `Execute Command: cd /home/june/trading && python3 ...`는 구조적으로 실패한다.

## 2) 해결 패턴 (권장)
- `trading-runner` HTTP 서비스(별도 컨테이너)를 두고, n8n 노드는 `HTTP Request`로 호출한다.
- n8n 노드 표준:
  - `POST http://trading-runner:8765/run-stage`
  - body: `{"stage":"<stage>","timeout":600,"notify":true}`
- runner는 `scripts/run_daily_workflow_stage.py --stage ...`를 실행하고 JSON을 그대로 반환한다.

## 3) Telegram 연결 패턴
- runner가 `notify=true`일 때 Telegram 발송을 수행하도록 하면 n8n UI credential 없이도 운영 가능.
- env fallback:
  1. `/home/june/trading/.env`
  2. `~/.hermes/.env`
- chat id fallback:
  - `TELEGRAM_CHAT_ID` 우선
  - 없으면 `HERMES_TELEGRAM_CHAT_ID`

## 4) import/백업 절차
- import 전:
  - `n8n export:workflow --backup --output=...`
- import:
  - `n8n import:workflow --input=... --projectId=...`
- Docker 환경에는 `daily_trading_workflow_v1.http.import.json` 사용.

## 5) 운영 검증 체크리스트
1. `GET http://trading-runner:8765/health` from n8n container
2. `POST /run-stage` smoke (예: `system_health_check`)
3. Telegram notify smoke (`notify=true`)에서 `message_id` 확인
4. 워크플로우는 초기 `active=false` 유지 후 manual 실행 검증
5. 오프닝 자동주문 guard(`pattern_model_not_ready...`, `ka10005_timeframe...`) 유지 확인

## 6) 새 stage 확장 패턴
- run_daily_workflow_stage.py + trading_stage_http_server.py 둘 다 stage allowlist를 갱신해야 runner에서 호출된다.
- stage 추가 시 최소 세트:
  - 구현 스크립트
  - stage handler
  - runner allowlist
  - n8n import JSON 노드
  - smoke test
