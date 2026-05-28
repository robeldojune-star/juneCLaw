# n8n 장초반 전략 워크플로우 초안

전략: `opening_multi_factor_v1`  
상태: 초안 / n8n import JSON 작성 전 설계 문서  
원칙: n8n은 오케스트레이션만 담당하고, 계산은 Python/core가 담당한다.

---

## 1. Workflow: Opening Strategy Research

권장 실행:

```text
09:05 KST  장초반 snapshot 확인
09:10 KST  10분 공격형 점수 계산
09:30 KST  30분 보수형 점수 계산
15:40 KST  당일 결과 평가/백테스트 데이터 적재
```

---

## 2. n8n 노드 구조

```text
Cron Trigger
  → Execute Command: cd /home/june/trading && python3 scripts/smoke_test_kiwoom_intraday_api.py 005930
  → IF: ok == true
      → Execute Command: python3 scripts/run_opening_strategy_research.py --stock-code 005930
      → IF: score >= 70 AND blocking_conditions does not include critical block
          → Telegram/Email: BUY 후보 알림
        ELSE
          → Telegram/Email: WATCH/HOLD 요약
    ELSE
      → Telegram/Email: Kiwoom 장초반 데이터 검증 실패
```

---

## 3. Execute Command 예시

```bash
cd /home/june/trading
python3 scripts/run_opening_strategy_research.py --stock-code 005930
```

출력은 JSON이다. n8n은 마지막 stdout을 파싱해 `score`, `score_details`, `blocking_conditions`를 읽는다.

---

## 4. 알림 포맷 후보

```text
[opening_multi_factor_v1]
종목: 005930
신호: HOLD
점수: 45.0

세부:
- 변동성: 14/30
- 수급: 16/30
- 90일 패턴: 0/25, 백테스트 대기
- 리스크: 15/15

차단조건:
- pattern_model_not_ready
- ka10005 timeframe needs market-hours validation
```

---

## 5. 안전장치

```text
- 이 workflow는 주문을 내지 않는다.
- order_candidate 생성은 별도 Leader AI workflow에서만 수행한다.
- 90일 패턴/분봉 검증이 끝나기 전에는 BUY라도 알림 전용이다.
- 실제 주문 전에는 모의투자 승인형 workflow로 분리한다.
```

---

## 6. 다음 단계

```text
1. n8n 서버 설치/접속 방식 확정
2. Execute Command 권한/작업 디렉터리 확인
3. JSON 파싱 노드 구성
4. Telegram 또는 Hermes webhook 알림 연결
5. KOSPI TOP50 반복 실행으로 확장
```
