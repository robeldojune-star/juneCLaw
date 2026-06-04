import os, sys, json, base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, '/home/june/trading')
from core.supabase_rest import SupabaseRestClient

# Load results
with open('/home/june/trading/reports/fujimoto_126_backtest_custom_swing.json') as f:
    data = json.load(f)
trades = data['results']
profitable = [t for t in trades if t.get('net_return_pct', 0) > 0]
loss = [t for t in trades if t.get('net_return_pct', 0) < 0]
best = max(profitable, key=lambda x: x['net_return_pct']) if profitable else None
worst = min(loss, key=lambda x: x['net_return_pct']) if loss else None

def fetch_bars(sb, stock_code, date_str):
    # date_str is YYYY-MM-DD
    rows = sb.get('intraday_prices', {
        'stock_code': f'eq.{stock_code}',
        'source': f'eq.kiwoom_ka10080_minute',
        'time_frame': f'eq.1min'
    }, timeout=30)
    bars = []
    for row in rows:
        ts = row['timestamp']  # e.g., "2026-05-20T09:00:00Z" or similar
        # Parse as UTC
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        dt = datetime.fromisoformat(ts)  # this will be timezone aware UTC
        # Keep as UTC
        if dt.date() == datetime.strptime(date_str, '%Y-%m-%d').date():
            bars.append((dt, float(row['close'])))
    bars.sort(key=lambda x: x[0])
    return bars

def make_svg(bars, entry_time_str, exit_time_str, entry_price, exit_price, title):
    if not bars:
        return None
    # Determine min and max price for scaling
    prices = [p for _, p in bars]
    min_price = min(prices)
    max_price = max(prices)
    if max_price == min_price:
        max_price = min_price + 1
    # Add some padding
    price_range = max_price - min_price
    y_pad = price_range * 0.1
    min_price -= y_pad
    max_price += y_pad
    # Canvas
    width, height = 800, 400
    margin = 60
    plot_w = width - 2 * margin
    plot_h = height - 2 * margin
    # Time range: use first and last bar times
    start_time = bars[0][0]
    end_time = bars[-1][0]
    # Ensure we have at least some duration
    if start_time == end_time:
        end_time = start_time + timedelta(minutes=1)
    total_seconds = (end_time - start_time).total_seconds()
    if total_seconds == 0:
        total_seconds = 60
    # Function to map
    def x_pos(t):
        return margin + ((t - start_time).total_seconds() / total_seconds) * plot_w
    def y_pos(p):
        return height - margin + ((min_price - p) / (max_price - min_price)) * plot_h  # invert y
    # Build SVG path for line
    path_cmds = []
    for i, (t, p) in enumerate(bars):
        x = x_pos(t)
        y = y_pos(p)
        if i == 0:
            path_cmds.append(f'M {x:.2f},{y:.2f}')
        else:
            path_cmds.append(f'L {x:.2f},{y:.2f}')
    path = ' '.join(path_cmds)
    # Entry and exit points
    # Parse entry_time and exit_time as naive KST, then make aware KST, convert to UTC
    KST = timezone(timedelta(hours=9))
    def parse_hm_to_utc(timestr, date_obj):
        # timestr like "14:08"
        t = datetime.strptime(timestr, '%H:%M').time()
        dt_naive = datetime.combine(date_obj, t)
        dt_kst = dt_naive.replace(tzinfo=KST)
        dt_utc = dt_kst.astimezone(timezone.utc)
        return dt_utc
    base_date = bars[0][0].date()  # date of first bar (should be same for all bars)
    entry_dt_utc = parse_hm_to_utc(entry_time_str, base_date)
    exit_dt_utc = parse_hm_to_utc(exit_time_str, base_date)
    # Find closest bar
    def find_closest(dt):
        return min(bars, key=lambda bp: abs((bp[0] - dt).total_seconds()))
    entry_point = find_closest(entry_dt_utc)
    exit_point = find_closest(exit_dt_utc)
    ex, ey = x_pos(entry_point[0]), y_pos(entry_point[1])
    xx, yx = x_pos(exit_point[0]), y_pos(exit_point[1])
    # Build SVG
    svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="white"/>
  <axes>
    <line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#ccc" stroke-width="2"/>
    <line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#ccc" stroke-width="2"/>
  </axes>
  <polyline fill="none" stroke="blue" stroke-width="2" points="{path}"/>
  <circle cx="{ex:.2f}" cy="{ey:.2f}" r="6" fill="green"/>
  <circle cx="{xx:.2f}" cy="{yx:.2f}" r="6" fill="red"/>
  <text x="{ex+8}" y="{ey-8}" font-size="12" fill="green">Entry</text>
  <text x="{xx+8}" y="{yx-8}" font-size="12" fill="red">Exit</text>
  <text x="{width/2}" y="{margin/2}" font-size="16" text-anchor="middle" fill="#333">{title}</text>
</svg>'''
    return svg

sb = SupabaseRestClient()
results = []
for label, trade in [('Best', best), ('Worst', worst)]:
    if not trade:
        continue
    bars = fetch_bars(sb, trade['stock_code'], trade['date'])
    if not bars:
        print('No bars for ' + trade['stock_code'] + ' on ' + trade['date'])
        continue
    svg = make_svg(bars,
                   trade['entry_time'],
                   trade['exit_time'],
                   trade['entry_price'],
                   trade['exit_price'],
                   f"{label} Trade: {trade['stock_code']} {trade['date']} (net {trade['net_return_pct']:.2f}%)")
    if svg:
        b64 = base64.b64encode(svg.encode('utf-8')).decode('ascii')
        data_uri = f"data:image/svg+xml;base64,{b64}"
        results.append((label, trade['stock_code'], trade['date'], data_uri))
        # Also save to file for inspection
        out_path = f"/tmp/{trade['stock_code']}_{trade['date']}_{label.lower()}.svg"
        with open(out_path, 'w') as f:
            f.write(svg)
        print("Saved " + out_path)

# Output the data URIs so they can be displayed
for label, code, date, uri in results:
    print(label + ' trade ' + code + ' ' + date + ':')
    print('MEDIA:' + uri)
    print()