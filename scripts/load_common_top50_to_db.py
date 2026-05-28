#!/usr/bin/env python3
"""Load ETF/ETN/preferred-share excluded KOSPI common-stock TOP50 CSV into Supabase.

Steps:
1. Deactivate existing kospi_top50 active universe.
2. Upsert CSV rows as the active universe.
3. Verify Postgres + Supabase REST.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
import requests

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "kospi_top50_common_stocks_marketcap_naver.csv"
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


def clean_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    # CSV may contain 17509604.0 or 17,509,604.
    text = text.replace(",", "")
    try:
        return int(float(text))
    except ValueError:
        digits = re.sub(r"[^0-9-]", "", text)
        return int(digits) if digits not in ("", "-", "+") else None


def load_rows() -> list[dict[str, Any]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")
    rows: list[dict[str, Any]] = []
    collected_at = datetime.now(timezone.utc)
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rank = clean_int(raw.get("보통주순위"))
            code = str(raw.get("종목코드") or "").zfill(6)
            name = str(raw.get("종목명") or "").strip()
            if not rank or not re.fullmatch(r"\d{6}", code) or not name:
                raise ValueError(f"Invalid CSV row: {raw}")
            rows.append({
                "rank": rank,
                "stock_code": code,
                "stock_name": name,
                "market": "KOSPI",
                "market_cap": clean_int(raw.get("시가총액")),  # Naver unit: 억원
                "volume": clean_int(raw.get("거래량")),
                "is_active": True,
                "source": "naver_marketcap_common_stock",
                "collected_at": collected_at,
            })
    if len(rows) != 50:
        raise RuntimeError(f"Expected 50 rows, got {len(rows)}")
    if len({r["stock_code"] for r in rows}) != 50:
        raise RuntimeError("Duplicate stock_code in CSV")
    return rows


def upsert_universe(database_url: str, rows: list[dict[str, Any]]) -> None:
    sql_deactivate = "UPDATE kospi_top50 SET is_active = false, updated_at = NOW() WHERE is_active = true"
    sql_upsert = """
        INSERT INTO kospi_top50 (
            rank, stock_code, stock_name, market, market_cap, volume,
            is_active, source, collected_at, updated_at
        ) VALUES (
            %(rank)s, %(stock_code)s, %(stock_name)s, %(market)s, %(market_cap)s, %(volume)s,
            true, %(source)s, %(collected_at)s, NOW()
        )
        ON CONFLICT (stock_code) DO UPDATE SET
            rank = EXCLUDED.rank,
            stock_name = EXCLUDED.stock_name,
            market = EXCLUDED.market,
            market_cap = EXCLUDED.market_cap,
            volume = EXCLUDED.volume,
            is_active = true,
            source = EXCLUDED.source,
            collected_at = EXCLUDED.collected_at,
            updated_at = NOW()
    """
    with psycopg.connect(database_url, connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_deactivate)
            cur.executemany(sql_upsert, rows)
        conn.commit()


def verify_postgres(database_url: str) -> tuple[int, list[tuple[Any, ...]], int]:
    with psycopg.connect(database_url, connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM kospi_top50 WHERE is_active = true")
            active_count = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM kospi_top50 WHERE is_active = false")
            inactive_count = int(cur.fetchone()[0])
            cur.execute("""
                SELECT rank, stock_code, stock_name, market_cap, source
                FROM kospi_top50
                WHERE is_active = true
                ORDER BY rank
                LIMIT 10
            """)
            top10 = cur.fetchall()
    return active_count, top10, inactive_count


def verify_rest(env: dict[str, str]) -> int:
    url = env["SUPABASE_URL"].rstrip("/") + "/rest/v1/kospi_top50?select=rank,stock_code,stock_name,source&is_active=eq.true&order=rank.asc&limit=5"
    headers = {
        "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": "Bearer " + env["SUPABASE_SERVICE_ROLE_KEY"],
        "Accept": "application/json",
    }
    response = requests.get(url, headers=headers, timeout=20)
    if not response.ok:
        raise RuntimeError(f"Supabase REST verify failed: HTTP {response.status_code}, {response.text[:300]}")
    data = response.json()
    print(f"REST 검증: status={response.status_code}, rows={len(data)}")
    for item in data:
        print(f"  {item['rank']}. {item['stock_code']} {item['stock_name']} | {item['source']}")
    return len(data)


def main() -> int:
    env = load_env()
    missing = [k for k in ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"] if not env.get(k)]
    if missing:
        print(f"❌ missing env: {', '.join(missing)}", file=sys.stderr)
        return 2
    rows = load_rows()
    print(f"CSV 로드: {len(rows)}개 / 첫 종목={rows[0]['stock_code']} {rows[0]['stock_name']}")
    upsert_universe(env["DATABASE_URL"], rows)
    active_count, top10, inactive_count = verify_postgres(env["DATABASE_URL"])
    print(f"Postgres 검증: active={active_count}, inactive={inactive_count}")
    for rank, code, name, market_cap, source in top10:
        print(f"  {rank:>2}. {code} {name} | 시총={market_cap:,}억 | {source}")
    verify_rest(env)
    if active_count != 50:
        raise RuntimeError(f"Active universe count must be 50, got {active_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
