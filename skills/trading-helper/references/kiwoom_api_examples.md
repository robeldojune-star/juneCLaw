# 키움 API 호출 예시 (이번 세션에서 검증됨)

## 인증 (OAuth)
```python
import requests, json, os

# config/mock.json 또는 .env에서 읽기
api_key = "LzeJm..."  # KIWOOM_REST_API_KEY_MOCK
api_secret = "..."    # KIWOOM_REST_API_SECRET_MOCK
base_url = "https://mockapi.kiwoom.com"  # 모의투자

# 토큰 발급
url = f"{base_url}/oauth2/token"
headers = {"Content-Type": "application/json; charset=UTF-8"}
data = {
    "grant_type": "client_credentials",
    "appkey": api_key,
    "secretkey": api_secret
}
response = requests.post(url, headers=headers, json=data, timeout=30)
result = response.json()
if result.get('return_code') == 0:
    token = result['token']
```

## TOP50 조회 (ka10030)
```python
# ❌ 나쁜 예: mang_stk_incls 사용, cnt 없음
# ✅ 좋은 예: mrkt_tp, sort_tp, cnt 사용
url = f"{base_url}/api/dostk/rkinfo"
headers = {
    "Content-Type": "application/json;charset=UTF-8",
    "authorization": f"Bearer {token}",
    "api-id": "ka10030"
}
body = {
    "mrkt_tp": "0",         # 0: KOSPI
    "sort_tp": "1",         # 1: 거래량순
    "cnt": "50"              # 50개 종목
}
response = requests.post(url, headers=headers, json=body, timeout=30)
```

## 일봉 조회 (ka10031)
```python
url = f"{base_url}/api/dostk/stkinfo"
headers = {
    "Content-Type": "application/json;charset=UTF-8",
    "authorization": f"Bearer {token}",
    "api-id": "ka10031"
}
body = {
    "stk_cd": "005930",     # 종목코드
    "date_from": "20260401", # 조회시작일
    "date_to": "20260527",   # 조회종료일
    "cnt": "30"              # 30일치
}
```

## 8030 에러 (투자구분 불일치)
- 원인: TR investing_type(1:모의, 2:실전)과 API URL이 맞지 않음
- 해결: `get_environment()` 함수로 장중(prod)/장외(mock) 자동 감지
- Method 1: .env에 _PROD/_MOCK 접미사 사용 (예: KIWOOM_REST_API_KEY_MOCK)
