#!/usr/bin/env python3
"""Verify kospi_top50 through direct Postgres and Supabase REST without printing secrets."""

from pathlib import Path
import sys

import psycopg
import requests

ROOT = Path(__file__).resolve().parents[1]


def load_env():
    env = {}
    for raw in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def main():
    env = load_env()
    required = ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        print(f"missing env: {', '.join(missing)}", file=sys.stderr)
        return 2

    with psycopg.connect(env["DATABASE_URL"], connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), MIN(rank), MAX(rank) FROM kospi_top50 WHERE is_active = true")
            count, min_rank, max_rank = cur.fetchone()
            cur.execute("SELECT rank, stock_code, stock_name FROM kospi_top50 WHERE is_active = true ORDER BY rank LIMIT 5")
            top5 = cur.fetchall()
    print(f"Postgres: active_count={count}, rank_range={min_rank}..{max_rank}")
    print("Postgres top5:")
    for row in top5:
        print(f"  {row[0]}. {row[1]} {row[2]}")

    url = env["SUPABASE_URL"].rstrip("/") + "/rest/v1/kospi_top50?select=rank,stock_code,stock_name&is_active=eq.true&order=rank.asc&limit=5"
    headers = {
        "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": "Bearer " + env["SUPABASE_SERVICE_ROLE_KEY"],
        "Accept": "application/json",
    }
    r = requests.get(url, headers=headers, timeout=20)
    print(f"Supabase REST: http_status={r.status_code}, rows={len(r.json()) if r.ok else 'n/a'}")
    if not r.ok:
        print(r.text[:500], file=sys.stderr)
        return 3
    for item in r.json():
        print(f"  {item['rank']}. {item['stock_code']} {item['stock_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
