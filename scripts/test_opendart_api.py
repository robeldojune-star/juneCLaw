#!/usr/bin/env python3
"""OpenDART API smoke test using .env without printing secrets."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import sys
import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
BASE = "https://opendart.fss.or.kr/api"
SAMSUNG_CORP_CODE = "00126380"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        return env
    for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def call(endpoint: str, params: dict[str, str]) -> dict:
    url = f"{BASE}/{endpoint}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def summarize_list(data: dict) -> dict:
    rows = data.get("list") or []
    return {
        "status": data.get("status"),
        "message": data.get("message"),
        "total_count": data.get("total_count"),
        "returned": len(rows),
        "first_items": [
            {
                "rcept_dt": x.get("rcept_dt"),
                "corp_name": x.get("corp_name"),
                "report_nm": x.get("report_nm"),
                "rcept_no": x.get("rcept_no"),
            }
            for x in rows[:3]
        ],
    }


def summarize_financials(data: dict) -> dict:
    rows = data.get("list") or []
    wanted = {"매출액", "영업이익", "당기순이익", "자산총계", "부채총계", "자본총계"}
    picked = []
    seen = set()
    for x in rows:
        nm = x.get("account_nm")
        if nm in wanted and nm not in seen:
            picked.append({
                "account_nm": nm,
                "fs_nm": x.get("fs_nm"),
                "sj_nm": x.get("sj_nm"),
                "thstrm_amount": x.get("thstrm_amount"),
            })
            seen.add(nm)
    return {
        "status": data.get("status"),
        "message": data.get("message"),
        "rows": len(rows),
        "picked_accounts": picked[:8],
    }


def main() -> int:
    env = load_env()
    api_key = env.get("DART_API_KEY") or env.get("OPENDART_API_KEY")
    print("OpenDART API smoke test")
    print(f"env_file={ENV_PATH}")
    print(f"api_key_present={bool(api_key)}")
    print(f"api_key_var={'OPENDART_API_KEY' if env.get('OPENDART_API_KEY') else 'DART_API_KEY' if env.get('DART_API_KEY') else 'NONE'}")
    if not api_key:
        print("ERROR: .env에 DART_API_KEY 또는 OPENDART_API_KEY가 없습니다.")
        return 2

    common = {"crtfc_key": api_key, "corp_code": SAMSUNG_CORP_CODE}

    company = call("company.json", common)
    company_summary = {
        "status": company.get("status"),
        "message": company.get("message"),
        "corp_name": company.get("corp_name"),
        "stock_code": company.get("stock_code"),
        "ceo_nm": company.get("ceo_nm"),
    }
    print("\n[1] company.json")
    print(json.dumps(company_summary, ensure_ascii=False, indent=2))

    today = date.today().strftime("%Y%m%d")
    disclosures = call("list.json", {
        **common,
        "bgn_de": f"{date.today().year}0101",
        "end_de": today,
        "page_count": "5",
    })
    print("\n[2] list.json recent disclosures")
    print(json.dumps(summarize_list(disclosures), ensure_ascii=False, indent=2))

    # OpenDART reprt_code: 11011=사업보고서(annual), 11012=반기, 11013=1분기, 11014=3분기
    financials = call("fnlttSinglAcntAll.json", {
        **common,
        "bsns_year": str(date.today().year - 1),
        "reprt_code": "11011",
        "fs_div": "CFS",
    })
    print("\n[3] fnlttSinglAcntAll.json annual CFS")
    print(json.dumps(summarize_financials(financials), ensure_ascii=False, indent=2))

    ok = all(x.get("status") == "000" for x in [company, disclosures, financials])
    print(f"\nRESULT={'OK' if ok else 'CHECK_NEEDED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
