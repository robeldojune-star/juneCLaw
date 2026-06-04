import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
sb = SupabaseRestClient()
# Try to get a few rows for 005930 on 2026-05-29
rows = sb.get('intraday_prices', {
    'stock_code': 'eq.005930',
    'source': 'eq.kiwoom_ka10080_minute',
    'time_frame': 'eq.1min',
    # Use a date filter? The column is timestamp, we need to filter by date.
    # We'll use a range: timestamp >= '2026-05-29T00:00:00' and timestamp < '2026-05-30T00:00:00'
}, timeout=30)
print(f'Number of rows: {len(rows)}')
if rows:
    print('First row:', rows[0])
    print('Last row:', rows[-1])