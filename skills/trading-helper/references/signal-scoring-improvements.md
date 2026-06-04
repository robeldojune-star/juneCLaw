# Signal Scoring Improvements

Learnings from running compute_signal_score.py in production environment.

## 1. Rate Limiting Mitigation for Kiwoom API

When calling Kiwoom ka10005 (foreign/institutional net buying) for multiple stocks, 429 rate-limit errors were encountered.

### Recommended Solutions:
- Add per-request delay: `time.sleep(0.5)` between API calls
- Implement exponential backoff for retry logic
- Limit number of stocks processed per run (use --top or --limit-stocks)
- Consider batching requests if Kiwoom API supports it

### Example Implementation:
```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_foreign_institutional_flow(stock_code, date):
    """Get foreign+institutional net buying with retry logic"""
    time.sleep(0.5)  # Base delay to avoid rate limits
    # ... actual API call ...
    return flow_data
```

## 2. Disclosure Score Enhancement

Disclosure scores were zero for many stocks due to lack of same-day disclosures.

### Recommended Solutions:
- Consider prior-day disclosures (t-1 effect) as market often reacts after close
- Use rolling window (e.g., last 3 days) for disclosure scoring
- Weight recent disclosures higher than older ones

### Example Implementation:
```python
def calculate_disclosure_score(stock_code, target_date):
    """Calculate disclosure score with t-1 and rolling window consideration"""
    # Get disclosures for target_date and previous 2 days
    disclosure_dates = [
        target_date,
        get_previous_trading_day(target_date),
        get_previous_trading_day(get_previous_trading_day(target_date))
    ]
    
    total_score = 0
    for i, date in enumerate(disclosure_dates):
        # Weight: today=100%, yesterday=60%, day before=30%
        weight = [1.0, 0.6, 0.3][i]
        daily_score = get_disclosure_score_for_date(stock_code, date)
        total_score += daily_score * weight
    
    return total_score
```

## 3. Score Component Normalization

Raw scores from different domains (disclosure, flow, volume) have different scales, causing imbalance in weighted sum.

### Recommended Solutions:
- Normalize each component to 0-100 scale before applying weights
- Use historical data to determine appropriate scaling factors
- Consider using percentiles or z-score normalization

### Example Implementation:
```python
def normalize_score(raw_score, min_val, max_val):
    """Normalize raw score to 0-100 scale"""
    if max_val == min_val:
        return 50  # Avoid division by zero
    return max(0, min(100, (raw_score - min_val) * 100 / (max_val - min_val)))

# In compute_total_score:
disclosure_norm = normalize_score(disclosure_raw, 0, 150)  # Based on observed max
flow_norm = normalize_score(flow_raw, -50, 50)  # Based on typical range
volume_norm = normalize_score(volume_raw, 0, 30)  # Based on observed max

total_score = (
    disclosure_norm * 0.4 +
    flow_norm * 0.4 +
    volume_norm * 0.2
)
```

## 4. Script Enhancements for compute_signal_score.py

Add command-line arguments to control behavior:
- `--delay`: Seconds to wait between Kiwoom API calls (default: 0.5)
- `--limit-stocks`: Maximum number of stocks to process
- `--use-previous-disclosure`: Flag to enable t-1 disclosure consideration
- `--normalize`: Flag to enable score normalization

These improvements address the specific issues encountered when running the signal scoring script in production environment with real Kiwoom/OpenDART/Supabase data.