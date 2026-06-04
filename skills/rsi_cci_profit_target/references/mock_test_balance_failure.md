# Mock Balance Test Failure Trace

When running `test_balance_query.py` with `TRADING_ENV=mock` but using real (production) Kiwoom credentials, the OAuth token request fails with:

```
2026-06-01 14:09:15,797 - ERROR - Token request failed: 입력 값 오류입니다[8030:투자구분(실전/모의)이 달라서 Appkey를 사용할수가 없습니다]
2026-06-01 14:09:15,797 - ERROR - Failed to obtain OAuth token
Traceback (most recent call last):
  File "/home/june/trading/test_balance_query.py", line 78, in _get_token
    raise Exception(f"Token error: {msg}")
Exception: Token error: 입력 값 오류입니다[8030:투자구분(실전/모의)이 달라서 Appkey를 사용할수가 없습니다]
```

**Resolution**: Ensure that when `TRADING_ENV=mock` is set, the environment variables used are the mock-specific ones:
- `KIWOOM_REST_API_KEY_MOCK`
- `KIWOOM_REST_API_SECRET_MOCK`
- `KIWOOM_ACCOUNT_NO_MOCK`

If only the real credentials are present, either:
1. Set `TRADING_ENV=prod` to use the production server with the real keys, or
2. Provide the mock credentials (obtainable from Kiwoom API portal for demo/mock account) and keep `TRADING_ENV=mock`.

See also: `.env.example` for the expected variable names.