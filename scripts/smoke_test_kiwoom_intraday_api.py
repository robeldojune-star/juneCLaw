"""Smoke test Kiwoom intraday/minute candidate APIs for opening strategies.

This script intentionally prints only structural summaries, not secrets.
It verifies whether ka10005/ka10006 on /api/dostk/mrkcond can provide
fields needed by opening_multi_factor_v1.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient, KiwoomAPIError  # noqa: E402


REQUIRED_FIELDS = {
    "open_pric",
    "high_pric",
    "low_pric",
    "close_pric",
    "trde_qty",
}


def summarize_response(api_id: str, data: dict) -> dict:
    keys = sorted(str(k) for k in data.keys())
    list_fields = []
    sample = None
    for key, value in data.items():
        if isinstance(value, list):
            list_fields.append({"key": key, "length": len(value)})
            if value and isinstance(value[0], dict) and sample is None:
                sample = {"list_key": key, "sample_keys": sorted(str(k) for k in value[0].keys())[:80]}
    top_required_present = sorted(REQUIRED_FIELDS.intersection(data.keys()))
    nested_required_present = []
    if sample:
        nested_required_present = sorted(REQUIRED_FIELDS.intersection(sample["sample_keys"]))
    return {
        "api_id": api_id,
        "return_code": data.get("return_code"),
        "return_msg": data.get("return_msg"),
        "top_level_keys": keys[:80],
        "list_fields": list_fields,
        "sample": sample,
        "required_fields_top_level": top_required_present,
        "required_fields_nested_sample": nested_required_present,
        "usable_candidate": bool(top_required_present or nested_required_present),
    }


def main() -> int:
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "005930"
    client = KiwoomAPIClient.from_env(PROJECT_ROOT / ".env")
    results = []
    for api_id in ["ka10005", "ka10006", "ka10007"]:
        try:
            response = client.post(api_id, "/api/dostk/mrkcond", {"stk_cd": stock_code}, raise_on_error=False)
            results.append(summarize_response(api_id, response.data))
        except KiwoomAPIError as exc:
            results.append({
                "api_id": api_id,
                "ok": False,
                "error": str(exc),
                "return_code": exc.return_code,
                "return_msg": exc.return_msg,
            })
        except Exception as exc:  # noqa: BLE001
            results.append({"api_id": api_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    out = {
        "ok": any(item.get("usable_candidate") for item in results),
        "workflow": "smoke_test_kiwoom_intraday_api",
        "stock_code": stock_code,
        "results": results,
        "next_action": "Use the first usable candidate for intraday collection; if none usable, inspect Kiwoom docs for minute-chart TR.",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
