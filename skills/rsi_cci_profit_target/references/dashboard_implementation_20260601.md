# Dashboard Implementation (2026-06-01)

## Overview
Added a simple web dashboard to visualize strategy signals in real-time using Flask.

## Files Created
- `/home/june/trading/dashboard/app.py` - Flask server
- `/home/june/trading/dashboard/templates/index.html` - HTML/JS interface
- `/home/june/trading/dashboard/data/signals.csv` - Signal log CSV
- Modified `/home/june/trading/scripts/run_strategy.py` to log signals

## Dashboard Features
- Real-time signal table (BUY/SELL with price and timestamp)
- Cumulative profit display
- Auto-refresh every 10 seconds
- Bootstrap 5 + Chart.js for styling

## URL
Accessible at: `http://<server_ip>:5000` (default port 5000)

## Implementation Details
### app.py
Simple Flask app with two routes:
- `/` - serves the HTML dashboard
- `/api/signals` - returns JSON of recent signals (last 50)

### index.html
- Uses Bootstrap 5 for responsive layout
- Chart.js for cumulative profit visualization
- JavaScript fetches `/api/signals` every 10 seconds and updates table/chart

### Signal Logging
Added `log_signal()` function to `run_strategy.py`:
- Appends to `dashboard/data/signals.csv`
- Columns: time (YYYYMMDDHHMMSS), stock, type (BUY/SELL), price, profit (%)
- Creates directory and file if missing

### Integration
The dashboard runs as a background process:
```bash
cd /home/june/trading/dashboard && python3 app.py &
```
Accessible at http://192.168.219.104:5000 (based on current server IP)

## Usage
1. Start dashboard: `cd dashboard && python3 app.py &`
2. Run strategy: `python3 scripts/run_strategy.py --env mock --execute --quantity 1`
3. View signals in real-time at the dashboard URL

## Notes
- For production use, consider using a proper WSGI server (gunicorn/uWSGI)
- Dashboard is lightweight and intended for internal monitoring only
- Signal CSV grows over time; consider rotation or limits for long-term use