"""Create interactive HTML signal-review charts for low BUY/high SELL markers.

This is the HTML counterpart to analyze_extreme_signal_markers.py.
It uses real ka10080 1-minute bars and writes per-stock-day Plotly HTML files
plus an index for browser/download review.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

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


def marker_payload(markers: list[Any]) -> dict[str, list[Any]]:
    return {
        "x": [m.hhmm for m in markers],
        "y": [m.price for m in markers],
        "text": [f"{m.label}<br>score={m.score}<br>low거리={m.dist_low_pct:.2f}%<br>high거리={m.dist_high_pct:.2f}%" for m in markers],
        "label": [m.label for m in markers],
        "score": [m.score for m in markers],
    }


def render_chart_html(stock_code: str, stock_name: str, trading_day: Any, bars: list[Any], markers: dict[str, Any], out_path: Path, *, or_window: int) -> dict[str, Any]:
    trade = first_or_trade(bars, or_window)
    payload = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "trading_day": str(trading_day),
        "source": SOURCE,
        "time_frame": TIME_FRAME,
        "x": [b.hhmm for b in bars],
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
        "buy": marker_payload(markers["buy_markers"]),
        "sell": marker_payload(markers["sell_markers"]),
        "stage": marker_payload(markers["stage_markers"]),
        "day_low": markers["day_low"],
        "day_high": markers["day_high"],
        "or_trade": trade,
        "exit": {"x": bars[-1].hhmm, "y": bars[-1].close, "text": f"기존 청산<br>{bars[-1].hhmm}<br>{bars[-1].close:,.0f}"} if bars else None,
    }
    title = f"{stock_name} {trading_day} 저점권 매수·고점권 매도 신호 HTML 차트"
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  :root {{ --bg:#0b1020; --panel:#111827; --line:#334155; --text:#e5e7eb; --muted:#94a3b8; --link:#93c5fd; }}
  body {{ margin:0; padding:24px; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Noto Sans CJK KR','NanumSquareRound','Segoe UI',sans-serif; }}
  a {{ color:var(--link); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; margin:12px 0; }}
  .badges span {{ display:inline-block; margin:3px; padding:5px 9px; border-radius:999px; background:#1f2937; color:#dbeafe; }}
  #chart {{ height: 820px; }}
  pre {{ white-space:pre-wrap; color:#cbd5e1; }}
  table {{ border-collapse:collapse; width:100%; }} th,td {{ border:1px solid var(--line); padding:7px; text-align:right; }} th {{ background:#1f2937; }} td:first-child,th:first-child {{ text-align:left; }}
</style>
</head>
<body>
<header class="card">
  <p><a href="index.html">← HTML 인덱스로 돌아가기</a></p>
  <h1>{esc(title)}</h1>
  <div class="badges">
    <span>종목: {esc(stock_name)} ({esc(stock_code)})</span>
    <span>날짜: {esc(trading_day)}</span>
    <span>source={SOURCE}</span>
    <span>time_frame={TIME_FRAME}</span>
    <span>read-only / 주문 금지</span>
  </div>
  <p>마우스로 확대/축소, 드래그, 마커 hover가 가능합니다. 원본 HTML 파일 자체를 다운로드해 브라우저에서 열어도 됩니다.</p>
</header>
<section id="chart" class="card"></section>
<section class="card">
  <h2>신호 수</h2>
  <table>
    <tr><th>매수 후보</th><td>{len(markers['buy_markers'])}</td><th>매도 후보</th><td>{len(markers['sell_markers'])}</td><th>시게루 단계</th><td>{len(markers['stage_markers'])}</td></tr>
  </table>
</section>
<section class="card">
  <h2>원자료 JSON</h2>
  <pre id="raw"></pre>
</section>
<script>
const data = {json.dumps(payload, ensure_ascii=False)};
document.getElementById('raw').textContent = JSON.stringify({{
  stock_code: data.stock_code,
  stock_name: data.stock_name,
  trading_day: data.trading_day,
  day_low: data.day_low,
  day_high: data.day_high,
  buy_markers: data.buy,
  sell_markers: data.sell,
  stage_markers: data.stage,
  or_trade: data.or_trade,
  exit: data.exit
}}, null, 2);

const candle = {{
  type: 'candlestick', name: '1분봉 캔들', x: data.x,
  open: data.open, high: data.high, low: data.low, close: data.close,
  increasing: {{line: {{color: '#ef4444'}}, fillcolor:'#ef4444'}},
  decreasing: {{line: {{color: '#3b82f6'}}, fillcolor:'#3b82f6'}},
  hovertemplate: '%{{x}}<br>시가 %{{open:,}}<br>고가 %{{high:,}}<br>저가 %{{low:,}}<br>종가 %{{close:,}}<extra></extra>'
}};
const volume = {{
  type:'bar', name:'거래량', x:data.x, y:data.volume, yaxis:'y2', marker:{{color:'#64748b', opacity:0.35}},
  hovertemplate: '%{{x}}<br>거래량 %{{y:,}}<extra></extra>'
}};
const dayLow = {{type:'scatter', mode:'lines', name:'당일 최저가', x:[data.x[0], data.x[data.x.length-1]], y:[data.day_low, data.day_low], line:{{color:'#22c55e', dash:'dot', width:1.5}}}};
const dayHigh = {{type:'scatter', mode:'lines', name:'당일 최고가', x:[data.x[0], data.x[data.x.length-1]], y:[data.day_high, data.day_high], line:{{color:'#fb7185', dash:'dot', width:1.5}}}};
const buy = {{
  type:'scatter', mode:'markers+text', name:'매수 후보', x:data.buy.x, y:data.buy.y,
  text:data.buy.label, customdata:data.buy.text, textposition:'top center',
  marker:{{symbol:'circle', size:data.buy.score.map(s => 9 + s*2), color:'#22c55e', line:{{color:'#ffffff', width:1}}}},
  hovertemplate:'%{{customdata}}<extra>매수 후보</extra>'
}};
const sell = {{
  type:'scatter', mode:'markers+text', name:'매도 후보', x:data.sell.x, y:data.sell.y,
  text:data.sell.label, customdata:data.sell.text, textposition:'bottom center',
  marker:{{symbol:'x', size:data.sell.score.map(s => 10 + s*2), color:'#ef4444', line:{{color:'#ffffff', width:1}}}},
  hovertemplate:'%{{customdata}}<extra>매도 후보</extra>'
}};
const stage = {{
  type:'scatter', mode:'markers+text', name:'시게루 STAGE', x:data.stage.x, y:data.stage.y,
  text:data.stage.label, customdata:data.stage.text, textposition:'middle right',
  marker:{{symbol:'star', size:18, color:'#facc15', line:{{color:'#111827', width:1}}}},
  hovertemplate:'%{{customdata}}<extra>시게루 단계</extra>'
}};
const traces = [candle, volume, dayLow, dayHigh, buy, sell, stage];
if (data.or_trade) {{
  traces.push({{type:'scatter', mode:'markers+text', name:'OR 진입', x:[data.or_trade.hhmm], y:[data.or_trade.price], text:['OR진입'], textposition:'top right', marker:{{symbol:'triangle-up', size:18, color:'#10b981', line:{{color:'#ffffff', width:1}}}}, hovertemplate:'OR진입<br>%{{x}}<br>%{{y:,}}<extra></extra>'}});
  traces.push({{type:'scatter', mode:'lines', name:'OR 고가', x:[data.x[0], data.x[data.x.length-1]], y:[data.or_trade.opening_high, data.or_trade.opening_high], line:{{color:'#f59e0b', dash:'dash', width:1.2}}}});
}}
if (data.exit) {{
  traces.push({{type:'scatter', mode:'markers+text', name:'기존 청산', x:[data.exit.x], y:[data.exit.y], text:['청산'], textposition:'bottom left', marker:{{symbol:'triangle-down', size:18, color:'#f97316', line:{{color:'#ffffff', width:1}}}}, hovertemplate:data.exit.text + '<extra></extra>'}});
}}
Plotly.newPlot('chart', traces, {{
  paper_bgcolor:'#111827', plot_bgcolor:'#111827', font:{{color:'#e5e7eb'}},
  title:`${{data.stock_name}} (${{data.stock_code}}) ${{data.trading_day}} 신호 마킹`,
  xaxis:{{rangeslider:{{visible:false}}, gridcolor:'#263244', title:'시간'}},
  yaxis:{{title:'가격', gridcolor:'#263244', domain:[0.24, 1]}},
  yaxis2:{{title:'거래량', gridcolor:'#263244', domain:[0, 0.18]}},
  legend:{{orientation:'h', y:1.08}},
  margin:{{t:90, l:70, r:70, b:50}}
}}, {{responsive:true, displaylogo:false}});
</script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "trading_day": str(trading_day),
        "buy_count": len(markers["buy_markers"]),
        "sell_count": len(markers["sell_markers"]),
        "stage_count": len(markers["stage_markers"]),
        "filename": out_path.name,
        "path": str(out_path),
    }


def render_index(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any], generated_at: str) -> None:
    trs = []
    cards = []
    for row in rows:
        cls = "good" if int(row.get("buy_count") or 0) else "muted"
        trs.append(
            f"<tr><td>{esc(row['stock_name'])}</td><td>{esc(row['stock_code'])}</td><td>{esc(row['trading_day'])}</td>"
            f"<td>{esc(row['buy_count'])}</td><td>{esc(row['sell_count'])}</td><td>{esc(row['stage_count'])}</td>"
            f"<td><a href='{esc(row['filename'])}' target='_blank'>HTML 열기</a></td>"
            f"<td><a href='{esc(row['filename'])}' download>다운로드</a></td></tr>"
        )
        cards.append(
            f"<article class='card'><h2>{esc(row['stock_name'])} <span>({esc(row['stock_code'])})</span></h2>"
            f"<p>{esc(row['trading_day'])}</p><p><b class='{cls}'>매수 {esc(row['buy_count'])}</b> · <b class='bad'>매도 {esc(row['sell_count'])}</b> · 시게루 {esc(row['stage_count'])}</p>"
            f"<p><a href='{esc(row['filename'])}' target='_blank'>인터랙티브 HTML 보기</a> · <a href='{esc(row['filename'])}' download>HTML 다운로드</a></p></article>"
        )
    buy = summary.get("buy", {})
    sell = summary.get("sell", {})
    text = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>원본 HTML 신호 차트 인덱스</title>
<style>
:root{{--bg:#0b1020;--panel:#111827;--line:#334155;--text:#e5e7eb;--muted:#94a3b8;--link:#93c5fd;--good:#86efac;--bad:#fca5a5}}
body{{margin:0;padding:26px;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Noto Sans CJK KR','NanumSquareRound','Segoe UI',sans-serif}}
a{{color:var(--link);text-decoration:none}}a:hover{{text-decoration:underline}}
.wrap{{max-width:1400px;margin:0 auto}}.box,.card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}.card h2{{margin:0}}.card h2 span,.muted{{color:var(--muted)}}.good{{color:var(--good)}}.bad{{color:var(--bad)}}
table{{width:100%;border-collapse:collapse;background:var(--panel);margin-top:12px}}th,td{{border:1px solid var(--line);padding:8px;text-align:right}}th{{background:#1f2937}}td:first-child,th:first-child{{text-align:left}}
</style></head><body><div class="wrap">
<h1>원본 HTML 신호 차트 인덱스</h1>
<p class="muted">PNG가 아닌 Plotly 기반 원본 HTML 차트입니다. 각 파일을 다운로드해서 브라우저에서 열면 확대/축소/hover 검토가 가능합니다.</p>
<section class="box"><h2>요약</h2><table><tr><th>분석 stock-day</th><td>{esc(summary.get('stock_days_seen'))}</td><th>생성 시각</th><td>{esc(generated_at)}</td></tr>
<tr><th>매수 후보</th><td>{esc(buy.get('count'))} / 극값근처 {esc(buy.get('near_count'))} ({esc(buy.get('near_rate_pct'))}%)</td><th>매도 후보</th><td>{esc(sell.get('count'))} / 극값근처 {esc(sell.get('near_count'))} ({esc(sell.get('near_rate_pct'))}%)</td></tr></table></section>
<section class="box"><h2>검토 결론</h2><ul><li>저점반등 + RSI40회복: 시게루 STAGE1 조기 관찰 후보</li><li>MACD전환: STAGE2 확인 후보</li><li>고점거부 + RSI70이탈: 익절/분할청산 후보</li><li>MACD둔화: 보조 경고 후보</li></ul></section>
<section class="grid">{''.join(cards)}</section>
<section class="box"><h2>전체 목록</h2><table><thead><tr><th>종목명</th><th>코드</th><th>날짜</th><th>매수후보</th><th>매도후보</th><th>시게루</th><th>열기</th><th>다운로드</th></tr></thead><tbody>{''.join(trs)}</tbody></table></section>
<p class="muted">안전 상태: read-only, paper_order_allowed=false, real_order_allowed=false, order_execution_enabled=false.</p>
</div></body></html>"""
    (out_dir / "index.html").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930", "000660", "035420", "005380", "068270"])
    parser.add_argument("--days", type=int, default=130)
    parser.add_argument("--limit-days", type=int, default=35)
    parser.add_argument("--chart-limit", type=int, default=10)
    parser.add_argument("--or-window", type=int, choices=[10, 30], default=10)
    parser.add_argument("--out-dir", default="reports/backtest_trade_charts_signal_review_html")
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
            stock_days = fetch_stock_days(cur, args.stock_codes, args.days, args.limit_days)
            for stock_code, trading_day in stock_days:
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
                    safe_name = str(stock_name).replace("/", "_").replace(" ", "_")
                    out_path = out_dir / f"{trading_day}_{safe_name}_{stock_code}_signals.html"
                    rows.append(render_chart_html(stock_code, stock_name, trading_day, bars, markers, out_path, or_window=args.or_window))

    generated_at = datetime.now(KST).isoformat(timespec="seconds")
    summary = {
        "stock_days_seen": days_seen,
        "buy": summarize_markers(all_buy, "dist_low_pct"),
        "sell": summarize_markers(all_sell, "dist_high_pct"),
    }
    render_index(out_dir, rows, summary, generated_at)
    payload = {
        "ok": True,
        "generated_at": generated_at,
        "out_dir": str(out_dir),
        "index": str(out_dir / "index.html"),
        "chart_count": len(rows),
        "charts": rows,
        "summary": summary,
        "blocking_conditions": blocks,
        "paper_order_allowed": False,
        "real_order_allowed": False,
        "order_execution_enabled": False,
    }
    (out_dir / "html_signal_review_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not blocks else 2


if __name__ == "__main__":
    raise SystemExit(main())
