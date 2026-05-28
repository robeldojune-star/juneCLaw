#!/usr/bin/env python3
"""Kiwoom mock account/API smoke test using .env without exposing secrets.

Tests 4 safe read-only APIs after OAuth:
1) ka10001 stock basic info
2) kt00004 account evaluation
3) ka10081 daily chart
4) ka10030 KOSPI trading-volume ranking

Also probes ka01690 because older docs say mock is supported; current mock server may reject it.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any
import json
import re
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
STOCK_CODE = "005930"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def env_get(env: dict[str, str], key: str, trading_env: str) -> str | None:
    suffix = "MOCK" if trading_env == "mock" else "PROD"
    return env.get(f"{key}_{suffix}") or env.get(key)


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
        return int(digits)
    except ValueError:
        return None


def money(value: Any) -> str:
    n = clean_int(value)
    return "N/A" if n is None else f"{n:,}원"


def post_json(url: str, headers: dict[str, str], body: dict[str, Any], retries: int = 3) -> tuple[int, dict[str, Any], str]:
    last_text = ""
    for attempt in range(1, retries + 1):
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        last_text = resp.text[:500]
        if resp.status_code == 429 and attempt < retries:
            time.sleep(10 * attempt)
            continue
        try:
            data = resp.json()
        except Exception:
            data = {"_non_json": last_text}
        return resp.status_code, data, last_text
    return 0, {"_error": "retry_exhausted", "text": last_text}, last_text


def issue_token(base_url: str, appkey: str, secretkey: str) -> str:
    status, data, _ = post_json(
        f"{base_url}/oauth2/token",
        {"Content-Type": "application/json; charset=UTF-8", "Accept": "application/json"},
        {"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey},
    )
    if status != 200 or data.get("return_code") != 0 or not data.get("token"):
        raise RuntimeError(f"OAuth failed: HTTP {status}, return_code={data.get('return_code')}, msg={data.get('return_msg')}")
    return str(data["token"])


def call_api(base_url: str, token: str, api_id: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    status, data, text = post_json(
        f"{base_url}{path}",
        {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": api_id,
            "cont-yn": "N",
            "next-key": "",
        },
        body,
    )
    return {"http_status": status, "data": data, "raw_preview": text[:250]}


def is_success(payload: dict[str, Any], allow_missing_return_code: bool = False) -> bool:
    data = payload["data"]
    rc = data.get("return_code")
    if allow_missing_return_code and rc is None and payload["http_status"] == 200:
        return True
    return payload["http_status"] == 200 and rc in (0, "0")


def latest_business_dates(days: int = 7) -> list[str]:
    out: list[str] = []
    d = date.today()
    while len(out) < days:
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return out


def main() -> int:
    print("Kiwoom mock API smoke test")
    print(f"env_file={ENV_PATH}")
    env = load_env()
    trading_env = (env.get("TRADING_ENV") or "mock").strip().lower()
    trading_env = "prod" if trading_env == "prod" else "mock"
    base_url = "https://mockapi.kiwoom.com" if trading_env == "mock" else "https://api.kiwoom.com"
    appkey = env_get(env, "KIWOOM_REST_API_KEY", trading_env)
    secretkey = env_get(env, "KIWOOM_REST_API_SECRET", trading_env)
    account_no = env_get(env, "KIWOOM_ACCOUNT_NO", trading_env)

    print(f"trading_env={trading_env}")
    print(f"base_url={base_url}")
    print(f"api_key_present={bool(appkey)}")
    print(f"api_secret_present={bool(secretkey)}")
    print(f"account_no_present={bool(account_no)}")
    if trading_env != "mock":
        print("ERROR: 안전상 이 스크립트는 모의투자(mock) 확인용입니다. TRADING_ENV를 mock으로 설정하세요.")
        return 2
    if not all([appkey, secretkey, account_no]):
        print("ERROR: KIWOOM 필수 환경변수가 부족합니다.")
        return 2

    token = issue_token(base_url, appkey, secretkey)
    print("\n[0] OAuth token: OK (token hidden)")

    results: list[tuple[str, bool, dict[str, Any]]] = []

    # 1) Stock info
    r1 = call_api(base_url, token, "ka10001", "/api/dostk/stkinfo", {"stk_cd": STOCK_CODE})
    d1 = r1["data"]
    summary1 = {
        "api": "ka10001",
        "ok": is_success(r1),
        "http_status": r1["http_status"],
        "return_code": d1.get("return_code"),
        "return_msg": d1.get("return_msg"),
        "stk_cd": d1.get("stk_cd"),
        "stk_nm": d1.get("stk_nm"),
        "cur_prc": d1.get("cur_prc"),
        "per": d1.get("per"),
        "pbr": d1.get("pbr"),
    }
    results.append(("ka10001 주식기본정보", summary1["ok"], summary1))

    # 2) Account evaluation kt00004. Include account if accepted by env; token also carries auth.
    r2 = call_api(base_url, token, "kt00004", "/api/dostk/acnt", {"accno": account_no, "qry_tp": "1", "dmst_stex_tp": "KRX"})
    d2 = r2["data"]
    holdings = d2.get("stk_acnt_evlt_prst") or d2.get("holdings") or d2.get("data", {}).get("holdings") or []
    summary2 = {
        "api": "kt00004",
        "ok": is_success(r2),
        "http_status": r2["http_status"],
        "return_code": d2.get("return_code"),
        "return_msg": d2.get("return_msg"),
        "entr": money(d2.get("entr") or d2.get("deposit") or d2.get("data", {}).get("deposit")),
        "tot_est_amt": money(d2.get("tot_est_amt") or d2.get("estimated_asset") or d2.get("data", {}).get("estimated_asset")),
        "holdings_count": len(holdings) if isinstance(holdings, list) else "N/A",
        "sample_holding_keys": list(holdings[0].keys())[:8] if isinstance(holdings, list) and holdings else [],
    }
    results.append(("kt00004 계좌평가현황", summary2["ok"], summary2))

    # 3) Daily chart ka10081
    r3 = call_api(base_url, token, "ka10081", "/api/dostk/chart", {"stk_cd": STOCK_CODE, "base_dt": date.today().strftime("%Y%m%d"), "upd_stkpc_tp": "1"})
    d3 = r3["data"]
    rows = d3.get("stk_dt_pole_chart_qry") or []
    first = rows[0] if isinstance(rows, list) and rows else {}
    summary3 = {
        "api": "ka10081",
        "ok": is_success(r3, allow_missing_return_code=True) and isinstance(rows, list) and len(rows) > 0,
        "http_status": r3["http_status"],
        "return_code": d3.get("return_code"),
        "return_msg": d3.get("return_msg"),
        "rows": len(rows) if isinstance(rows, list) else "N/A",
        "latest_dt": first.get("dt"),
        "latest_close": money(first.get("cur_prc")),
        "response_keys": list(d3.keys())[:10],
    }
    results.append(("ka10081 일봉차트", summary3["ok"], summary3))

    # 4) KOSPI trading volume ranking ka10030
    r4 = call_api(base_url, token, "ka10030", "/api/dostk/rkinfo", {
        "mrkt_tp": "001",
        "sort_tp": "1",
        "mang_stk_incls": "0",
        "crd_tp": "0",
        "trde_qty_tp": "0",
        "pric_tp": "0",
        "trde_prica_tp": "0",
        "mrkt_open_tp": "0",
        "stex_tp": "1",
    })
    d4 = r4["data"]
    rank_rows = d4.get("tdy_trde_qty_upper") or []
    sample = rank_rows[:3] if isinstance(rank_rows, list) else []
    summary4 = {
        "api": "ka10030",
        "ok": is_success(r4) and isinstance(rank_rows, list) and len(rank_rows) > 0,
        "http_status": r4["http_status"],
        "return_code": d4.get("return_code"),
        "return_msg": d4.get("return_msg"),
        "rows": len(rank_rows) if isinstance(rank_rows, list) else "N/A",
        "first_items": [
            {
                "stk_cd": x.get("stk_cd"),
                "stk_nm": x.get("stk_nm"),
                "cur_prc": x.get("cur_prc"),
                "trde_qty": x.get("trde_qty"),
            }
            for x in sample
        ],
    }
    results.append(("ka10030 KOSPI 거래량상위", summary4["ok"], summary4))

    # Optional probe) Daily balance PnL ka01690. Try latest business dates until valid response.
    daily_attempts = []
    selected_r5 = None
    selected_date = None
    for ymd in latest_business_dates(7):
        r = call_api(base_url, token, "ka01690", "/api/dostk/acnt", {"accno": account_no, "qry_dt": ymd})
        dd = r["data"]
        daily_attempts.append({"date": ymd, "http_status": r["http_status"], "return_code": dd.get("return_code"), "return_msg": dd.get("return_msg"), "tot_evlt_amt": dd.get("tot_evlt_amt")})
        if is_success(r):
            selected_r5 = r
            selected_date = ymd
            # accept first normal response, even if amount is 0; report it
            break
    d5 = selected_r5["data"] if selected_r5 else {}
    optional_ka01690 = {
        "api": "ka01690",
        "ok": bool(selected_r5 and is_success(selected_r5)),
        "selected_date": selected_date,
        "return_code": d5.get("return_code"),
        "return_msg": d5.get("return_msg"),
        "tot_evlt_amt": money(d5.get("tot_evlt_amt") or d5.get("tot_est_amt")),
        "tot_evltv_prft": money(d5.get("tot_evltv_prft")),
        "tot_prft_rt": d5.get("tot_prft_rt"),
        "attempts": daily_attempts,
    }

    print("\n=== API results ===")
    for name, ok, summary in results:
        print(f"\n[{name}] {'OK' if ok else 'FAIL'}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n[optional: ka01690 일별잔고수익률 probe]")
    print(json.dumps(optional_ka01690, ensure_ascii=False, indent=2))

    ok_all = all(ok for _, ok, _ in results)
    print(f"\nRESULT={'OK' if ok_all else 'CHECK_NEEDED'}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
