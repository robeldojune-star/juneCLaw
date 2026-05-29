"""Inspect intraday_prices rows without printing secrets."""
from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError  # noqa: E402


def main() -> int:
    try:
        sb = SupabaseRestClient()
        rows = sb.get(
            "intraday_prices",
            {
                "select": "stock_code,timestamp,time_frame,source,open,high,low,close,volume",
                "order": "timestamp.desc",
                "limit": "50",
            },
            timeout=30,
        )
    except SupabaseRestError as exc:
        print(json.dumps({"ok": False, "blocking_conditions": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    by_source: dict[str, int] = {}
    for r in rows:
        key = f"{r.get('source')}|{r.get('time_frame')}"
        by_source[key] = by_source.get(key, 0) + 1
    print(json.dumps({"ok": True, "sample_count": len(rows), "by_source_timeframe_sample": by_source, "sample": rows[:20]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
