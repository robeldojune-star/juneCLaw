# n8n Docker 설정 운영 노트 v1

상태: 설정 완료  
대상: `/home/june/n8n/docker-compose.yml` + `/home/june/trading` stage runner

---

## 1. 발견한 문제

n8n은 Docker 컨테이너에서 실행 중이다.

```text
n8n-n8n-1        docker.n8n.io/n8nio/n8n:latest
n8n-worker-1     docker.n8n.io/n8nio/n8n:latest
n8n-postgres-1   postgres:15-alpine
n8n-redis-1      redis:7-alpine
```

따라서 n8n `Execute Command` 노드는 호스트의 `/home/june/trading`을 직접 볼 수 없고, n8n 이미지에는 `python3`도 없다.

```text
컨테이너 내부 /home/june/trading 없음
컨테이너 내부 python3 없음
```

그래서 기존 `Execute Command` 기반 import JSON은 Docker 운영에서는 실패한다.

---

## 2. 적용한 해결책

`trading-runner` Docker 서비스를 추가했다.

역할:

```text
n8n HTTP Request node
  -> http://trading-runner:8765/run-stage
  -> /app/scripts/run_daily_workflow_stage.py --stage <stage>
  -> 표준 JSON 반환
  -> notify=true면 Telegram 요약 전송
```

서비스 파일:

```text
/home/june/trading/scripts/trading_stage_http_server.py
/home/june/trading/docker/trading-runner/Dockerfile
```

Docker Compose 수정 위치:

```text
/home/june/n8n/docker-compose.yml
```

백업:

```text
/home/june/n8n/backups/docker-compose.before-trading-runner.*.yml
```

---

## 3. 실행 상태

확인 명령:

```bash
docker ps --filter name=n8n
docker logs --tail 50 n8n-trading-runner-1
```

n8n 컨테이너에서 runner health 확인:

```bash
docker exec n8n-n8n-1 sh -lc 'wget -qO- --timeout=10 http://trading-runner:8765/health'
```

정상 예:

```json
{
  "ok": true,
  "service": "trading-runner",
  "project_root": "/app",
  "python": "3.11.15",
  "telegram_config_present": true
}
```

---

## 4. n8n import 파일

Docker용 import 파일:

```text
/home/june/trading/workflows/n8n/daily_trading_workflow_v1.http.import.json
```

기존 Execute Command용 파일:

```text
/home/june/trading/workflows/n8n/daily_trading_workflow_v1.import.json
```

Docker 환경에서는 `.http.import.json`을 사용한다.

현재 n8n DB에 import 완료:

```text
id: daily_trading_workflow_v1
name: daily_trading_workflow_v1_docker_http
active: false
HTTP Request runner nodes: 16
```

---

## 5. Telegram 알림

n8n UI credential 없이도 runner가 Hermes env fallback으로 Telegram을 전송한다.

마운트:

```text
/home/june/.hermes/.env -> /home/runner/.hermes/.env:ro
```

필요 키:

```text
TELEGRAM_BOT_TOKEN
HERMES_TELEGRAM_CHAT_ID 또는 TELEGRAM_CHAT_ID
```

검증 완료:

```text
notify smoke: ok=true, message_id=300
```

---

## 6. 재시작/재배포

runner 코드 수정 후:

```bash
docker compose -f /home/june/n8n/docker-compose.yml restart trading-runner
```

Dockerfile/의존성 수정 후:

```bash
docker compose -f /home/june/n8n/docker-compose.yml up -d --build trading-runner
```

workflow JSON 수정 후 재import:

```bash
docker cp /home/june/trading/workflows/n8n/daily_trading_workflow_v1.http.import.json n8n-n8n-1:/tmp/daily_trading_workflow_v1.http.import.json

docker exec n8n-n8n-1 n8n import:workflow \
  --input=/tmp/daily_trading_workflow_v1.http.import.json \
  --projectId=cos0ZEljBIBrvMIs
```

---

## 7. 활성화 전 체크리스트

```text
1. n8n UI에서 daily_trading_workflow_v1_docker_http 열기
2. 각 Cron 시간이 Asia/Seoul 기준인지 확인
3. Manual 실행으로 system_health_check 또는 news_briefing_growth_analysis 테스트
4. Telegram 메시지가 1건만 오는지 확인
5. 자동 실행은 검증 후 active=true로 전환
6. opening_10m/30m은 blocking_conditions가 유지되는지 확인
```

자동 주문 workflow는 아직 활성화하지 않는다.
