"""Create original-format interactive HTML charts with entry/exit + signal markers.

This keeps the preferred reports/backtest_trade_charts/*_entry_exit.html style:
- Dark Plotly HTML page
- Candlestick chart
- Volume display
- Summary card
- Index table

Enhancements:
- Korean stock names in title/index
- Low-area BUY signal markers
- High-area SELL signal markers
- Shigeru/Fujimoto STAGE1/2/3 markers
- Existing OR entry and exit markers

Read-only: uses real ka10080 1-minute rows; does not write orders/positions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from analyze_extreme_signal_markers import (  # noqa: E402
    KST,
    SOURCE,
    TIME_FRAME,
    fetch_bars,
    fetch_stock_days,
    fetch_stock_names,
    first_or_trade,
    make_markers,
    summarize_markers,
)
from core.supabase_rest import read_env  # noqa: E402


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def marker_trace_payload(markers: list[Any], x_by_hhmm: dict[str, str]) -> dict[str, list[Any]]:
    return {
        "x": [x_by_hhmm.get(m.hhmm, m.hhmm) for m in markers],
        "y": [m.price for m in markers],
        "text": [m.label for m in markers],
        "hover": [
            f"{m.label}<br>시각={m.hhmm}<br>가격={m.price:,.0f}<br>score={m.score}<br>최저가거리={m.dist_low_pct:.2f}%<br>최고가거리={m.dist_high_pct:.2f}%"
            for m in markers
        ],
        "score": [m.score for m in markers],
    }


def select_display_markers(markers: list[Any], *, side: str, limit: int = 8) -> list[Any]:
    """Keep the chart readable: only show low-rebound-near signals.

    For signal-review charts, the user wants to inspect whether Shigeru can be
    upgraded around actual low-rebound timing. Therefore the visual chart should
    show only the strongest "저점반등" markers near the day low, not every RSI/MACD
    or sell-side candidate.
    """
    if side == "buy":
        ranked = [
            m
            for m in markers
            if m.label == "저점반등" and m.dist_low_pct is not None and m.dist_low_pct <= 0.7
        ]
        ranked.sort(key=lambda m: (-m.score, m.dist_low_pct, m.idx))
    else:
        ranked = []
        ranked.sort(key=lambda m: (-m.score, m.dist_high_pct, m.idx))
    selected: list[Any] = []
    for marker in ranked:
        if all(abs(marker.idx - prior.idx) >= 10 for prior in selected):
            selected.append(marker)
        if len(selected) >= limit:
            break
    return sorted(selected, key=lambda m: m.idx)


def render_trade_html(stock_code: str, stock_name: str, trading_day: Any, bars: list[Any], markers: dict[str, Any], out_path: Path, *, or_window: int) -> dict[str, Any]:
    trade = first_or_trade(bars, or_window)
    exit_bar = bars[-1]
    all_buy = markers["buy_markers"]
    all_sell = markers["sell_markers"]
    # Display only low-rebound-near buy signals. Counts still show all candidates.
    buy = select_display_markers(all_buy, side="buy", limit=8)
    sell: list[Any] = []
    stage: list[Any] = []
    x = [b.ts.isoformat() for b in bars]
    x_by_hhmm = {b.hhmm: b.ts.isoformat() for b in bars}
    payload = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "date": str(trading_day),
        "source": SOURCE,
        "time_frame": TIME_FRAME,
        "x": x,
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
        "day_low": markers["day_low"],
        "day_high": markers["day_high"],
        "buy": marker_trace_payload(buy, x_by_hhmm),
        "sell": marker_trace_payload(sell, x_by_hhmm),
        "stage": marker_trace_payload(stage, x_by_hhmm),
        "trade": {**trade, "x": x_by_hhmm.get(trade["hhmm"], trade["hhmm"])} if trade else None,
        "exit": {"time": exit_bar.hhmm, "x": exit_bar.ts.isoformat(), "price": exit_bar.close},
        "counts": {"buy": len(all_buy), "sell": len(all_sell), "stage": len(stage), "buy_displayed": len(buy), "sell_displayed": len(sell)},
    }
    title = f"{stock_name} {trading_day} 1분봉 백테스트 진입/청산 + 신호"
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{esc(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans CJK KR', 'NanumSquareRound', 'Segoe UI', sans-serif; margin: 24px; background:#0b1020; color:#e5e7eb; }}
.card {{ background:#111827; border:1px solid #334155; border-radius:12px; padding:16px; margin:12px 0; }}
.badge {{ display:inline-block; padding:4px 8px; margin:2px; border-radius:999px; background:#1f2937; color:#bfdbfe; }}
.good {{ color:#86efac; }} .bad {{ color:#fca5a5; }} .warn {{ color:#fde68a; }}
a {{ color:#93c5fd; text-decoration:none; }} a:hover {{ text-decoration:underline; }}
#chart {{ height: 820px; }}
pre {{ white-space:pre-wrap; color:#cbd5e1; }}
</style>
</head>
<body>
<p><a href="index_signal_review.html">← 신호검토 인덱스</a> · <a href="index.html">기존 entry/exit 인덱스</a></p>
<h1>{esc(title)}</h1>
<div class="card">
  <span class="badge">종목={esc(stock_name)} ({esc(stock_code)})</span>
  <span class="badge">source={SOURCE}</span>
  <span class="badge">time_frame={TIME_FRAME}</span>
  <span class="badge">거래량 표시</span>
  <span class="badge">read-only / 주문 금지</span>
  <p>기존 차트 형식을 유지하되, 신호 마커는 <b>당일 최저가 0.7% 이내의 저점반등 후보</b>만 표시합니다. RSI/MACD/고점권 매도/STAGE 마커는 가독성을 위해 숨겼습니다.</p>
  <pre id="summary"></pre>
</div>
<div id="chart" class="card"></div>
<script>
const data = {json.dumps(payload, ensure_ascii=False)};
document.getElementById('summary').textContent = JSON.stringify({{
  stock_name: data.stock_name,
  stock_code: data.stock_code,
  date: data.date,
  signal_counts: data.counts,
  day_low: data.day_low,
  day_high: data.day_high,
  or_entry: data.trade,
  exit: data.exit,
  paper_order_allowed: false,
  real_order_allowed: false,
  order_execution_enabled: false
}}, null, 2);

const candle = {{
  type: 'candlestick', name: '1분봉', x: data.x,
  open: data.open, high: data.high, low: data.low, close: data.close,
  increasing: {{line: {{color: '#ef4444'}}, fillcolor:'#ef4444'}},
  decreasing: {{line: {{color: '#3b82f6'}}, fillcolor:'#3b82f6'}},
  hovertemplate: '%{{x}}<br>시가 %{{open:,}}<br>고가 %{{high:,}}<br>저가 %{{low:,}}<br>종가 %{{close:,}}<extra></extra>'
}};
const volume = {{
  type:'bar', name:'거래량', x:data.x, y:data.volume, yaxis:'y2',
  marker:{{color:'#64748b', opacity:0.45}},
  hovertemplate:'%{{x}}<br>거래량 %{{y:,}}<extra></extra>'
}};
const dayLow = {{
  type:'scatter', mode:'lines', name:'당일 최저가',
  x:[data.x[0], data.x[data.x.length-1]], y:[data.day_low, data.day_low],
  line:{{color:'#22c55e', width:1.3, dash:'dot'}}
}};
const dayHigh = {{
  type:'scatter', mode:'lines', name:'당일 최고가',
  x:[data.x[0], data.x[data.x.length-1]], y:[data.day_high, data.day_high],
  line:{{color:'#fb7185', width:1.3, dash:'dot'}}
}};
const buy = {{
  type:'scatter', mode:'markers', name:'저점반등 근접 신호',
  x:data.buy.x, y:data.buy.y, customdata:data.buy.hover,
  marker:{{symbol:'circle', size:data.buy.score.map(s => 10 + s*2), color:'#22c55e', line:{{color:'#ffffff', width:1}}}},
  hovertemplate:'%{{customdata}}<extra>저점반등</extra>'
}};
const sell = {{
  type:'scatter', mode:'markers', name:'고점권 매도 후보',
  x:data.sell.x, y:data.sell.y, customdata:data.sell.hover,
  marker:{{symbol:'x', size:data.sell.score.map(s => 10 + s*2), color:'#ef4444', line:{{color:'#ffffff', width:1}}}},
  hovertemplate:'%{{customdata}}<extra>SELL 후보</extra>'
}};
const stage = {{
  type:'scatter', mode:'markers+text', name:'시게루 STAGE',
  x:data.stage.x, y:data.stage.y, text:data.stage.text, customdata:data.stage.hover,
  textposition:'middle right',
  marker:{{symbol:'star', size:20, color:'#facc15', line:{{color:'#111827', width:1}}}},
  hovertemplate:'%{{customdata}}<extra>SHIGERU</extra>'
}};
const exit = {{
  type:'scatter', mode:'markers+text', name:'EXIT',
  x:[data.exit.x], y:[data.exit.price], text:['청산'], textposition:'bottom left',
  marker:{{symbol:'triangle-down', size:18, color:'#f97316', line:{{color:'#ffffff', width:1}}}},
  hovertemplate:'청산<br>%{{x}}<br>%{{y:,}}<extra></extra>'
}};
const traces = [candle, volume, dayLow, dayHigh, buy, exit];
if (data.trade) {{
  traces.push({{
    type:'scatter', mode:'markers+text', name:'ENTRY/OR',
    x:[data.trade.x], y:[data.trade.price], text:['진입/OR'], textposition:'top right',
    marker:{{symbol:'triangle-up', size:18, color:'#10b981', line:{{color:'#ffffff', width:1}}}},
    hovertemplate:'OR진입<br>%{{x}}<br>%{{y:,}}<extra></extra>'
  }});
  traces.push({{
    type:'scatter', mode:'lines', name:'OR 고가 기준선',
    x:[data.x[0], data.x[data.x.length-1]], y:[data.trade.opening_high, data.trade.opening_high],
    line:{{color:'#f59e0b', width:1.3, dash:'dash'}}
  }});
}}
Plotly.newPlot('chart', traces, {{
  paper_bgcolor:'#111827', plot_bgcolor:'#111827', font:{{color:'#e5e7eb'}},
  title:'1분봉 캔들 + 거래량 + 진입/청산 + 신호 마커',
  xaxis:{{rangeslider:{{visible:false}}, gridcolor:'#1f2937', title:'시간'}},
  yaxis:{{title:'가격', gridcolor:'#1f2937'}},
  yaxis2:{{title:'거래량', overlaying:'y', side:'right', showgrid:false}},
  legend:{{orientation:'h', y:1.08}},
  margin:{{t:90, l:70, r:70, b:50}}
}}, {{responsive:true, displaylogo:false}});
</script>
</body>
</html>
"""
    out_path.write_text(html_text, encoding="utf-8")
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "date": str(trading_day),
        "buy_count": len(all_buy),
        "sell_count": len(all_sell),
        "buy_displayed": len(buy),
        "sell_displayed": len(sell),
        "stage_count": len(stage),
        "filename": out_path.name,
        "path": str(out_path),
    }


