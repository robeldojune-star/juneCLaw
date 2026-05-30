"""Generate visual QA charts for Kiwoom ka10080 historical 1-minute bars."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, num  # noqa: E402

SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"
KST = ZoneInfo("Asia/Seoul")


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(KST)
    except ValueError:
        return None


def fetch_rows(stock_code: str, limit: int) -> list[dict[str, Any]]:
    sb = SupabaseRestClient()
    rows: list[dict[str, Any]] = []
    offset = 0
    page_size = min(1000, max(1, limit))
    while len(rows) < limit:
        page = sb.get(
            "intraday_prices",
            {
                "select": "stock_code,timestamp,open,high,low,close,volume,source,time_frame",
                "stock_code": f"eq.{stock_code}",
                "source": f"eq.{SOURCE}",
                "time_frame": f"eq.{TIME_FRAME}",
                "order": "timestamp.asc",
                "limit": str(min(page_size, limit - len(rows))),
                "offset": str(offset),
            },
            timeout=60,
        )
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-code", default="005930")
    parser.add_argument("--limit", type=int, default=3000)
    parser.add_argument("--out", default="reports/ka10080_minute_quality_005930.html")
    args = parser.parse_args()

    rows = fetch_rows(args.stock_code, args.limit)
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    points = []
    for row in rows:
        ts = parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        item = {
            "ts": ts,
            "day": ts.strftime("%Y-%m-%d"),
            "time": ts.strftime("%H:%M"),
            "open": num(row.get("open")),
            "high": num(row.get("high")),
            "low": num(row.get("low")),
            "close": num(row.get("close")),
            "volume": num(row.get("volume")),
        }
        by_day[item["day"]].append(item)
        points.append(item)

    day_cards = []
    for day, items in sorted(by_day.items()):
        times = sorted({x["time"] for x in items if "09:00" <= x["time"] <= "15:30"})
        day_cards.append({
            "day": day,
            "rows": len(items),
            "regular_unique_minutes": len(times),
            "first": min(x["time"] for x in items),
            "last": max(x["time"] for x in items),
            "min_close": min(x["close"] for x in items),
            "max_close": max(x["close"] for x in items),
        })

    data_json = json.dumps(points, ensure_ascii=False, default=str)
    cards_json = json.dumps(day_cards, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang='ko'>
<head>
<meta charset='utf-8'>
<title>ka10080 1분봉 품질 차트 - {args.stock_code}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans CJK KR', 'Segoe UI', sans-serif; margin: 24px; background: #0b1020; color: #e5e7eb; }}
.card {{ background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin: 12px 0; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.badge {{ display: inline-block; padding: 3px 8px; border-radius: 999px; background: #1f2937; color: #93c5fd; margin-right: 6px; }}
.warn {{ color: #fbbf24; }}
.ok {{ color: #86efac; }}
#chart, #heatmap {{ height: 520px; }}
</style>
</head>
<body>
<h1>ka10080 과거 1분봉 품질 차트</h1>
<div class='card'>
  <span class='badge'>stock_code={args.stock_code}</span>
  <span class='badge'>source={SOURCE}</span>
  <span class='badge'>time_frame={TIME_FRAME}</span>
  <p>목적: 캔들/거래량 흐름과 날짜별 minute coverage를 시각적으로 확인해 빈 구간, 이상 가격, 데이터 끊김을 찾는다.</p>
</div>
<div id='chart' class='card'></div>
<div id='heatmap' class='card'></div>
<div class='card'><h2>날짜별 요약</h2><div id='cards' class='grid'></div></div>
<script>
const rows = {data_json};
const cards = {cards_json};
const x = rows.map(r => r.ts);
const candle = {{
  type: 'candlestick', x,
  open: rows.map(r => r.open), high: rows.map(r => r.high), low: rows.map(r => r.low), close: rows.map(r => r.close),
  increasing: {{line: {{color: '#ef4444'}}}}, decreasing: {{line: {{color: '#3b82f6'}}}},
  name: '1분봉'
}};
const volume = {{
  type: 'bar', x, y: rows.map(r => r.volume), name: 'volume', yaxis: 'y2', marker: {{color: '#64748b', opacity: 0.35}}
}};
Plotly.newPlot('chart', [candle, volume], {{
  paper_bgcolor: '#111827', plot_bgcolor: '#111827', font: {{color: '#e5e7eb'}},
  title: '캔들 + 거래량', xaxis: {{rangeslider: {{visible: false}}, gridcolor: '#1f2937'}},
  yaxis: {{title: '가격', gridcolor: '#1f2937'}},
  yaxis2: {{title: '거래량', overlaying: 'y', side: 'right', showgrid: false}},
  margin: {{t: 50, l: 60, r: 60, b: 40}}
}}, {{responsive: true}});

const days = [...new Set(rows.map(r => r.day))].sort();
const minutes = [];
for (let h=9; h<=15; h++) {{
  const end = h === 15 ? 30 : 59;
  const start = h === 9 ? 0 : 0;
  for (let m=start; m<=end; m++) minutes.push(`${{String(h).padStart(2,'0')}}:${{String(m).padStart(2,'0')}}`);
}}
const present = new Set(rows.filter(r => r.time >= '09:00' && r.time <= '15:30').map(r => `${{r.day}}|${{r.time}}`));
const z = days.map(d => minutes.map(m => present.has(`${{d}}|${{m}}`) ? 1 : 0));
Plotly.newPlot('heatmap', [{{type:'heatmap', x: minutes, y: days, z, colorscale: [[0,'#7f1d1d'],[1,'#22c55e']], showscale: false}}], {{
  paper_bgcolor: '#111827', plot_bgcolor: '#111827', font: {{color: '#e5e7eb'}},
  title: '정규장 09:00~15:30 minute coverage heatmap — 초록=있음, 빨강=없음',
  xaxis: {{tickangle: -45, nticks: 24}}, yaxis: {{autorange: 'reversed'}}, margin: {{t: 70, l: 90, r: 30, b: 90}}
}}, {{responsive: true}});

const cardsDiv = document.getElementById('cards');
for (const c of cards) {{
  const cls = c.regular_unique_minutes >= 300 ? 'ok' : 'warn';
  cardsDiv.insertAdjacentHTML('beforeend', `<div class='card'><b>${{c.day}}</b><br>rows=${{c.rows}}<br><span class='${{cls}}'>regular_minutes=${{c.regular_unique_minutes}}</span><br>time=${{c.first}}~${{c.last}}<br>close=${{c.min_close.toLocaleString()}}~${{c.max_close.toLocaleString()}}</div>`);
}}
</script>
</body>
</html>
"""
    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out_path), "rows": len(rows), "days": len(day_cards)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
