# Environment Verification Guide

## Critical Lesson Learned (2026-05-31)

Always verify which environment (mock/prod) your trading scripts are actually using BEFORE running any trading operations.

### Why This Matters
- Scripts read `TRADING_ENV = os.getenv('TRADING_ENV', 'mock').lower()` - defaults to 'mock' if not set!
- User discovered they thought they were in prod but were actually in mock, causing confusion
- Mixing mock/real credentials causes error 8030: "투자구분(실전/모의)이 달라서 Appkey를 사용할수가 없습니다"

### Verification Methods (Use ALL)

1. **Source .env and check TRADING_ENV**:
   ```bash
   source /home/june/trading/.env
   echo "TRADING_ENV: $TRADING_ENV"
   ```
   Should show `prod` or `mock` as intended.

2. **Check script logs directly** - MOST RELIABLE METHOD:
   ```
   [INFO] Environment: prod
   ```
   or
   ```
   [INFO] Environment: mock
   ```
   **Always look for this line in script output** - this is what the scripts actually use.

3. **Use verification script** (recommended before critical operations):
   ```bash
   python3 check_env.py
   ```
   Shows which credentials are present without exposing values.

4. **Test account access**:
   ```bash
   python3 test_balance_query.py
   ```
   Confirms real account connectivity and shows actual balances.

### Best Practice
Always verify environment FIRST - use `source .env && echo $TRADING_ENV` and check script logs for "[INFO] Environment: X" before running any trading operations.