def render_index(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    table_rows = []
    for row in rows:
        table_rows.append(
            f"<tr><td>{esc(row['stock_name'])}</td><td>{esc(row['stock_code'])}</td><td>{esc(row['date'])}</td>"
            f"<td>{row['buy_count']} / 저점반등 표시 {row['buy_displayed']}</td><td>{row['sell_count']} / 표시 0</td><td>숨김</td>"
            f"<td><a href='{esc(row['filename'])}' target='_blank'>차트</a></td>"
            f"<td><a href='{esc(row['filename'])}' download>다운로드</a></td></tr>"
        )
    buy = summary.get("buy", {})
    sell = summary.get("sell", {})
    html_text = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>백테스트 신호검토 차트 인덱스</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans CJK KR','NanumSquareRound','Segoe UI',sans-serif;margin:24px;background:#0b1020;color:#e5e7eb}} table{{border-collapse:collapse;width:100%;background:#111827}} th,td{{border:1px solid #334155;padding:8px;text-align:right}} th{{background:#1f2937}} td:first-child,td:nth-child(2),td:nth-child(3),td:last-child{{text-align:center}} a{{color:#93c5fd}} .good{{color:#86efac}} .bad{{color:#fca5a5}} .card{{background:#111827;border:1px solid #334155;border-radius:12px;padding:16px;margin:12px 0}}</style>
</head><body><h1>백테스트 신호검토 차트 인덱스</h1>
<div class="card"><p>기존 <code>entry_exit.html</code> 형식을 우선 유지했습니다. 거래량은 우측 축에 얇게 겹쳐 표시하고, 차트 신호는 <b>당일 최저가 0.7% 이내의 저점반등 후보</b>만 표시합니다. RSI/MACD/고점권 매도/STAGE 신호는 차트 가독성을 위해 숨겼습니다.</p>
<p>매수 후보: {buy.get('count')}개 / 최저가 0.7% 이내 {buy.get('near_count')}개 ({buy.get('near_rate_pct')}%) · 매도 후보: {sell.get('count')}개 / 최고가 0.7% 이내 {sell.get('near_count')}개 ({sell.get('near_rate_pct')}%)</p>
<p><a href="index.html">기존 entry/exit 인덱스 보기</a></p></div>
<table><thead><tr><th>종목명</th><th>코드</th><th>날짜</th><th>매수후보/저점반등표시</th><th>매도후보</th><th>시게루</th><th>차트</th><th>다운로드</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table>
<p>안전 상태: read-only, paper_order_allowed=false, real_order_allowed=false, order_execution_enabled=false.</p>
</body></html>"""
    (out_dir / "index_signal_review.html").write_text(html_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930", "000660", "035420", "005380", "068270"])
    parser.add_argument("--days", type=int, default=130)
    parser.add_argument("--limit-days", type=int, default=35)
    parser.add_argument("--chart-limit", type=int, default=10)
    parser.add_argument("--or-window", type=int, choices=[10, 30], default=10)
    parser.add_argument("--out-dir", default="reports/backtest_trade_charts")
    args = parser.parse_args()

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        print(json.dumps({"ok": False, "blocking_conditions": ["missing_database_url"]}, ensure_ascii=False, indent=2))
        return 2

    import psycopg

    out_dir = PROJECT_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    all_buy: list[Any] = []
    all_sell: list[Any] = []
    days_seen = 0
    blocks: list[str] = []

    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            names = fetch_stock_names(cur, args.stock_codes)
            for stock_code, trading_day in fetch_stock_days(cur, args.stock_codes, args.days, args.limit_days):
                bars = fetch_bars(cur, stock_code, trading_day)
                if not bars:
                    blocks.append(f"missing_bars:{stock_code}:{trading_day}")
                    continue
                days_seen += 1
                markers = make_markers(bars)
                all_buy.extend(markers["buy_markers"])
                all_sell.extend(markers["sell_markers"])
                if len(rows) < args.chart_limit and (markers["buy_markers"] or markers["sell_markers"]):
                    stock_name = names.get(stock_code) or stock_code
                    out_path = out_dir / f"{trading_day}_{stock_code}_signal_review.html"
                    rows.append(render_trade_html(stock_code, stock_name, trading_day, bars, markers, out_path, or_window=args.or_window))

    summary = {
        "stock_days_seen": days_seen,
        "buy": summarize_markers(all_buy, "dist_low_pct"),
        "sell": summarize_markers(all_sell, "dist_high_pct"),
    }
    render_index(out_dir, rows, summary)
    payload = {
        "ok": not blocks,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "index": str(out_dir / "index_signal_review.html"),
        "chart_count": len(rows),
        "charts": rows,
        "summary": summary,
        "blocking_conditions": blocks,
        "paper_order_allowed": False,
        "real_order_allowed": False,
        "order_execution_enabled": False,
    }
    (out_dir / "signal_review_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not blocks else 2


if __name__ == "__main__":
    raise SystemExit(main())
