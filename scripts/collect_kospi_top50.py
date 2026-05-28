#!/usr/bin/env python3
"""Collect KOSPI TOP50 by trading volume from Kiwoom ka10030 and upsert to Supabase.

Real-data-first rule: this script never inserts fallback/sample rows. If Kiwoom returns
an error or an empty list, it exits without changing the stock universe.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f".env file not found: {path}")

    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        # Support common .env style: TRADING_ENV=mock  # comment
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


def clean_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    # Kiwoom often prefixes signed prices/ratios with +/-. For volume/value, keep digits.
    digits = re.sub(r"[^0-9-]", "", text)
    if digits in ("", "-", "+"):
        return None
    try:
        return abs(int(digits))
    except ValueError:
        return None


def clean_stock_code(value: Any) -> str:
    code = str(value or "").strip()
    # Some Kiwoom responses prefix codes with A.
    if code.startswith("A") and len(code) == 7:
        code = code[1:]
    return code


def get_base_url(trading_env: str) -> str:
    return "https://api.kiwoom.com" if trading_env == "prod" else "https://mockapi.kiwoom.com"


def issue_token(base_url: str, api_key: str, api_secret: str) -> str:
    url = f"{base_url}/oauth2/token"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json",
    }
    payload = {
        "grant_type": "client_credentials",
        "appkey": api_key,
        "secretkey": api_secret,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(f"Token response is not JSON: HTTP {response.status_code}, {response.text[:300]}") from exc

    if response.status_code != 200 or data.get("return_code") != 0:
        raise RuntimeError(
            f"Kiwoom token issue failed: HTTP {response.status_code}, "
            f"return_code={data.get('return_code')}, return_msg={data.get('return_msg')}"
        )
    token = data.get("token")
    if not token:
        raise RuntimeError(f"Kiwoom token missing in response keys={list(data.keys())}")
    return str(token)


def request_kospi_top50(base_url: str, token: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = f"{base_url}/api/dostk/rkinfo"
    headers = {
        "Authorization": f"Bearer {token}",
        "authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "api-id": "ka10030",
    }
    body = {
        "mrkt_tp": "001",       # KOSPI
        "sort_tp": "1",         # by trading volume
        "mang_stk_incls": "0",  # include all (as Kiwoom requires one of enum values)
        "crd_tp": "0",
        "trde_qty_tp": "0",
        "pric_tp": "0",
        "trde_prica_tp": "0",
        "mrkt_open_tp": "0",
        "stex_tp": "1",         # KRX
    }

    last_error: Exception | None = None
    for attempt in range(1, 4):
        response = requests.post(url, headers=headers, json=body, timeout=30)
        if response.status_code == 429:
            wait = 10 * attempt
            print(f"⚠️ Kiwoom rate limit(429). {wait}s 대기 후 재시도 {attempt}/3", flush=True)
            time.sleep(wait)
            continue
        try:
            data = response.json()
        except Exception as exc:
            last_error = RuntimeError(f"ka10030 non-JSON response: HTTP {response.status_code}, {response.text[:500]}")
            break

        if response.status_code == 200 and data.get("return_code") == 0:
            rows = data.get("tdy_trde_qty_upper", [])
            if not isinstance(rows, list):
                raise RuntimeError(f"Unexpected ka10030 rows type: {type(rows).__name__}, keys={list(data.keys())}")
            return rows[:50], data

        last_error = RuntimeError(
            f"ka10030 failed: HTTP {response.status_code}, "
            f"return_code={data.get('return_code')}, return_msg={data.get('return_msg')}, keys={list(data.keys())}"
        )
        # return_code 5 is Kiwoom request limit; wait before retry.
        if data.get("return_code") in (5, "5"):
            wait = 10 * attempt
            print(f"⚠️ Kiwoom return_code=5. {wait}s 대기 후 재시도 {attempt}/3", flush=True)
            time.sleep(wait)
            continue
        break

    raise last_error or RuntimeError("ka10030 failed without detailed error")


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    collected_at = datetime.now(timezone.utc)
    seen: set[str] = set()

    for idx, raw in enumerate(rows, start=1):
        code = clean_stock_code(raw.get("stk_cd"))
        name = str(raw.get("stk_nm") or "").strip()
        if not code or not name:
            print(f"⚠️ skip invalid row rank={idx}: code={code!r}, name={name!r}", flush=True)
            continue
        if code in seen:
            continue
        seen.add(code)
        normalized.append(
            {
                "rank": idx,
                "stock_code": code,
                "stock_name": name,
                "market": "KOSPI",
                "volume": clean_int(raw.get("trde_qty")),
                "trading_value": clean_int(raw.get("trde_amt")),
                "is_active": True,
                "source": "kiwoom:ka10030",
                "collected_at": collected_at,
            }
        )
    return normalized


def upsert_kospi_top50(database_url: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        raise RuntimeError("No normalized rows to upsert; DB unchanged.")

    sql_deactivate = "UPDATE kospi_top50 SET is_active = false, updated_at = NOW() WHERE is_active = true"
    sql_upsert = """
        INSERT INTO kospi_top50 (
            rank, stock_code, stock_name, market, volume, trading_value,
            is_active, source, collected_at, updated_at
        ) VALUES (
            %(rank)s, %(stock_code)s, %(stock_name)s, %(market)s, %(volume)s, %(trading_value)s,
            %(is_active)s, %(source)s, %(collected_at)s, NOW()
        )
        ON CONFLICT (stock_code) DO UPDATE SET
            rank = EXCLUDED.rank,
            stock_name = EXCLUDED.stock_name,
            market = EXCLUDED.market,
            volume = EXCLUDED.volume,
            trading_value = EXCLUDED.trading_value,
            is_active = true,
            source = EXCLUDED.source,
            collected_at = EXCLUDED.collected_at,
            updated_at = NOW()
    """
    with psycopg.connect(database_url, connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_deactivate)
            cur.executemany(sql_upsert, rows)
            cur.execute("SELECT COUNT(*) FROM kospi_top50 WHERE is_active = true")
            active_count = int(cur.fetchone()[0])
        conn.commit()
    return active_count


def verify(database_url: str) -> list[tuple[Any, ...]]:
    with psycopg.connect(database_url, connect_timeout=20, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rank, stock_code, stock_name, volume, trading_value, collected_at
                FROM kospi_top50
                WHERE is_active = true
                ORDER BY rank ASC
                LIMIT 10
                """
            )
            return cur.fetchall()


