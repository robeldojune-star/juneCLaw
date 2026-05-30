"""Create per-trade 1-minute charts for the current opening backtest logic.

Charts are for visual QA only. They use real Supabase intraday_prices rows:
source=kiwoom_ka10080_minute, time_frame=1min.

Current applied backtest logic being visualized:
- eligible stock-day requires complete 09:00~09:30 1-minute bars
- signal/entry trigger: first bar high breakout (same simplified logic as backtest_opening_strategy.py)
- entry price: close of first bar whose high breaks above first-bar high
- exit price: last available bar close of that stock-day
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError, num  # noqa: E402

SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"
KST = timezone(timedelta(hours=9))


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def fetch_rows(sb: SupabaseRestClient, stock_code: str, days: int, page_size: int = 1000) -> list[dict[str, Any]]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = sb.get(
            "intraday_prices",
            {
                "select": "stock_code,timestamp,time_frame,source,open,high,low,close,volume,trading_value",
                "stock_code": f"eq.{stock_code}",
                "time_frame": f"eq.{TIME_FRAME}",
                "source": f"eq.{SOURCE}",
                "timestamp": f"gte.{since}",
                "order": "timestamp.asc",
                "limit": str(page_size),
                "offset": str(offset),
            },
            timeout=60,
        )
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
        if offset > 200000:
            break
    return rows


def minute_range(start_hhmm: str, end_hhmm: str) -> set[str]:
    base = "2026-01-01"
    cur = datetime.fromisoformat(f"{base}T{start_hhmm}:00+09:00")
    end = datetime.fromisoformat(f"{base}T{end_hhmm}:00+09:00")
    out: set[str] = set()
    while cur <= end:
        out.add(cur.strftime("%H:%M"))
        cur = cur.replace(minute=cur.minute + 1) if cur.minute < 59 else cur.replace(hour=cur.hour + 1, minute=0)
    return out


def group_by_day(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ts = parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        row = dict(row)
        row["_ts_kst"] = ts
        row["_time_kst"] = ts.strftime("%H:%M")
        row["_date_kst"] = ts.strftime("%Y-%m-%d")
        by_day[row["_date_kst"]].append(row)
    for day in by_day:
        by_day[day].sort(key=lambda r: r["_ts_kst"])
    return dict(by_day)


def is_eligible_day(day_rows: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    expected = minute_range("09:00", "09:30")
    present = {str(r.get("_time_kst")) for r in day_rows}
    missing = sorted(expected - present)
    return not missing, missing


def simulate_trade(day_rows: list[dict[str, Any]], *, fee_bps: float, slippage_bps: float) -> dict[str, Any] | None:
    if len(day_rows) < 3:
        return None
    first = day_rows[0]
    opening_high = num(first.get("high"))
    if opening_high <= 0:
        return None
    entry_row = None
    for row in day_rows[1:]:
        if num(row.get("high")) > opening_high:
            entry_row = row
            break
    if entry_row is None:
        return None
    exit_row = day_rows[-1]
    entry_price = num(entry_row.get("close"))
    exit_price = num(exit_row.get("close"))
    if entry_price <= 0 or exit_price <= 0:
        return None
    gross_return = (exit_price - entry_price) / entry_price * 100.0
    cost_pct = (fee_bps + slippage_bps) / 100.0 * 2
    net_return = gross_return - cost_pct
    return {
        "stock_code": entry_row.get("stock_code"),
        "date": entry_row.get("_date_kst"),
        "opening_high": opening_high,
        "signal_time": entry_row.get("_time_kst"),
        "entry_time": entry_row.get("_time_kst"),
        "entry_price": entry_price,
        "exit_time": exit_row.get("_time_kst"),
        "exit_price": exit_price,
        "gross_return_pct": round(gross_return, 4),
        "cost_pct": round(cost_pct, 4),
        "net_return_pct": round(net_return, 4),
        "entry_timestamp": entry_row["_ts_kst"].isoformat(),
        "exit_timestamp": exit_row["_ts_kst"].isoformat(),
    }


def render_trade_html(day_rows: list[dict[str, Any]], trade: dict[str, Any], out_path: Path) -> None:
    x = [r["_ts_kst"].isoformat() for r in day_rows]
    data = {
        "x": x,
        "open": [num(r.get("open")) for r in day_rows],
        "high": [num(r.get("high")) for r in day_rows],
        "low": [num(r.get("low")) for r in day_rows],
        "close": [num(r.get("close")) for r in day_rows],
        "volume": [num(r.get("volume")) for r in day_rows],
        "trade": trade,
    }
    title = f"{trade['stock_code']} {trade['date']} 1분봉 백테스트 진입/청산"
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans CJK KR', 'Segoe UI', sans-serif; margin: 24px; background:#0b1020; color:#e5e7eb; }}
.card {{ background:#111827; border:1px solid #334155; border-radius:12px; padding:16px; margin:12px 0; }}
.badge {{ display:inline-block; padding:4px 8px; margin:2px; border-radius:999px; background:#1f2937; color:#bfdbfe; }}
.good {{ color:#86efac; }} .bad {{ color:#fca5a5; }}
#chart {{ height: 720px; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="card">
  <span class="badge">source={SOURCE}</span>
  <span class="badge">time_frame={TIME_FRAME}</span>
  <span class="badge">eligible=09:00~09:30 complete</span>
  <span class="badge">strategy=current simplified opening breakout</span>
  <p>현재 백테스트 적용 로직: <b>첫 1분봉 high</b>를 돌파하면 해당 1분봉 close로 진입, 해당 날짜 마지막 1분봉 close로 청산합니다.</p>
  <pre id="summary"></pre>
</div>
<div id="chart" class="card"></div>
<script>
const data = {json.dumps(data, ensure_ascii=False)};
const t = data.trade;
document.getElementById('summary').textContent = JSON.stringify(t, null, 2);
const candle = {{
  type: 'candlestick', name: '1분봉', x: data.x,
  open: data.open, high: data.high, low: data.low, close: data.close,
  increasing: {{line: {{color: '#ef4444'}}}}, decreasing: {{line: {{color: '#3b82f6'}}}},
}};
const volume = {{
  type:'bar', name:'volume', x:data.x, y:data.volume, yaxis:'y2', marker:{{color:'#64748b', opacity:0.35}}
}};
const entry = {{
  type:'scatter', mode:'markers+text', name:'ENTRY/SIGNAL',
  x:[t.entry_timestamp], y:[t.entry_price], text:['진입/신호'], textposition:'top center',
  marker:{{symbol:'triangle-up', size:16, color:'#22c55e', line:{{color:'#ffffff', width:1}}}}
}};
const exit = {{
  type:'scatter', mode:'markers+text', name:'EXIT',
  x:[t.exit_timestamp], y:[t.exit_price], text:['청산'], textposition:'bottom center',
  marker:{{symbol:'triangle-down', size:16, color:'#f97316', line:{{color:'#ffffff', width:1}}}}
}};
const openingLine = {{
  type:'scatter', mode:'lines', name:'첫 1분봉 high 기준선',
  x:[data.x[0], data.x[data.x.length-1]], y:[t.opening_high, t.opening_high],
  line:{{color:'#facc15', width:1.5, dash:'dot'}}
}};
Plotly.newPlot('chart', [candle, volume, openingLine, entry, exit], {{
  paper_bgcolor:'#111827', plot_bgcolor:'#111827', font:{{color:'#e5e7eb'}},
  title:'1분봉 캔들 + 진입/청산 마커',
  xaxis:{{rangeslider:{{visible:false}}, gridcolor:'#1f2937'}},
  yaxis:{{title:'가격', gridcolor:'#1f2937'}},
  yaxis2:{{title:'거래량', overlaying:'y', side:'right', showgrid:false}},
  shapes:[
    {{type:'rect', xref:'x', yref:'paper', x0:`${{t.date}}T09:00:00+09:00`, x1:`${{t.date}}T09:30:00+09:00`, y0:0, y1:1, fillcolor:'#2563eb', opacity:0.08, line:{{width:0}}}}
  ],
  annotations:[
    {{xref:'x', yref:'paper', x:`${{t.date}}T09:30:00+09:00`, y:1.02, text:'09:00~09:30 eligible window', showarrow:false, font:{{color:'#93c5fd'}}}}
  ],
  margin:{{t:60, l:70, r:70, b:50}}
}}, {{responsive:true}});
</script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")


def render_index(trades: list[dict[str, Any]], links: list[tuple[dict[str, Any], str]], out_path: Path) -> None:
    rows = []
    for trade, rel in links:
        cls = "good" if trade["net_return_pct"] > 0 else "bad"
        rows.append(
            f"<tr><td>{html.escape(str(trade['stock_code']))}</td><td>{html.escape(str(trade['date']))}</td>"
            f"<td>{trade['entry_time']}</td><td>{trade['entry_price']:,.0f}</td>"
            f"<td>{trade['exit_time']}</td><td>{trade['exit_price']:,.0f}</td>"
            f"<td class='{cls}'>{trade['net_return_pct']:.4f}%</td><td><a href='{html.escape(rel)}'>차트</a></td></tr>"
        )
    html_text = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>백테스트 거래 차트 인덱스</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans CJK KR','Segoe UI',sans-serif;margin:24px;background:#0b1020;color:#e5e7eb}} table{{border-collapse:collapse;width:100%;background:#111827}} th,td{{border:1px solid #334155;padding:8px;text-align:right}} th{{background:#1f2937}} td:first-child,td:nth-child(2),td:last-child{{text-align:center}} a{{color:#93c5fd}} .good{{color:#86efac}} .bad{{color:#fca5a5}}</style>
</head><body><h1>백테스트 거래 차트 인덱스</h1><p>현재 적용된 단순 오프닝 돌파 백테스트의 거래별 1분봉 차트입니다.</p><table><thead><tr><th>종목</th><th>날짜</th><th>진입시각</th><th>진입가</th><th>청산시각</th><th>청산가</th><th>순수익률</th><th>차트</th></tr></thead><tbody>{''.join(rows)}</tbody></table></body></html>"""
    out_path.write_text(html_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930", "000660", "035420", "005380", "068270"])
    parser.add_argument("--days", type=int, default=130)
    parser.add_argument("--fee-bps", type=float, default=23.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--out-dir", default="reports/backtest_trade_charts")
    args = parser.parse_args()

    blocks: list[str] = []
    alerts: list[str] = []
    trades: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    try:
        sb = SupabaseRestClient()
        for code in args.stock_codes:
            rows = fetch_rows(sb, code, args.days)
            for day, day_rows in group_by_day(rows).items():
                eligible, missing = is_eligible_day(day_rows)
                if not eligible:
                    continue
                trade = simulate_trade(day_rows, fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
                if trade:
                    trades.append((trade, day_rows))
    except SupabaseRestError as exc:
        blocks.append(str(exc))

    trades.sort(key=lambda x: (str(x[0].get("date")), str(x[0].get("stock_code"))))
    selected = trades[: max(0, args.limit)]
    out_dir = PROJECT_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    links: list[tuple[dict[str, Any], str]] = []
    for trade, day_rows in selected:
        filename = f"{trade['date']}_{trade['stock_code']}_entry_exit.html"
        render_trade_html(day_rows, trade, out_dir / filename)
        links.append((trade, filename))
    render_index([t for t, _ in selected], links, out_dir / "index.html")

    if not trades and not blocks:
        alerts.append("no_backtest_trades_found")
    out = {
        "ok": not blocks,
        "stage": "create_backtest_trade_charts",
        "summary": {
            "source": SOURCE,
            "time_frame": TIME_FRAME,
            "stock_codes": args.stock_codes,
            "days": args.days,
            "total_trades_found": len(trades),
            "charts_created": len(selected),
            "index_path": str(out_dir / "index.html"),
            "fee_bps_one_way": args.fee_bps,
            "slippage_bps_one_way": args.slippage_bps,
        },
        "sample_trades": [t for t, _ in selected[:10]],
        "blocking_conditions": blocks,
        "alerts": alerts,
        "next_actions": [
            "인덱스 HTML에서 종목/날짜별 진입·청산 마커를 확인하세요.",
            "현재 차트는 기존 단순 백테스트 로직을 시각화한 것이며, 실제 OR10/OR30 range 분리 로직은 별도 개선이 필요합니다.",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blocks else 2


if __name__ == "__main__":
    raise SystemExit(main())
