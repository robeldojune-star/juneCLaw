# Trade Visualization for Trading Strategies

## Overview
When external plotting libraries cannot be installed due to environment restrictions (e.g., permission issues, externally managed Python environments), custom SVG generation provides a lightweight alternative for visualizing trade entry/exit points on price charts.

## Problem
- Cannot install matplotlib or other plotting libraries due to permission restrictions
- Need to visualize trade signals, entry points, exit points, and stop-loss/take-profit levels
- Want to avoid external dependencies while maintaining clear visual representation

## Solution: Custom SVG Generation
Generate SVG charts directly using Python's string formatting capabilities. This approach:
- Requires no external dependencies beyond standard library
- Produces lightweight, scalable vector graphics
- Can be embedded directly in reports or viewed in any browser
- Allows precise control over visual elements

## Implementation Pattern

### 1. Data Collection
Fetch intraday price data (1-minute bars) for the target date and stock:
```python
from core.kiwoom_client import KiwoomAPIClient
from core.supabase_rest import SupabaseRestClient

# Get 1-minute bars for the trading day
kb = KiwoomAPIClient.from_env()
df_1m = kb.get_1min_bars(stock_code, trade_date)
```

### 2. SVG Generation Components
Create reusable functions for common chart elements:

#### A. Basic SVG Container
```python
def create_svg_chart(width=800, height=600, padding=50):
    return f'''<svg width="{width}" height="{height}" 
                viewBox="0 0 {width} {height}" 
                xmlns="http://www.w3.org/2000/svg">
                <style>
                    .price-line {{ stroke: #000; stroke-width: 1; }}
                    .volume-bar {{ fill: rgba(128,128,128,0.3); }}
                    .entry-point {{ fill: green; }}
                    .exit-point {{ fill: red; }}
                    .stop-loss {{ stroke: orange; stroke-width: 2; }}
                    .take-profit {{ stroke: blue; stroke-width: 2; }}
                    .grid-line {{ stroke: #eee; stroke-width: 0.5; }}
                    .text {{ font-family: sans-serif; font-size: 12px; }}
                </style>
'''
```

#### B. Price Data Scaling
```python
def scale_price(price, min_price, max_price, chart_height, padding):
    """Scale price to pixel coordinates (Y increases downward in SVG)"""
    price_range = max_price - min_price
    if price_range == 0:
        return chart_height // 2
    return padding + (chart_height - 2 * padding) * (1 - (price - min_price) / price_range)

def scale_time(timestamp, first_timestamp, last_timestamp, chart_width, padding):
    """Scale timestamp to pixel coordinates"""
    time_range = last_timestamp - first_timestamp
    if time_range == 0:
        return padding
    return padding + (chart_width - 2 * padding) * ((timestamp - first_timestamp) / time_range)
```

#### C. Drawing Price Line
```python
def draw_price_line(svg_elements, timestamps, prices, 
                   min_price, max_price, first_ts, last_ts,
                   width, height, padding):
    points = []
    for ts, price in zip(timestamps, prices):
        x = scale_time(ts, first_ts, last_ts, width, padding)
        y = scale_price(price, min_price, max_price, height, padding)
        points.append(f"{x},{y}")
    
    if len(points) >= 2:
        svg_elements.append(f'<polyline points="{ " ".join(points) }" '
                          f'class="price-line" fill="none" />')
```

#### D. Adding Trade Markers
```python
def add_entry_marker(svg_elements, timestamp, price, 
                    min_price, max_price, first_ts, last_ts,
                    width, height, padding, label="ENTRY"):
    x = scale_time(timestamp, first_ts, last_ts, width, padding)
    y = scale_price(price, min_price, max_price, height, padding)
    svg_elements.extend([
        f'<circle cx="{x}" cy="{y}" r="6" class="entry-point" />',
        f'<text x="{x+8}" y="{y-8}" class="text">{label}</text>'
    ])

def add_exit_marker(svg_elements, timestamp, price, 
                   min_price, max_price, first_ts, last_ts,
                   width, height, padding, label="EXIT"):
    x = scale_time(timestamp, first_ts, last_ts, width, padding)
    y = scale_price(price, min_price, max_price, height, padding)
    svg_elements.extend([
        f'<circle cx="{x}" cy="{y}" r="6" class="exit-point" />',
        f'<text x="{x+8}" y="{y+20}" class="text">{label}</text>'
    ])
```

#### E. Volume Bars (Optional)
```python
def add_volume_bars(svg_elements, timestamps, volumes,
                   min_volume, max_volume, first_ts, last_ts,
                   width, height, padding, volume_height_ratio=0.3):
    vol_chart_height = height * volume_height_ratio
    vol_padding = padding * 0.5
    
    for ts, vol in zip(timestamps, volumes):
        if vol <= 0:
            continue
        x = scale_time(ts, first_ts, last_ts, width, padding)
        bar_width = max(1, (width - 2 * padding) / len(timestamps) * 0.8)
        bar_height = (vol / max_volume) * vol_chart_height if max_volume > 0 else 0
        y = height - padding - bar_height
        
        svg_elements.append(f'<rect x="{x - bar_width/2}" y="{y}" '
                          f'width="{bar_width}" height="{bar_height}" '
                          f'class="volume-bar" />')
```

