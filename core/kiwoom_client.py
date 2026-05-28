"""Stable Kiwoom REST API client.

This module intentionally centralizes the patterns that were verified against the
real Kiwoom mock server:
- OAuth token endpoint: /oauth2/token
- token response key: token, not access_token
- JSON request body via requests.post(..., json=payload)
- API id in the api-id header
- per-environment .env loading without printing secrets
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re
import time

import requests


class KiwoomAPIError(RuntimeError):
    """Raised when Kiwoom returns HTTP/API-level failure."""

    def __init__(self, message: str, *, api_id: str | None = None, http_status: int | None = None, return_code: Any = None, return_msg: Any = None, response: dict[str, Any] | None = None):
        super().__init__(message)
        self.api_id = api_id
        self.http_status = http_status
        self.return_code = return_code
        self.return_msg = return_msg
        self.response = response or {}


@dataclass(frozen=True)
class KiwoomConfig:
    trading_env: str
    base_url: str
    api_key: str
    api_secret: str
    account_no: str | None = None
    env_path: Path | None = None


@dataclass
class KiwoomResponse:
    api_id: str
    http_status: int
    data: dict[str, Any]
    raw_preview: str

    @property
    def return_code(self) -> Any:
        return self.data.get("return_code")

    @property
    def return_msg(self) -> Any:
        return self.data.get("return_msg")

    @property
    def ok(self) -> bool:
        return self.http_status == 200 and self.return_code in (0, "0")


def load_env_file(env_path: str | Path) -> dict[str, str]:
    """Load .env without exporting values or printing secrets."""
    path = Path(env_path)
    if not path.exists():
        raise FileNotFoundError(f".env file not found: {path}")
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return env


def build_config(env_path: str | Path = ".env", trading_env: str | None = None) -> KiwoomConfig:
    """Build KiwoomConfig from .env.

    Supports either base variable names or environment-suffixed names:
    KIWOOM_REST_API_KEY / KIWOOM_REST_API_KEY_MOCK / KIWOOM_REST_API_KEY_PROD.
    """
    path = Path(env_path)
    env = load_env_file(path)
    selected_env = (trading_env or env.get("TRADING_ENV") or "mock").strip().lower()
    selected_env = "prod" if selected_env == "prod" else "mock"
    suffix = "PROD" if selected_env == "prod" else "MOCK"

    def get_required(key: str) -> str:
        value = env.get(f"{key}_{suffix}") or env.get(key)
        if not value:
            raise KiwoomAPIError(f"Missing required Kiwoom environment variable: {key} or {key}_{suffix}")
        return value

    api_key = get_required("KIWOOM_REST_API_KEY")
    api_secret = get_required("KIWOOM_REST_API_SECRET")
    account_no = env.get(f"KIWOOM_ACCOUNT_NO_{suffix}") or env.get("KIWOOM_ACCOUNT_NO")
    base_url = "https://api.kiwoom.com" if selected_env == "prod" else "https://mockapi.kiwoom.com"
    return KiwoomConfig(
        trading_env=selected_env,
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        account_no=account_no,
        env_path=path,
    )


def clean_int(value: Any, *, abs_value: bool = False) -> int | None:
    """Parse Kiwoom numeric strings.

    Kiwoom frequently returns signed price strings like '+1011' or '-299500'.
    Use abs_value=True for current-price display/calculation when the sign only
    represents direction, not negative value.
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    digits = re.sub(r"[^0-9+-]", "", text)
    if digits in ("", "-", "+"):
        return None
    try:
        parsed = int(digits)
    except ValueError:
        return None
    return abs(parsed) if abs_value else parsed


def money(value: Any) -> str:
    parsed = clean_int(value, abs_value=True)
    return "N/A" if parsed is None else f"{parsed:,}원"


class KiwoomAPIClient:
    """Small stable Kiwoom REST client for read APIs and later order APIs."""

    def __init__(self, config: KiwoomConfig):
        self.config = config
        self._token: str | None = None
        self._token_expires_at = 0.0

    @classmethod
    def from_env(cls, env_path: str | Path = ".env", trading_env: str | None = None) -> "KiwoomAPIClient":
        return cls(build_config(env_path=env_path, trading_env=trading_env))

    def issue_token(self, *, force: bool = False) -> str:
        """Issue or reuse OAuth token. Token is hidden from callers' logs."""
        now = time.time()
        if not force and self._token and now < self._token_expires_at:
            return self._token
        response = requests.post(
            f"{self.config.base_url}/oauth2/token",
            headers={"Content-Type": "application/json; charset=UTF-8", "Accept": "application/json"},
            json={"grant_type": "client_credentials", "appkey": self.config.api_key, "secretkey": self.config.api_secret},
            timeout=30,
        )
        try:
            data = response.json()
        except Exception as exc:
            raise KiwoomAPIError(f"OAuth response is not JSON: HTTP {response.status_code}", api_id="oauth2/token", http_status=response.status_code) from exc
        if response.status_code != 200 or data.get("return_code") != 0 or not data.get("token"):
            raise KiwoomAPIError(
                f"OAuth failed: HTTP {response.status_code}, return_code={data.get('return_code')}, msg={data.get('return_msg')}",
                api_id="oauth2/token",
                http_status=response.status_code,
                return_code=data.get("return_code"),
                return_msg=data.get("return_msg"),
                response=data,
            )
        self._token = str(data["token"])
        # Kiwoom token is effectively about 1 hour; keep a 5 minute safety margin.
        self._token_expires_at = now + 55 * 60
        return self._token

    def post(self, api_id: str, path: str, body: dict[str, Any] | None = None, *, retries: int = 3, raise_on_error: bool = True) -> KiwoomResponse:
        token = self.issue_token()
        payload = body or {}
        last_response: KiwoomResponse | None = None
        for attempt in range(1, retries + 1):
            response = requests.post(
                f"{self.config.base_url}{path}",
                headers={
                    "Content-Type": "application/json;charset=UTF-8",
                    "authorization": f"Bearer {token}",
                    "api-id": api_id,
                    "cont-yn": "N",
                    "next-key": "",
                },
                json=payload,
                timeout=30,
            )
            text_preview = response.text[:500]
            try:
                data = response.json()
            except Exception:
                data = {"_non_json": text_preview}
            last_response = KiwoomResponse(api_id=api_id, http_status=response.status_code, data=data, raw_preview=text_preview)
            if response.status_code == 429 and attempt < retries:
                time.sleep(10 * attempt)
                continue
            break

        assert last_response is not None
        if raise_on_error and not last_response.ok:
            raise KiwoomAPIError(
                f"Kiwoom API failed: api_id={api_id}, HTTP {last_response.http_status}, return_code={last_response.return_code}, msg={last_response.return_msg}",
                api_id=api_id,
                http_status=last_response.http_status,
                return_code=last_response.return_code,
                return_msg=last_response.return_msg,
                response=last_response.data,
            )
        return last_response
