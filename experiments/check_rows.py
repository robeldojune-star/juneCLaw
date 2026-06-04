import sys
sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient
sb = SupabaseRestClient()
# Count total rows for kiwoom_ka10080_minute
resp = sb.get('intraday_prices', {'select': 'count', 'source': 'eq.kiwoom_ka10080_minute', 'time_frame': 'eq.1min'}, timeout=30)
print('Total rows:', resp)
# Get distinct dates via a sample (limit 5000) to estimate
resp2 = sb.get('intraday_prices', {'select': 'timestamp', 'source': 'eq.kiwoom_ka10080_minute', 'time_frame': 'eq.1min', 'order': 'timestamp.asc', 'limit': '5000'}, timeout=30)
if isinstance(resp2, list):
    dates = set()
    for r in resp2:
        ts = r.get('timestamp')
        if ts:
            date = ts.split('T')[0] if 'T' in ts else ts[:10]
            dates.add(date)
    print('Unique dates (from sample up to 5000):', len(dates))
    if len(dates) > 0:
        sorted_dates = sorted(dates)
        print('First 5:', sorted_dates[:5])
        print('Last 5:', sorted_dates[-5:])
else:
    print('resp2:', resp2)