### 3. Complete SVG Generation Workflow
```python
def generate_trade_chart(stock_code, trade_date, entry_time, exit_time,
                        entry_price, exit_price, stop_loss=None, take_profit=None):
    # 1. Fetch 1-minute data
    kb = KiwoomAPIClient.from_env()
    df_1m = kb.get_1min_bars(stock_code, trade_date)
    
    if df_1m.empty:
        raise ValueError(f"No 1-minute data for {stock_code} on {trade_date}")
    
    # 2. Prepare data
    timestamps = [int(pd.Timestamp(ts).timestamp()) for ts in df_1m['timestamp']]
    prices = df_1m['close'].tolist()
    volumes = df_1m['volume'].tolist()
    
    min_price, max_price = min(prices), max(prices)
    min_volume, max_volume = min(volumes), max(volumes)
    first_ts, last_ts = timestamps[0], timestamps[-1]
    
    # 3. Chart dimensions
    width, height, padding = 1000, 600, 60
    
    # 4. Generate SVG
    svg_elements = [create_svg_chart(width, height, padding)]
    
    # Add grid lines (optional)
    # ... add horizontal/vertical grid lines ...
    
    # Add price line
    draw_price_line(svg_elements, timestamps, prices,
                   min_price, max_price, first_ts, last_ts,
                   width, height, padding)
    
    # Add volume bars (bottom section)
    add_volume_bars(svg_elements, timestamps, volumes,
                   min_volume, max_volume, first_ts, last_ts,
                   width, height, padding)
    
    # Add trade markers
    add_entry_marker(svg_elements, 
                    int(pd.Timestamp(entry_time).timestamp()), entry_price,
                    min_price, max_price, first_ts, last_ts,
                    width, height, padding, "ENTRY")
    
    add_exit_marker(svg_elements,
                   int(pd.Timestamp(exit_time).timestamp()), exit_price,
                   min_price, max_price, first_ts, last_ts,
                   width, height, padding, "EXIT")
    
    # Add stop-loss/take-profit lines if provided
    if stop_loss:
        y_sl = scale_price(stop_loss, min_price, max_price, height, padding)
        svg_elements.append(f'<line x1="{padding}" x2="{width-padding}" '
                          f'y1="{y_sl}" y2="{y_sl}" class="stop-loss" />')
        svg_elements.append(f'<text x="{width-padding+5}" y="{y_sl-5}" '
                          f'class="text">SL: {stop_loss}</text>')
    
    if take_profit:
        y_tp = scale_price(take_profit, min_price, max_price, height, padding)
        svg_elements.append(f'<line x1="{padding}" x2="{width-padding}" '
                          f'y1="{y_tp}" y2="{y_tp}" class="take-profit" />')
        svg_elements.append(f'<text x="{width-padding+5}" y="{y_tp-5}" '
                          f'class="text">TP: {take_profit}</text>')
    
    # Close SVG
    svg_elements.append('</svg>')
    
    return '\n'.join(svg_elements)
```

## Usage Example
```python
# Generate chart for a profitable trade
svg_chart = generate_trade_chart(
    stock_code="017670",  # SK Telecom
    trade_date="2026-05-29",
    entry_time="2026-05-29 09:35:00",
    exit_time="2026-05-29 10:15:00",
    entry_price=52000,
    exit_price=53200,
    stop_loss=51480,  # -1% stop loss
    take_profit=54080  # +4% take profit
)

# Save to file
with open("/tmp/trade_017670_2026-05-29.svg", "w") as f:
    f.write(svg_chart)

# Or encode as base64 for embedding
import base64
b64_svg = base64.b64encode(svg_chart.encode()).decode()
html_embed = f'<img src="data:image/svg+xml;base64,{b64_svg}" alt="Trade Chart" />'
```

## Best Practices
1. **Handle Missing Data Gracefully**: Check if intraday data exists before generating chart
2. **Timezone Awareness**: Critical for Korean market - ensure all timestamps are converted to KST (UTC+9) before scaling. Common bug: subtracting offset-naive and offset-aware datetimes (as seen in plot_trade.py failure). Always parse timestamps with timezone info explicitly.
3. **Fallback Mechanism**: If 1-minute data unavailable, fall back to daily data with appropriate warnings
4. **Accessibility**: Consider adding ARIA labels or descriptive titles for screen readers
5. **Performance**: For large datasets, consider sampling points or using polyline simplification
6. **Consistent Styling**: Define color schemes and stroke widths as constants for easy theming
7. **Clear Marking**: Always visually distinguish entry (green circle) and exit (red circle) points with labels
8. **Context Lines**: Consider adding horizontal lines for stop-loss/take-profit levels when they influence the trade outcome
9. **Validation**: Always verify generated SVG by viewing in browser or saving to file to catch rendering issues early

## Integration with Trading System
This visualization approach can be integrated into:
- Post-trade analysis scripts
- Backtest report generation
- Real-time monitoring dashboards (as lightweight charts)
- Trade alert systems (embedding charts in notifications)

## Files Created in This Session
- `/home/june/trading/plot_trade.py` - Initial attempt (had datetime timezone bug)
- `/home/june/trading/plot_trade2.py` - Working version that generated SVG for best trade
- `/tmp/017670_2026-05-29_best.svg` - Successful visualization of profitable trade

## Advantages of This Approach
- Zero external dependencies
- Works in restricted environments
- Produces publication-quality vector graphics
- Easy to customize and extend
- Can be generated programmatically without interactive tools

## Limitations
- More development effort than using established plotting libraries
- Limited to 2D charts (no interactive features without JavaScript)
- Requires manual implementation of chart elements (axes, legends, etc.)