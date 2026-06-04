# Mock Test Success (2026-06-01)

**Command run**: 
```bash
cd /home/june/trading && python3 scripts/run_strategy.py --env mock --stock 042660 --lookback 5 --profit-target 1.5
```

**Output summary**:
- Loaded environment from: /home/june/trading/envs/mock/.env
- Kiwoom client initialized for env: mock
- Detected BUY/SELL signals:
  - 20260522 BUY at 11:50 price 121300
  - 20260526 BUY at 12:03 price 135300
  - 20260527 BUY at 12:19 price 134800 → SELL at 13:36 price 136900 profit 1.56%
  - 20260527 BUY at 15:16 price -134500 (note: raw price signed, strategy uses abs)
  - 20260601 BUY at 09:00 price 125500 → SELL at 09:17 price 127700 profit 1.75%
  - 20260601 BUY at 10:36 price 127700 (no exit by target)
- Total trades executed/simulated: 2
- Win rate: 100.00%
- Average profit per trade: 1.66%
- Profits: [1.56%, 1.75%]

**Notes**:
- The strategy uses absolute values for price comparisons, so the negative price in the log does not affect logic.
- Two trades reached the +1.5% profit target and were closed.
- No orders were placed because `--execute` flag was not used (dry‑run).