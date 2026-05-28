#!/usr/bin/env python3
"""Collect daily OHLCV from Kiwoom ka10081 for active kospi_top50 stocks.

Real-data-first: no fallback/sample data is inserted. Empty or error API responses are logged
as failures and skipped.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def get_trading_env(env: dict[str, str]) -> str:
    value = (env.get("TRADING_ENV") or "mock").strip().lower()
    return "prod" if value == "prod" else "mock"


def env_get(env: dict[str, str], key: str, trading_env: str) -> str | None:
    suffix = "PROD" if trading_env == "prod" else "MOCK"
    return env.get(f"{key}_{suffix}") or env.get(key)


def base_url(trading_env: str) -> str:
    return "https://api.kiwoom.com" if trading_env == "prod" else "https://mockapi.kiwoom.com"


def clean_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    digits = re.sub(r"[^0-9-]", "", text)
    if digits in ("", "-", "+"):
        return None
    try:
        return abs(int(digits))
    except ValueError:
        return None


def issue_token(host: str, appkey: str, secretkey: str) -> str:
    resp = requests.post(
        f"{host}/oauth2/token",
        headers={"Content-Type": "application/json; charset=UTF-8", "Accept": "application/json"},
        json={"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey},
        timeout=30,
    )
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"OAuth response is not JSON: HTTP {resp.status_code}, {resp.text[:200]}") from exc
    if resp.status_code != 200 or data.get("return_code") != 0 or not data.get("token"):
        raise RuntimeError(f"OAuth failed: HTTP {resp.status_code}, return_code={data.get('return_code')}, msg={data.get('return_msg')}")
    return data["token"]


def active_stocks(database_url: str, limit: int | None = None) -> list[tuple[str, str, int]]:
    sql = """
        SELECT stock_code, stock_name, rank
        FROM kospi_top50
        WHERE is_active = true
        ORDER BY rank
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    with psycopg.connect(database_url, connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [(str(code), str(name), int(rank)) for code, name, rank in cur.fetchall()]


def call_ka10081(host: str, token: str, stock_code: str, base_dt: str, max_retries: int = 3) -> list[dict[str, Any]]:
    url = f"{host}/api/dostk/chart"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}",
        "api-id": "ka10081",
        "cont-yn": "N",
        "next-key": "",
    }
    body = {"stk_cd": stock_code, "base_dt": base_dt, "upd_stkpc_tp": "1"}
    for attempt in range(1, max_retries + 1):
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        if resp.status_code == 429:
            wait = 10 * attempt
            print(f"  ⚠️ 429 rate limit: {stock_code}, {wait}s 대기 후 재시도")
            time.sleep(wait)
            continue
        try:
            data = resp.json()
        except Exception as exc:
            raise RuntimeError(f"{stock_code} non-json response: HTTP {resp.status_code}, {resp.text[:250]}") from exc
        if resp.status_code != 200 or data.get("return_code") not in (0, "0", None):
            # Some chart responses may omit return_code on success; otherwise show sanitized message only.
            raise RuntimeError(f"{stock_code} API failed: HTTP {resp.status_code}, return_code={data.get('return_code')}, msg={data.get('return_msg')}")
        rows = data.get("stk_dt_pole_chart_qry")
        if rows is None:
            raise RuntimeError(f"{stock_code} response missing stk_dt_pole_chart_qry; keys={list(data.keys())[:12]}")
        if not isinstance(rows, list):
            raise RuntimeError(f"{stock_code} chart data is not list: {type(rows).__name__}")
        return rows
    raise RuntimeError(f"{stock_code} failed after {max_retries} retries due to rate limit")


