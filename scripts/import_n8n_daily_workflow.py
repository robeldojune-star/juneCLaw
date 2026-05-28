"""Import the draft n8n daily trading workflow via n8n public API.

Requires N8N_URL and N8N_API_KEY in .env or process env. Does not print the API key.
If API key is absent, exits with a clear blocking condition.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.supabase_rest import read_env  # noqa: E402

WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "n8n" / "daily_trading_workflow_v1.import.json"


def main() -> int:
    env = {**read_env(), **os.environ}
    n8n_url = (env.get("N8N_URL") or "http://127.0.0.1:5678").rstrip("/")
    api_key = env.get("N8N_API_KEY")
    blocks: list[str] = []
    if not api_key:
        blocks.append("missing_n8n_api_key")
    if not WORKFLOW_PATH.exists():
        blocks.append("n8n_workflow_import_json_missing")

    if blocks:
        print(json.dumps({
            "ok": False,
            "workflow": "daily_trading_workflow_v1",
            "stage": "n8n_import",
            "status": "blocked",
            "n8n_url": n8n_url,
            "blocking_conditions": blocks,
            "next_actions": ["Create an n8n API key, put N8N_API_KEY in .env or process env, then rerun this script."],
        }, ensure_ascii=False, indent=2))
        return 2

    payload = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    # n8n API usually creates workflows without id/versionId/static import metadata.
    payload.pop("id", None)
    payload.pop("versionId", None)
    req = Request(
        f"{n8n_url}/api/v1/workflows",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", "X-N8N-API-KEY": api_key},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else {}
            out = {"ok": True, "workflow": "daily_trading_workflow_v1", "stage": "n8n_import", "status": "completed", "n8n_url": n8n_url, "imported_workflow_id": data.get("id"), "name": data.get("name")}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[-1200:]
        out = {"ok": False, "workflow": "daily_trading_workflow_v1", "stage": "n8n_import", "status": "blocked", "n8n_url": n8n_url, "blocking_conditions": [f"n8n_api_http_{exc.code}"], "error_tail": body}
    except URLError as exc:
        out = {"ok": False, "workflow": "daily_trading_workflow_v1", "stage": "n8n_import", "status": "blocked", "n8n_url": n8n_url, "blocking_conditions": ["n8n_api_unreachable"], "error": str(exc.reason)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
