import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from core.supabase_rest import SupabaseRestClient

sb = SupabaseRestClient()
all_dates = set()
offset = 0
limit = 1000
while True:
    resp = sb.get('intraday_prices', {
        'select': 'timestamp',
        'source': 'eq.kiwoom_ka10080_minute',
        'time_frame': 'eq.1min',
        'order': 'timestamp.asc',
        'limit': str(limit),
        'offset': str(offset)
    }, timeout=30)
    if not isinstance(resp, list):
        print('Error:', resp)
        break
    if not resp:
        break
    for r in resp:
        ts = r.get('timestamp')
        if ts:
            # extract date part YYYY-MM-DD
            date = ts.split('T')[0] if 'T' in ts else ts[:10]
            all_dates.add(date)
    offset += limit
    if len(resp) < limit:
        break
print('Total rows scanned:', offset)
print('Unique dates:', len(all_dates))
if len(all_dates) > 0:
    sorted_dates = sorted(all_dates)
    print('First 10 dates:', sorted_dates[:10])
    print('Last 10 dates:', sorted_dates[-10:])
else:
    print('No dates found')