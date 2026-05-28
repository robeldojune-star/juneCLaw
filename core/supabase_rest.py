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

    def _request_json(self, method: str, endpoint: str, *, body: Any = None, timeout: int = 20, prefer: str | None = None) -> Any:
        data = None
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = Request(endpoint, headers=headers, method=method.upper(), data=data)
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else []
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")[-1200:]
            raise SupabaseRestError(f"http_{exc.code}: {raw}") from exc
        except URLError as exc:
            raise SupabaseRestError(f"url_error: {exc.reason}") from exc

    def get(self, table: str, params: dict[str, str] | None = None, *, timeout: int = 20) -> list[dict[str, Any]]:
        query = urlencode(params or {})
        endpoint = f"{self.url}/rest/v1/{table}" + (f"?{query}" if query else "")
        data = self._request_json("GET", endpoint, timeout=timeout, prefer="count=exact")
        if not isinstance(data, list):
            raise SupabaseRestError(f"unexpected_rest_shape_{table}")
        return [row for row in data if isinstance(row, dict)]

    def insert_rows(self, table: str, rows: list[dict[str, Any]], *, timeout: int = 20) -> list[dict[str, Any]]:
        if not rows:
            return []
        endpoint = f"{self.url}/rest/v1/{table}"
        data = self._request_json("POST", endpoint, body=rows, timeout=timeout, prefer="return=representation")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
        return []

    def upsert_rows(self, table: str, rows: list[dict[str, Any]], *, on_conflict: str, timeout: int = 20) -> list[dict[str, Any]]:
        if not rows:
            return []
        endpoint = f"{self.url}/rest/v1/{table}?on_conflict={on_conflict}"
        data = self._request_json("POST", endpoint, body=rows, timeout=timeout, prefer="resolution=merge-duplicates,return=representation")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
        return []


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
