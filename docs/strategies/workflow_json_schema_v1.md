# n8n/Python 공통 Workflow JSON 스키마 v1

적용 파일:

```text
scripts/run_daily_workflow_stage.py
scripts/daily_pnl_feedback_report.py
workflows/n8n/daily_trading_workflow_v1.import.json
```

---

## 1. 목적

모든 시간대별 workflow가 같은 JSON 형태를 stdout으로 출력하게 하여 n8n이 성공/실패/차단 조건을 일관되게 분기할 수 있도록 한다.

---

## 2. 표준 출력 구조

```json
{
  "ok": false,
  "workflow": "daily_trading_workflow_v1",
  "stage": "opening_30m_standard_layer",
  "status": "blocked",
  "started_at": "2026-05-29T00:00:00+00:00",
  "finished_at": "2026-05-29T00:00:10+00:00",
  "model_grade": "low",
  "steps": [],
  "summary": {},
  "alerts": [],
  "blocking_conditions": [],
  "next_actions": []
}
```

---

## 3. 필드 의미

| 필드 | 의미 |
|---|---|
| `ok` | 하위 단계가 모두 정상이고 critical block이 없으면 true |
| `workflow` | 상위 워크플로우 이름 |
| `stage` | 현재 시간대별 stage 이름 |
| `status` | `completed`, `blocked`, `failed` 중 하나 |
| `model_grade` | n8n/AI 운영 비용 관리용 모델 등급 |
| `steps` | 내부 실행 단계 목록 |
| `alerts` | Telegram/Hermes 알림 후보 메시지 |
| `blocking_conditions` | 다음 단계/주문 실행을 막는 명시적 조건 |
| `next_actions` | 운영자가 다음에 확인할 항목 |

---

## 4. n8n 분기 원칙

```text
ok == true
  → 다음 단계 또는 요약 알림

ok == false AND blocking_conditions 존재
  → 차단 사유를 Telegram/Hermes에 보고, 주문 workflow로 넘기지 않음

status == failed
  → 재시도 또는 Monitoring AI 진단
```

---

## 5. 주문 안전 규칙

```text
- run_daily_workflow_stage.py는 주문을 내지 않는다.
- opening_10m/30m layer는 알림/모의 후보 전용이다.
- pattern_model_not_ready_for_auto_order 또는 ka10005_timeframe_needs_market_hours_validation이 있으면 자동 주문 금지.
- Leader AI 주문 workflow는 별도 승인형으로 분리한다.
```

---

## 6. Telegram 연결 원칙

n8n에서 Telegram credential을 설정한 뒤 다음 내용만 전송한다.

```text
stage
ok/status
summary
alerts
blocking_conditions
next_actions
```

민감정보, API 키, 계좌번호, PAT는 stdout에 포함하지 않는다.