def main() -> int:
    env = load_env()
    required = ["DATABASE_URL", "KIWOOM_REST_API_KEY", "KIWOOM_REST_API_SECRET"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        print(f"❌ Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        return 2

    trading_env = env.get("TRADING_ENV", "mock").strip().lower() or "mock"
    if trading_env not in {"mock", "prod"}:
        print(f"⚠️ Unknown TRADING_ENV={trading_env!r}; using mock", flush=True)
        trading_env = "mock"
    base_url = get_base_url(trading_env)

    print(f"🚀 KOSPI TOP50 수집 시작: env={trading_env}, base_url={base_url}", flush=True)
    token = issue_token(base_url, env["KIWOOM_REST_API_KEY"], env["KIWOOM_REST_API_SECRET"])
    print("✅ Kiwoom OAuth 토큰 발급 성공", flush=True)

    raw_rows, raw_response = request_kospi_top50(base_url, token)
    if not raw_rows:
        print("❌ Kiwoom ka10030 응답은 정상이나 종목 리스트가 비어있습니다. DB 변경 없음.", file=sys.stderr)
        print(f"응답 키: {list(raw_response.keys())}", file=sys.stderr)
        return 3

    rows = normalize_rows(raw_rows)
    if len(rows) < 10:
        print(f"❌ 정상화된 종목 수가 너무 적습니다: {len(rows)}개. DB 변경 없음.", file=sys.stderr)
        return 4

    active_count = upsert_kospi_top50(env["DATABASE_URL"], rows)
    top10 = verify(env["DATABASE_URL"])

    print(f"✅ DB 저장 완료: active kospi_top50={active_count}개, 이번 수집={len(rows)}개", flush=True)
    print("\n상위 10개:")
    for rank, code, name, volume, trading_value, collected_at in top10:
        print(f"{rank:>2}. {code} {name} | 거래량={volume:,} | 거래대금={trading_value:,} | 수집={collected_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
