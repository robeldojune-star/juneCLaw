"""Compare our stored/calculated trading data against fresh Kiwoom raw data.

Read-only validation tool. It does not write DB rows and never places orders.

What can be compared directly:
- Fresh Kiwoom ka10081 daily OHLCV vs our Supabase daily_prices rows.
- Fresh Kiwoom ka10080 minute OHLCV vs our Supabase intraday_prices rows.

What cannot usually be compared directly via Kiwoom REST:
- RSI/MACD/Ichimoku values, unless a verified Kiwoom endpoint exporting those
  indicator values is added later. Current comparison recomputes indicators from
  fresh Kiwoom OHLCV and compares them to our technical_indicators table.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient, clean_int  # noqa: E402
from core.market_data_service import MarketDataService, normalize_stock_code  # noqa: E402
from core.supabase_rest import SupabaseRestClient, SupabaseRestError  # noqa: E402

SOURCE_DAILY = "kiwoom_ka10081"
SOURCE_MINUTE = "kiwoom_ka10080_minute"
TIME_FRAME_MINUTE = "1min"
KST = ZoneInfo("Asia/Seoul")


def pct_diff(a: float | int | None, b: float | int | None) -> float | None:
    if a is None or b is None:
        return None
    try:
        if float(b) == 0:
            return None
        return round((float(a) - float(b)) / float(b) * 100.0, 6)
    except Exception:
        return None


def abs_diff(a: float | int | None, b: float | int | None) -> float | None:
    if a is None or b is None:
        return None
    try:
        return round(float(a) - float(b), 6)
    except Exception:
        return None


def parse_kiwoom_daily(code: str, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        dt = re.sub(r"\D", "", str(row.get("dt") or ""))
        if len(dt) != 8:
            continue
        date = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}"
        out[date] = {
            "stock_code": code,
            "date": date,
            "open": clean_int(row.get("open_pric"), abs_value=True),
            "high": clean_int(row.get("high_pric"), abs_value=True),
            "low": clean_int(row.get("low_pric"), abs_value=True),
            "close": clean_int(row.get("cur_prc"), abs_value=True) or clean_int(row.get("close_pric"), abs_value=True),
            "volume": clean_int(row.get("trde_qty"), abs_value=True),
        }
    return out


def parse_cntr_tm(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) < 12:
        return None
    digits = digits[:14] if len(digits) >= 14 else digits[:12] + "00"
    try:
        ts = datetime.strptime(digits, "%Y%m%d%H%M%S").replace(tzinfo=KST)
        return ts.isoformat()
    except ValueError:
        return None


def parse_kiwoom_minute(code: str, rows: list[dict[str, Any]], limit: int) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ts = parse_cntr_tm(row.get("cntr_tm"))
        if not ts:
            continue
        out[ts] = {
            "stock_code": code,
            "timestamp": ts,
            "open": clean_int(row.get("open_pric"), abs_value=True),
            "high": clean_int(row.get("high_pric"), abs_value=True),
            "low": clean_int(row.get("low_pric"), abs_value=True),
            "close": clean_int(row.get("cur_prc"), abs_value=True) or clean_int(row.get("close_pric"), abs_value=True),
            "volume": clean_int(row.get("trde_qty"), abs_value=True),
        }
        if len(out) >= limit:
            break
    return out


def compare_rows(fresh: dict[str, dict[str, Any]], stored: dict[str, dict[str, Any]], key_name: str, fields: list[str]) -> dict[str, Any]:
    shared_keys = sorted(set(fresh) & set(stored))
    missing_in_stored = sorted(set(fresh) - set(stored))[:20]
    extra_in_stored = sorted(set(stored) - set(fresh))[:20]
    mismatches: list[dict[str, Any]] = []
    exact_matches = 0
    for key in shared_keys:
        row_ok = True
        field_diffs: dict[str, Any] = {}
        for field in fields:
            a = fresh[key].get(field)
            b = stored[key].get(field)
            try:
                a_num = None if a is None else float(a)
                b_num = None if b is None else float(b)
            except Exception:
                a_num, b_num = a, b
            if a_num != b_num:
                row_ok = False
                field_diffs[field] = {"kiwoom_fresh": a, "our_stored": b, "abs_diff": abs_diff(a, b), "pct_diff_vs_stored": pct_diff(a, b)}
        if row_ok:
            exact_matches += 1
        elif len(mismatches) < 30:
            mismatches.append({key_name: key, "diffs": field_diffs})
    return {
        "fresh_rows": len(fresh),
        "stored_rows": len(stored),
        "shared_rows": len(shared_keys),
        "exact_match_rows": exact_matches,
        "mismatch_rows": len(shared_keys) - exact_matches,
        "missing_in_our_stored_sample": missing_in_stored,
        "extra_in_our_stored_sample": extra_in_stored,
        "mismatch_sample": mismatches,
    }


def latest_stored_daily(sb: SupabaseRestClient, code: str, limit: int) -> dict[str, dict[str, Any]]:
    rows = sb.get(
        "daily_prices",
        {
            "select": "date,open,high,low,close,volume,source",
            "stock_code": f"eq.{code}",
            "source": f"eq.{SOURCE_DAILY}",
            "order": "date.desc",
            "limit": str(limit),
        },
        timeout=30,
    )
    return {str(r.get("date")): r for r in rows if r.get("date")}


def latest_stored_minute(sb: SupabaseRestClient, code: str, limit: int) -> dict[str, dict[str, Any]]:
    rows = sb.get(
        "intraday_prices",
        {
            "select": "timestamp,open,high,low,close,volume,source,time_frame",
            "stock_code": f"eq.{code}",
            "source": f"eq.{SOURCE_MINUTE}",
            "time_frame": f"eq.{TIME_FRAME_MINUTE}",
            "order": "timestamp.desc",
            "limit": str(limit),
        },
        timeout=30,
    )
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        ts = str(r.get("timestamp") or "")
        try:
            normalized_ts = datetime.fromisoformat(ts).astimezone(KST).isoformat()
        except ValueError:
            normalized_ts = ts
        out[normalized_ts] = r
    return out


def rounded_or_none(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def compare_daily_indicators(sb: SupabaseRestClient, code: str, fresh_daily: dict[str, dict[str, Any]]) -> dict[str, Any]:
    # Match scripts/calculate_technical_indicators.py production formula, not
    # core/fujimoto_126_filter.py's intraday Shigeru formula.
    df = pd.DataFrame([fresh_daily[d] for d in sorted(fresh_daily)])
    if df.empty:
        return {"method": "production_daily_formula", "blocking_conditions": ["no_fresh_daily_rows"]}
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["rsi"] = 100 - (100 / (1 + rs))
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["signal_line"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["signal_line"]

    computed: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        d = row["date"].date().isoformat()
        computed[d] = {
            "rsi": rounded_or_none(float(row["rsi"])) if pd.notna(row["rsi"]) else None,
            "macd": rounded_or_none(float(row["macd"])) if pd.notna(row["macd"]) else None,
            "signal_line": rounded_or_none(float(row["signal_line"])) if pd.notna(row["signal_line"]) else None,
            "macd_hist": rounded_or_none(float(row["macd_hist"])) if pd.notna(row["macd_hist"]) else None,
        }
    rows = sb.get(
        "technical_indicators",
        {
            "select": "date,rsi,macd,signal_line,macd_hist,time_frame",
            "stock_code": f"eq.{code}",
            "time_frame": "eq.daily",
            "order": "date.desc",
            "limit": str(len(computed)),
        },
        timeout=30,
    )
    stored = {str(r.get("date")): r for r in rows if r.get("date")}
    shared = sorted(set(computed) & set(stored))
    diffs: list[dict[str, Any]] = []
    tolerance = {"rsi": 0.05, "macd": 1.0, "signal_line": 1.0, "macd_hist": 1.0}
    pass_count = 0
    checked = 0
    for d in shared:
        row_diff: dict[str, Any] = {}
        for field in ["rsi", "macd", "signal_line", "macd_hist"]:
            a = computed[d].get(field)
            b = stored[d].get(field)
            if a is None or b is None:
                continue
            checked += 1
            delta = abs_diff(a, b)
            if delta is not None and abs(delta) <= tolerance[field]:
                pass_count += 1
            elif len(diffs) < 30:
                row_diff[field] = {"computed_from_fresh_kiwoom_ohlcv": a, "our_stored_indicator": b, "abs_diff": delta, "tolerance": tolerance[field]}
        if row_diff:
            diffs.append({"date": d, "diffs": row_diff})
    return {
        "method": "Recompute RSI/MACD from fresh Kiwoom daily OHLCV, then compare to our technical_indicators.daily. This is not a direct Kiwoom indicator-value comparison.",
        "computed_dates": len(computed),
        "stored_indicator_rows": len(stored),
        "shared_dates": len(shared),
        "checked_fields": checked,
        "within_tolerance_fields": pass_count,
        "outside_tolerance_fields": checked - pass_count,
        "diff_sample": diffs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-codes", nargs="+", default=["005930"])
    parser.add_argument("--base-dt", default=datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d"))
    parser.add_argument("--trading-env", choices=["mock", "prod"], default=None)
    parser.add_argument("--daily-limit", type=int, default=120)
    parser.add_argument("--minute-limit", type=int, default=200)
    parser.add_argument("--skip-minute", action="store_true")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    codes = [normalize_stock_code(c) for c in args.stock_codes]
    result: dict[str, Any] = {
        "ok": True,
        "generated_at_kst": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "purpose": "our_data_vs_fresh_kiwoom_validation",
        "important_note": "Kiwoom REST docs available in this repo expose raw market/fundamental/ranking fields, not verified RSI/MACD/Ichimoku indicator values. Indicator comparison is recomputation-based.",
        "sources": {
            "kiwoom_daily_raw": "ka10081 /api/dostk/chart",
            "kiwoom_minute_raw": "ka10080 /api/dostk/chart",
            "our_daily_table": "daily_prices source=kiwoom_ka10081",
            "our_minute_table": "intraday_prices source=kiwoom_ka10080_minute time_frame=1min",
            "our_indicator_table": "technical_indicators time_frame=daily",
        },
        "blocking_conditions": [],
        "per_stock": {},
    }

    try:
        sb = SupabaseRestClient()
        client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env", trading_env=args.trading_env)
        market = MarketDataService(client)
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["blocking_conditions"].append(f"setup_failed:{type(exc).__name__}")
        result["error"] = str(exc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    for code in codes:
        stock_out: dict[str, Any] = {"blocking_conditions": []}
        try:
            fresh_daily_rows = market.get_daily_chart_raw(code, base_dt=args.base_dt, adjusted_price=True)
            fresh_daily_all = parse_kiwoom_daily(code, fresh_daily_rows)
            fresh_daily = dict(list(fresh_daily_all.items())[: args.daily_limit])
            stored_daily = latest_stored_daily(sb, code, args.daily_limit)
            stock_out["daily_ohlcv_comparison"] = compare_rows(fresh_daily, stored_daily, "date", ["open", "high", "low", "close", "volume"])
            stock_out["daily_indicator_comparison"] = compare_daily_indicators(sb, code, fresh_daily_all)
        except Exception as exc:  # noqa: BLE001
            stock_out["blocking_conditions"].append(f"daily_compare_failed:{type(exc).__name__}:{exc}")

        if not args.skip_minute:
            try:
                fresh_minute_rows = market.get_minute_chart_raw(code, base_dt=args.base_dt, minute_scope="1", adjusted_price=True)
                fresh_minute = parse_kiwoom_minute(code, fresh_minute_rows, args.minute_limit)
                stored_minute = latest_stored_minute(sb, code, args.minute_limit)
                # Timestamp timezone representation can differ; direct timestamp compare is strict.
                stock_out["minute_ohlcv_comparison"] = compare_rows(fresh_minute, stored_minute, "timestamp", ["open", "high", "low", "close", "volume"])
            except Exception as exc:  # noqa: BLE001
                stock_out["blocking_conditions"].append(f"minute_compare_failed:{type(exc).__name__}:{exc}")

        result["per_stock"][code] = stock_out
        if stock_out["blocking_conditions"]:
            result["ok"] = False

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["json_out"] = str(out_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
