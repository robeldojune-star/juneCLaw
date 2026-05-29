from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import SupabaseRestClient, SupabaseRestError  # noqa: E402


def main() -> int:
    sb = SupabaseRestClient()
    now_utc = datetime.now(timezone.utc)
    since = (now_utc - timedelta(days=5)).isoformat(timespec="seconds")

    rows = sb.get(
        "trading_signals",
        {
            "select": "stock_code,signal_type,strategy,signal_date,score",
            "signal_date": f"gte.{since}",
            "order": "signal_date.desc",
            "limit": "500",
        },
    )

    if not rows:
        print("rows=0")
        return 0

    by_date = Counter()
    by_date_sig = Counter()
    by_strategy = Counter()

    for r in rows:
        sd = str(r.get("signal_date") or "")
        d = sd[:10]
        sig = str(r.get("signal_type") or "")
        strategy = str(r.get("strategy") or "")
        by_date[d] += 1
        by_date_sig[(d, sig)] += 1
        by_strategy[strategy] += 1

    print(f"now_utc={now_utc.isoformat(timespec='seconds')}")
    print(f"rows={len(rows)}")
    print("latest_5_rows:")
    for r in rows[:5]:
        print(r)

    print("counts_by_date:")
    for d, c in sorted(by_date.items(), reverse=True):
        print(d, c)

    print("counts_by_date_signal:")
    for (d, sig), c in sorted(by_date_sig.items(), reverse=True):
        print(d, sig, c)

    print("counts_by_strategy:")
    for s, c in by_strategy.items():
        print(s, c)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SupabaseRestError as exc:
        print(f"SupabaseRestError: {exc}")
        raise SystemExit(2)
