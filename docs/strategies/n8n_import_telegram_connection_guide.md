# n8n import 및 Telegram 연결 운영 가이드 v1

상태: 로컬 n8n 실행 확인 / 현재 우선순위 낮음 / API import는 `N8N_API_KEY` 필요  
대상 workflow: `workflows/n8n/daily_trading_workflow_v1.import.json`  
참고: 현재 1차 운영 경로는 Hermes cron + trading-runner이며, n8n은 비활성 백업/향후 승인 UI 후보로 둔다.

---

## 1. 현재 확인 결과

```text
n8n process: running
local health: http://127.0.0.1:5678/healthz -> {"status":"ok"}
/rest/workflows: 401 Unauthorized
N8N_API_KEY: missing
TELEGRAM_BOT_TOKEN: project .env missing / Hermes .env present
TELEGRAM_CHAT_ID: project .env missing
Hermes send_message telegram: OK
```

따라서 현재 자동 import는 n8n API credential 입력 전까지 block 상태다. Telegram은 Hermes 홈 채널 전송은 확인됐지만, n8n의 직접 Telegram Bot 노드는 n8n credential 또는 chat id 설정이 추가로 필요하다.

---

## 2. n8n import 방법

### 방법 A — UI import

1. 브라우저에서 n8n 접속
2. Workflows → Import from File
3. 아래 파일 선택

```text
/home/june/trading/workflows/n8n/daily_trading_workflow_v1.import.json
```

4. Import 후 workflow가 `active=false`인지 확인
5. Execute Command 노드의 작업 디렉터리와 Python 경로 확인

### 방법 B — API import

`.env` 또는 실행 환경에 아래를 추가한다. 실제 키는 Git/채팅에 기록하지 않는다.

```bash
N8N_URL=http://127.0.0.1:5678
N8N_API_KEY=...
```

실행:

```bash
cd /home/june/trading
python3 scripts/import_n8n_daily_workflow.py
```

---

## 3. Telegram 연결 방법

### n8n credential 권장

n8n UI에서 Telegram credential을 등록하고, workflow 내 sticky note의 안내대로 Telegram Send Message 노드를 연결한다.

권장 메시지 필드:

```text
stage: {{$json.stage}}
status: {{$json.status}}
summary: {{$json.summary}}
alerts: {{$json.alerts}}
blocking_conditions: {{$json.blocking_conditions}}
```

### 환경변수 테스트 방식

로컬 `.env`에 아래를 넣은 뒤 테스트할 수 있다.

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

실행:

```bash
python3 scripts/check_telegram_connection.py
```

---

## 4. 안전 규칙

```text
- workflow import 직후 active=false 유지
- Telegram credential 연결 전 자동 활성화 금지
- opening_10m/opening_30m는 알림/모의 후보만 생성
- 자동 주문 workflow는 별도 승인형으로 분리
- PAT/API 키/계좌번호는 채팅, Git, 로그에 출력 금지
```

---

## 5. 이번 단계 확인 결과

```text
GitHub push: 완료, main == origin/main 확인
n8n health: http://127.0.0.1:5678/healthz OK
n8n API import: N8N_API_KEY 없음으로 blocked
Telegram test: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 없음으로 blocked
```

구현된 연결:

```text
news_briefing_growth_analysis -> config/news_sources.json + scripts/collect_news_rss.py
candidate_compression_layer -> opening strategy candidate loop
09:10/09:30 opening stage -> TOP 5~10 후보군 루프
Leader AI approval -> workflows/n8n/leader_approval_order_workflow.template.json
```

