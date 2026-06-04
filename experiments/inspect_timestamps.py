import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
sb = SupabaseRestClient()
# Get a few rows with timestamp and source
resp = sb.get('intraday_prices', {'select': 'stock_code,timestamp,source,time_frame', 'source': 'eq.kiwoom_ka10080_minute', 'time_frame': 'eq.1min', 'order': 'timestamp.asc', 'limit': '20'}, timeout=30)
print('First 20 rows:')
for r in resp:
    print(r)
# Get last 20 rows
resp2 = sb.get('intraday_prices', {'select': 'stock_code,timestamp,source,time_frame', 'source': 'eq.kiwoom_ka10080_minute', 'time_frame': 'eq.1min', 'order': 'timestamp.desc', 'limit': '20'}, timeout=30)
print('\\nLast 20 rows:')
for r in resp2:
    print(r)