"""Small Supabase REST helper for workflow scripts.

The helper never prints secrets. It uses service-role key when available and
falls back to anon key for read-only checks.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_env(env_path: Path | None = None) -> dict[str, str]:
    env_path = env_path or PROJECT_ROOT / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return out


class SupabaseRestError(RuntimeError):
    pass


class SupabaseRestClient:
    def __init__(self, env: dict[str, str] | None = None):
        self.env = env or read_env()
        self.url = (self.env.get("SUPABASE_URL") or "").rstrip("/")
        self.key = self.env.get("SUPABASE_SERVICE_ROLE_KEY") or self.env.get("SUPABASE_ANON_KEY")
        if not self.url or not self.key:
            raise SupabaseRestError("missing_supabase_url_or_key")

    def get(self, table: str, params: dict[str, str] | None = None, *, timeout: int = 20) -> list[dict[str, Any]]:
        query = urlencode(params or {})
        endpoint = f"{self.url}/rest/v1/{table}" + (f"?{query}" if query else "")
        req = Request(
            endpoint,
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Accept": "application/json",
                "Prefer": "count=exact",
            },
            method="GET",
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                data = json.loads(body) if body else []
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[-1000:]
            raise SupabaseRestError(f"http_{exc.code}_{table}: {body}") from exc
        except URLError as exc:
            raise SupabaseRestError(f"url_error_{table}: {exc.reason}") from exc
        if not isinstance(data, list):
            raise SupabaseRestError(f"unexpected_rest_shape_{table}")
        return [row for row in data if isinstance(row, dict)]


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
