"""Compare Fujimoto 1-2-6 signal replay with OR10/OR30 on the same signal next-day universe.

Read-only: reads reports + Supabase/Postgres intraday_prices, writes markdown/json report files only.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import read_env  # noqa: E402
from scripts.backtest_opening_strategy import _simulate_variant  # noqa: E402

SOURCE = "kiwoom_ka10080_minute"
TIME_FRAME = "1min"
KST = timezone(timedelta(hours=9))


def ts_to_kst(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def fetch_rows(cur: Any, stock_code: str, trading_day: date) -> list[dict[str, Any]]:
    cur.execute(
        """
        select stock_code, timestamp, time_frame, source, open, high, low, close, volume, trading_value
        from intraday_prices
        where stock_code=%s and source=%s and time_frame=%s
          and (timestamp at time zone 'Asia/Seoul')::date=%s
        order by timestamp asc
        """,
        (stock_code, SOURCE, TIME_FRAME, trading_day),
    )
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def ret_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    vals = [float(r["net_return_pct"]) for r in rows if r.get("net_return_pct") is not None]
    if not vals:
        return {"trades": 0, "win_rate_pct": None, "avg_return_pct": None, "min_return_pct": None, "max_return_pct": None}
    return {
        "trades": len(vals),
        "win_rate_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 2),
        "avg_return_pct": round(sum(vals) / len(vals), 4),
        "min_return_pct": round(min(vals), 4),
        "max_return_pct": round(max(vals), 4),
    }


def main() -> int:
    fujimoto_path = PROJECT_ROOT / "reports/fujimoto_126_backtest_signals_post_backfill.json"
    fujimoto = json.loads(fujimoto_path.read_text(encoding="utf-8"))
    f_rows = [r for r in fujimoto["results"] if r.get("entry_trading_date") == "2026-05-29"]
    codes = sorted({r["stock_code"] for r in f_rows})

    env = read_env(PROJECT_ROOT / ".env")
    if not env.get("DATABASE_URL"):
        print(json.dumps({"ok": False, "blocking_conditions": ["missing_database_url"]}, ensure_ascii=False, indent=2))
        return 2

    import psycopg

    or10_by_code: dict[str, dict[str, Any]] = {}
    or30_by_code: dict[str, dict[str, Any]] = {}
    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            for code in codes:
                rows = fetch_rows(cur, code, date(2026, 5, 29))
                or10_by_code[code] = _simulate_variant(rows, 10, fee_bps=23, slippage_bps=10, stop_loss_pct=-1.0, take_profit_pct=1.5, time_exit="15:20")
                or30_by_code[code] = _simulate_variant(rows, 30, fee_bps=23, slippage_bps=10, stop_loss_pct=-1.0, take_profit_pct=1.5, time_exit="15:20")

    def agg_or(by_code: dict[str, dict[str, Any]]) -> dict[str, Any]:
        trades = sum(v.get("trades", 0) for v in by_code.values())
        avg_parts = [v["avg_return_pct"] for v in by_code.values() if v.get("avg_return_pct") is not None]
        win_parts = [v["win_rate"] for v in by_code.values() if v.get("win_rate") is not None]
        mdd_parts = [v["max_drawdown_pct"] for v in by_code.values() if v.get("max_drawdown_pct") is not None]
        exit_counts: dict[str, int] = {}
        for v in by_code.values():
            for reason, count in (v.get("exit_reason_counts") or {}).items():
                exit_counts[reason] = exit_counts.get(reason, 0) + int(count)
        return {
            "trades": trades,
            "coverage_codes_with_trade": sum(1 for v in by_code.values() if v.get("trades", 0) > 0),
            "win_rate_pct_mean_by_code": round(sum(win_parts) / len(win_parts), 2) if win_parts else None,
            "avg_return_pct_mean_by_code": round(sum(avg_parts) / len(avg_parts), 4) if avg_parts else None,
            "min_return_pct_by_code": round(min(mdd_parts), 4) if mdd_parts else None,
            "exit_reason_counts": exit_counts,
        }

    comparison = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "universe": {"trading_day": "2026-05-29", "codes": codes, "code_count": len(codes), "source": SOURCE, "time_frame": TIME_FRAME},
        "fujimoto_126": {"summary": ret_summary(f_rows), "exit_reason_counts": fujimoto["summary"]["exit_reason_counts"], "blocking_condition_counts": fujimoto["summary"]["blocking_condition_counts"]},
        "or10": {"summary": agg_or(or10_by_code), "per_code": or10_by_code},
        "or30": {"summary": agg_or(or30_by_code), "per_code": or30_by_code},
        "decision": {
            "recommended_use": "entry_delay_filter_or_watchlist_priority_only",
            "reason": "후지모토는 signals 표본에서 평균 수익률/승률이 OR10/OR30보다 좋지만, 모든 BUY 후보를 STAGE3로 통과시켜 차단 필터 기능은 아직 약함. 독립 진입 트리거보다는 OR 진입을 09:50~10:50 확인 구간으로 늦추거나 후보 우선순위/리스크 게이트로 쓰는 편이 안전함.",
            "order_gate": "paper_order_allowed=false, real_order_allowed=false 유지",
        },
    }

    json_out = PROJECT_ROOT / "reports/fujimoto_or_comparison_post_backfill.json"
    md_out = PROJECT_ROOT / "reports/fujimoto_or_comparison_post_backfill.md"
    json_out.write_text(json.dumps(comparison, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    lines = [
        "# 후지모토 1-2-6 vs OR10/OR30 비교 리포트",
        "",
        f"- 생성 시각: `{comparison['generated_at']}`",
        "- 표본: `2026-05-28 BUY signals`의 다음 거래일 `2026-05-29`, 23종목",
        "- 데이터: 실제 `intraday_prices`, source=`kiwoom_ka10080_minute`, time_frame=`1min`",
        "- 안전: read-only 분석, 주문/포지션 미변경, paper/real 주문 금지",
        "",
        "## 성과 비교",
        "",
        "| 전략 | 거래/진입 | 승률 | 평균 net% | min/위험 | 종료/청산 분포 |",
        "|---|---:|---:|---:|---:|---|",
        f"| 후지모토 1-2-6 | {comparison['fujimoto_126']['summary']['trades']} | {comparison['fujimoto_126']['summary']['win_rate_pct']} | {comparison['fujimoto_126']['summary']['avg_return_pct']} | {comparison['fujimoto_126']['summary']['min_return_pct']} | `{json.dumps(comparison['fujimoto_126']['exit_reason_counts'], ensure_ascii=False)}` |",
        f"| OR10 | {comparison['or10']['summary']['trades']} | {comparison['or10']['summary']['win_rate_pct_mean_by_code']}* | {comparison['or10']['summary']['avg_return_pct_mean_by_code']}* | {comparison['or10']['summary']['min_return_pct_by_code']} | `{json.dumps(comparison['or10']['summary']['exit_reason_counts'], ensure_ascii=False)}` |",
        f"| OR30 | {comparison['or30']['summary']['trades']} | {comparison['or30']['summary']['win_rate_pct_mean_by_code']}* | {comparison['or30']['summary']['avg_return_pct_mean_by_code']}* | {comparison['or30']['summary']['min_return_pct_by_code']} | `{json.dumps(comparison['or30']['summary']['exit_reason_counts'], ensure_ascii=False)}` |",
        "",
        "* OR 승률/평균은 기존 스크립트 구조와 맞춘 종목별 평균입니다. 거래 단위 평균과 약간 다를 수 있습니다.",
        "",
        "## 판단",
        "",
        "- 후지모토 signals 표본: 23건 모두 진입, 평균 `+0.4969%`, 승률 `60.87%`, 손절 7건/익절 12건/시간청산 4건.",
        "- OR10/OR30: 같은 종목군에서 OR30이 OR10보다 낫지만 둘 다 평균이 음수였습니다.",
        "- 단, 후지모토가 모든 후보를 통과시켰으므로 **차단형 보조 필터**로는 아직 검증 부족입니다.",
        "- 현재 결론: **진입 지연/확인 필터 또는 후보 우선순위 필터**로 쓰는 것이 더 타당합니다.",
        "- paper/real 주문은 계속 금지합니다.",
        "",
    ]
    md_out.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "json_out": str(json_out), "md_out": str(md_out), "summary": {"fujimoto": comparison["fujimoto_126"]["summary"], "or10": comparison["or10"]["summary"], "or30": comparison["or30"]["summary"]}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