def parse_daily_rows(stock_code: str, raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in raw_rows:
        dt = str(row.get("dt") or "").strip()
        if not re.fullmatch(r"\d{8}", dt):
            continue
        close = clean_int(row.get("cur_prc"))
        item = {
            "stock_code": stock_code,
            "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}",
            "open": clean_int(row.get("open_pric")),
            "high": clean_int(row.get("high_pric")),
            "low": clean_int(row.get("low_pric")),
            "close": close,
            "volume": clean_int(row.get("trde_qty")),
            "trading_value": clean_int(row.get("trde_prica")),
            "source": "kiwoom_ka10081",
        }
        if all(item[k] is not None for k in ["open", "high", "low", "close"]):
            out.append(item)
    # API commonly returns newest first; DB does not care, but sorting helps reports.
    out.sort(key=lambda x: x["date"])
    return out


def upsert_daily(database_url: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    sql = """
        INSERT INTO daily_prices (
            stock_code, date, open, high, low, close, volume, trading_value, source, updated_at
        ) VALUES (
            %(stock_code)s, %(date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(trading_value)s, %(source)s, NOW()
        )
        ON CONFLICT (stock_code, date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            trading_value = EXCLUDED.trading_value,
            source = EXCLUDED.source,
            updated_at = NOW()
    """
    with psycopg.connect(database_url, connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()


def verify_daily(database_url: str) -> tuple[int, int, str | None, str | None, list[tuple[Any, ...]]]:
    with psycopg.connect(database_url, connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM daily_prices WHERE source='kiwoom_ka10081'")
            total = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(DISTINCT stock_code) FROM daily_prices WHERE source='kiwoom_ka10081'")
            stocks = int(cur.fetchone()[0])
            cur.execute("SELECT MIN(date), MAX(date) FROM daily_prices WHERE source='kiwoom_ka10081'")
            min_dt, max_dt = cur.fetchone()
            cur.execute("""
                SELECT stock_code, COUNT(*) AS rows, MIN(date), MAX(date)
                FROM daily_prices
                WHERE source='kiwoom_ka10081'
                GROUP BY stock_code
                ORDER BY rows DESC, stock_code
                LIMIT 10
            """)
            sample = cur.fetchall()
    return total, stocks, str(min_dt) if min_dt else None, str(max_dt) if max_dt else None, sample


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dt", default=datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    env = load_env()
    missing = [k for k in ["DATABASE_URL"] if not env.get(k)]
    trading_env = get_trading_env(env)
    appkey = env_get(env, "KIWOOM_REST_API_KEY", trading_env)
    secretkey = env_get(env, "KIWOOM_REST_API_SECRET", trading_env)
    if not appkey:
        missing.append(f"KIWOOM_REST_API_KEY(_{trading_env.upper()})")
    if not secretkey:
        missing.append(f"KIWOOM_REST_API_SECRET(_{trading_env.upper()})")
    if missing:
        print(f"❌ missing env: {', '.join(missing)}", file=sys.stderr)
        return 2

    host = base_url(trading_env)
    stocks = active_stocks(env["DATABASE_URL"], args.limit)
    if not stocks:
        print("❌ active kospi_top50 종목이 없습니다.", file=sys.stderr)
        return 2

    print(f"Kiwoom 일봉 수집 시작: env={trading_env}, base_dt={args.base_dt}, stocks={len(stocks)}, delay={args.delay}s")
    token = issue_token(host, appkey, secretkey)  # token value never printed
    print("OAuth 토큰 발급: OK")

    ok = 0
    failed: list[str] = []
    inserted_total = 0
    for idx, (code, name, rank) in enumerate(stocks, start=1):
        if idx > 1:
            time.sleep(args.delay)
        print(f"[{idx:02d}/{len(stocks):02d}] {rank:>2}. {code} {name} ...", flush=True)
        try:
            raw_rows = call_ka10081(host, token, code, args.base_dt)
            rows = parse_daily_rows(code, raw_rows)
            if not rows:
                raise RuntimeError(f"parsed rows is empty; raw_count={len(raw_rows)}")
            upsert_daily(env["DATABASE_URL"], rows)
            ok += 1
            inserted_total += len(rows)
            print(f"  ✅ {len(rows)} rows 저장 ({rows[0]['date']}~{rows[-1]['date']})")
        except Exception as exc:
            failed.append(f"{code} {name}: {exc}")
            print(f"  ❌ 실패: {exc}")

    total, stocks_count, min_dt, max_dt, sample = verify_daily(env["DATABASE_URL"])
    print("\nDB 검증:")
    print(f"  kiwoom_ka10081 total_rows={total}, stock_count={stocks_count}, date_range={min_dt}~{max_dt}")
    for code, row_count, sdt, edt in sample:
        print(f"  {code}: {row_count} rows ({sdt}~{edt})")
    print(f"\n수집 결과: success={ok}, failed={len(failed)}, 이번 실행 파싱/저장 rows={inserted_total}")
    if failed:
        print("실패 목록:")
        for item in failed[:20]:
            print(f"  - {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
