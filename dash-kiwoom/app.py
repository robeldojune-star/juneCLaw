#!/usr/bin/env python3
"""Dash Kiwoom dashboard backend.

This dashboard is intentionally read-only.  The current master trading plan keeps
paper/real orders blocked until the backtest and paper gates pass.  The backend
therefore exposes monitoring/status APIs and Socket.IO updates, but it does not
place orders.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
DATA_FILE = APP_ROOT / "data" / "signals.csv"
CADDY_SITES: list[dict[str, Any]] = [
    {
        "name": "Hermes WebUI",
        "domain": "hermes-june.duckdns.org",
        "url": "https://hermes-june.duckdns.org/",
        "upstream": "127.0.0.1:8787",
        "category": "AI Agent",
        "description": "Hermes WebUI 대화형 작업 공간",
        "icon": "🤖",
        "expected": [200, 301, 302, 307, 308],
    },
    {
        "name": "Hermes Dashboard",
        "domain": "dash-june.duckdns.org",
        "url": "https://dash-june.duckdns.org/",
        "upstream": "127.0.0.1:9119",
        "category": "Hermes Ops",
        "description": "Hermes 내부 대시보드 / 세션 관리",
        "icon": "🧭",
        "expected": [200, 301, 302, 307, 308, 401, 403],
    },
    {
        "name": "Code Server",
        "domain": "code-june.duckdns.org",
        "url": "https://code-june.duckdns.org/",
        "upstream": "127.0.0.1:8080",
        "category": "IDE",
        "description": "브라우저 기반 VS Code 개발 환경",
        "icon": "💻",
        "expected": [200, 301, 302, 307, 308, 401, 403],
    },
    {
        "name": "n8n Automation",
        "domain": "n8n-june.duckdns.org",
        "url": "https://n8n-june.duckdns.org/",
        "upstream": "127.0.0.1:5678",
        "category": "Automation",
        "description": "뉴스·공시·워크플로우 자동화 허브",
        "icon": "🔁",
        "expected": [200, 301, 302, 307, 308, 401, 403],
    },
    {
        "name": "Dash Kiwoom",
        "domain": "dash-kiwoom.duckdns.org",
        "url": "https://dash-kiwoom.duckdns.org/",
        "upstream": "127.0.0.1:3000",
        "category": "Trading OS",
        "description": "키움 AI 트레이딩 read-only 터미널",
        "icon": "📈",
        "expected": [200],
    },
]
_caddy_cache: dict[str, Any] = {"fetched_at": 0.0, "data": None}
_caddy_lock = threading.Lock()
_n8n_cache: dict[str, Any] = {"fetched_at": 0.0, "data": None}
_n8n_lock = threading.Lock()

# Ensure we can import project modules when the dashboard is launched directly.
sys.path.insert(0, str(PROJECT_ROOT / "shared"))
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from core.kiwoom_client import KiwoomAPIClient
except Exception:  # pragma: no cover - dashboard should still render without Kiwoom deps
    KiwoomAPIClient = None  # type: ignore[assignment]

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("DASH_KIWOOM_SECRET", "dash-kiwoom-readonly")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Static operating state extracted from docs/strategies/00_master_trading_plan.md
MASTER_STATUS: dict[str, Any] = {
    "generated_from": "docs/strategies/00_master_trading_plan.md + master_plan.md",
    "updated_at": "2026-06-03 11:25 KST",
    "operating_mode": "read_only_surveillance",
    "order_gate": {
        "real": "blocked",
        "paper": "blocked",
        "signal_recording": "allowed",
        "backtest": "allowed",
        "reason": "ka10080 백테스트/paper gate 통과 전까지 주문 금지",
    },
    "primary_strategy": "opening_multi_factor_v1",
    "secondary_strategy": "RSI/CCI Disparity + Fujimoto 1-2-6 보조 검증",
    "data_sources": [
        {"name": "과거 1분봉 백테스트", "source": "Kiwoom REST ka10080", "status": "allowed"},
        {"name": "장중 감시", "source": "Kiwoom ka10006 snapshot_1m", "status": "operating"},
        {"name": "일봉/후속 수익률", "source": "daily_prices", "status": "needs_backfill"},
        {"name": "공시/재무", "source": "OpenDART", "status": "candidate"},
        {"name": "계좌 상태", "source": "Kiwoom kt00004", "status": "risk_check_only"},
    ],
    "phases": [
        {"phase": "Phase 1", "title": "데이터 수집 안정화", "status": "partial_done", "progress": 70},
        {"phase": "Phase 2", "title": "ka10080 과거 1분봉 백테스트", "status": "in_progress", "progress": 45},
        {"phase": "Phase 3", "title": "신호 활용 gap 분석", "status": "in_progress", "progress": 35},
        {"phase": "Phase 4", "title": "진입 변형 누적 비교", "status": "sample_limited", "progress": 25},
        {"phase": "Phase 5", "title": "Paper 검증", "status": "blocked", "progress": 0},
        {"phase": "Phase 6", "title": "Real pilot", "status": "blocked", "progress": 0},
    ],
    "priority_tasks": [
        "ka10080 분봉 backfill 확대",
        "technical_score_v1 신호 backfill",
        "BLOCKED vs INTRADAY 후속 수익률 재계산",
        "paper gate 수치 확정",
        "리스크/포지션 사이징 로직 구현",
        "센티멘트 필터 프로토타입",
        "Walk-Forward Validation",
        "Paper Trading 일별 주문 내역 CSV/DB 로깅",
    ],
}

_account_cache: dict[str, Any] = {"env": None, "data": None, "error": None, "fetched_at": None}
_account_lock = threading.Lock()
_chart_cache: dict[str, Any] = {"key": None, "data": None, "error": None, "fetched_at": None}
_chart_lock = threading.Lock()
PAPER_LEDGER_FILE = APP_ROOT / "data" / "paper_ledger.csv"
PAPER_LEDGER_COLUMNS = [
    "time",
    "env",
    "stock",
    "side",
    "qty",
    "price",
    "reference_signal_price",
    "assumed_fill_price",
    "fee_bps_one_way",
    "slippage_bps_one_way",
    "impact_bps_one_way",
    "estimated_fee",
    "estimated_cash_effect",
    "reason",
    "status",
    "mode",
    "pnl",
]
BACKTEST_READINESS_JSON = PROJECT_ROOT / "reports" / "backtest_readiness_latest.json"
BACKTEST_REPORT_FILE = PROJECT_ROOT / "docs" / "strategies" / "ka10080_minute_backtest_pipeline_report_2026-05-29.md"
SNAPSHOT_SOURCE = "kiwoom_ka10006_snapshot"
SNAPSHOT_TIME_FRAME = "snapshot_1m"


def load_environment(env_name: str) -> Path:
    """Load mock/prod environment file without mixing credentials."""
    env_path = PROJECT_ROOT / "envs" / env_name / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)
    os.environ["TRADING_ENV"] = env_name
    return env_path


def _parse_signal_time(value: Any) -> pd.Timestamp:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return pd.NaT
    # Expected format from scripts/run_strategy.py: YYYYMMDDHHMMSS
    parsed = pd.to_datetime(text, format="%Y%m%d%H%M%S", errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(text, errors="coerce")
    return parsed


def load_signals() -> pd.DataFrame:
    """Load and normalize dashboard signals from CSV.

    Kiwoom often prefixes prices with a sign.  For display purposes the dashboard
    uses absolute prices while keeping the signal type as the directional source
    of truth.
    """
    columns = ["time", "stock", "type", "price", "profit"]
    if not DATA_FILE.is_file():
        return pd.DataFrame(columns=columns)

    df = pd.read_csv(DATA_FILE, dtype={"time": str, "stock": str, "type": str})
    for col in columns:
        if col not in df.columns:
            df[col] = None

    df = df[columns].copy()
    df["parsed_time"] = df["time"].apply(_parse_signal_time)
    df["stock"] = df["stock"].fillna("").astype(str).str.zfill(6)
    df["type"] = df["type"].fillna("unknown").astype(str).str.lower().str.strip()
    df["price"] = pd.to_numeric(df["price"], errors="coerce").abs()
    df["profit"] = pd.to_numeric(df["profit"], errors="coerce")
    df = df.dropna(subset=["parsed_time"])
    df = df.drop_duplicates(subset=["parsed_time", "stock", "type", "price"], keep="last")
    return df.sort_values("parsed_time", ascending=False).reset_index(drop=True)


def serialize_signals(df: pd.DataFrame, limit: int = 50) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in df.head(limit).to_dict(orient="records"):
        ts = row.get("parsed_time")
        if isinstance(ts, pd.Timestamp):
            row["time"] = ts.strftime("%Y%m%d%H%M%S")
            row["display_time"] = ts.strftime("%m/%d %H:%M")
            row["iso_time"] = ts.isoformat()
        for key, value in list(row.items()):
            if isinstance(value, float) and pd.isna(value):
                row[key] = None
            if isinstance(value, pd.Timestamp):
                row[key] = value.isoformat()
        records.append(row)
    return records


def calculate_signal_metrics(df: pd.DataFrame) -> dict[str, Any]:
    raw_rows = 0
    if DATA_FILE.is_file():
        try:
            raw_rows = max(sum(1 for _ in DATA_FILE.open("r", encoding="utf-8")) - 1, 0)
        except OSError:
            raw_rows = 0

    latest = None
    if not df.empty:
        latest_row = df.iloc[0]
        latest = {
            "time": latest_row["parsed_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "stock": latest_row["stock"],
            "type": latest_row["type"],
            "price": float(latest_row["price"]) if pd.notna(latest_row["price"]) else None,
        }

    counts = df["type"].value_counts().to_dict() if not df.empty else {}
    return {
        "raw_rows": raw_rows,
        "unique_rows": int(len(df)),
        "duplicates_removed": int(max(raw_rows - len(df), 0)),
        "buy_count": int(counts.get("buy", 0)),
        "sell_count": int(counts.get("sell", 0)),
        "latest": latest,
        "data_file": str(DATA_FILE),
        "file_exists": DATA_FILE.is_file(),
    }


def build_market_overview(df: pd.DataFrame) -> dict[str, Any]:
    """Build honest market-monitor cards from data the dashboard actually has.

    The previous UI displayed hard-coded KOSPI/KOSDAQ/USD/BTC numbers. Until a
    real index/FX/crypto feed is wired in, this section must show dashboard data
    freshness and signal-monitor status instead of pretending to be live market
    quotes.
    """
    # Signal timestamps are produced in KST as naive YYYYMMDDHHMMSS strings.
    # The server may run in UTC, so compare freshness against KST wall time.
    now = datetime.utcnow() + timedelta(hours=9)
    latest_time = None
    latest_age_min = None
    latest_stock = None
    latest_type = None
    latest_price = None
    session_start = None
    session_rows = 0
    session_buy = 0
    session_sell = 0

    if not df.empty:
        latest = df.iloc[0]
        latest_ts = latest.get("parsed_time")
        if isinstance(latest_ts, pd.Timestamp) and not pd.isna(latest_ts):
            latest_time = latest_ts.strftime("%Y-%m-%d %H:%M:%S")
            latest_age_min = max(0, round((now - latest_ts.to_pydatetime()).total_seconds() / 60, 1))
            day_df = df[df["parsed_time"].dt.date == latest_ts.date()]
            session_rows = int(len(day_df))
            session_buy = int((day_df["type"] == "buy").sum())
            session_sell = int((day_df["type"] == "sell").sum())
            session_start = latest_ts.strftime("%Y-%m-%d")
        latest_stock = str(latest.get("stock") or "-")
        latest_type = str(latest.get("type") or "-").upper()
        if pd.notna(latest.get("price")):
            latest_price = float(latest.get("price"))

    freshness = "no_data"
    if latest_age_min is not None:
        if latest_age_min <= 5:
            freshness = "live"
        elif latest_age_min <= 60:
            freshness = "delayed"
        else:
            freshness = "stale"

    return {
        "source": "signals.csv",
        "feedStatus": freshness,
        "indexFeedStatus": "not_connected",
        "disclaimer": "KOSPI/KOSDAQ/USD/BTC 실시간 시세는 아직 연결되지 않았습니다.",
        "latestTime": latest_time,
        "latestAgeMin": latest_age_min,
        "latestStock": latest_stock,
        "latestType": latest_type,
        "latestPrice": latest_price,
        "sessionDate": session_start,
        "sessionSignals": session_rows,
        "sessionBuy": session_buy,
        "sessionSell": session_sell,
        "totalSignals": int(len(df)),
        "dataFile": str(DATA_FILE),
    }


def build_chart_data(df: pd.DataFrame, limit: int = 80) -> list[dict[str, float | int]]:
    if df.empty:
        return []
    chart_df = (
        df.sort_values("parsed_time")
        .drop_duplicates(subset=["parsed_time"], keep="last")
        .tail(limit)
    )
    candles: list[dict[str, float | int]] = []
    last_close: float | None = None
    for row in chart_df.itertuples(index=False):
        price = getattr(row, "price", None)
        ts = getattr(row, "parsed_time", None)
        if pd.isna(price) or not isinstance(ts, pd.Timestamp):
            continue
        close = float(price)
        open_price = last_close if last_close is not None else close
        high = max(open_price, close) * 1.001
        low = min(open_price, close) * 0.999
        candles.append({
            "time": int(ts.timestamp()),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
        })
        last_close = close
    return candles


def _normalize_holdings(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        data = raw.get("data", raw)
    else:
        data = getattr(raw, "data", {})
    holdings = data.get("stk_acnt_evlt_prst", []) if isinstance(data, dict) else []
    normalized = []
    for item in holdings or []:
        normalized.append({
            "stkCode": item.get("stk_cd") or item.get("stkCode") or item.get("stock_code") or "-",
            "stkNm": item.get("stk_nm") or item.get("stkNm") or item.get("name") or "Unknown",
            "avgPrc": _to_number(item.get("avg_prc") or item.get("avgPrc")),
            "rmndQty": _to_number(item.get("rmnd_qty") or item.get("rmndQty")),
            "evltAmt": _to_number(item.get("evlt_amt") or item.get("evltAmt")),
            "plAmt": _to_number(item.get("pl_amt") or item.get("plAmt")),
            "plRt": _to_number(item.get("pl_rt") or item.get("plRt")),
        })
    return normalized


def _to_number(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def get_account_info(env_name: str = "mock", *, force: bool = False) -> dict[str, Any]:
    """Return mock/prod account info for display only.

    Cached to avoid calling Kiwoom every Socket.IO tick.
    """
    with _account_lock:
        now = datetime.now(timezone.utc)
        fetched_at = _account_cache.get("fetched_at")
        cache_age = (now - fetched_at).total_seconds() if fetched_at else None
        if (
            not force
            and _account_cache.get("env") == env_name
            and _account_cache.get("data") is not None
            and cache_age is not None
            and cache_age < 300
        ):
            return _account_cache["data"]

        if KiwoomAPIClient is None:
            data = {"mode": env_name, "holdings": [], "error": "Kiwoom client import failed"}
        else:
            try:
                env_path = load_environment(env_name)
                client = KiwoomAPIClient.from_env(env_path=env_path)
                body = {"qry_tp": "1", "dmst_stex_tp": "KRX"}
                acct_info = client.post("kt00004", "/api/dostk/acnt", body)
                raw_data = getattr(acct_info, "data", acct_info)
                data = {
                    "mode": env_name,
                    "holdings": _normalize_holdings(raw_data),
                    "rawSummary": raw_data if isinstance(raw_data, dict) else {},
                    "fetchedAt": now.isoformat(),
                    "error": None,
                }
            except Exception as exc:  # Keep the dashboard alive if Kiwoom is unavailable.
                data = {"mode": env_name, "holdings": [], "error": str(exc), "fetchedAt": now.isoformat()}

        _account_cache.update({"env": env_name, "data": data, "error": data.get("error"), "fetched_at": now})
        return data


def _mask_account(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) <= 5:
        return "미설정" if not text else "***"
    return f"{text[:3]}***{text[-2:]}"


def _load_env_values(env_name: str) -> dict[str, str]:
    env_path = PROJECT_ROOT / "envs" / env_name / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.split(" #", 1)[0].strip().strip('\"').strip("'")
    return values


def build_account_statuses() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    for env_name in ("mock", "prod"):
        env_values = _load_env_values(env_name)
        info = get_account_info(env_name)
        statuses[env_name] = {
            "mode": env_name,
            "connected": not bool(info.get("error")),
            "error": info.get("error"),
            "accountMasked": _mask_account(env_values.get("KIWOOM_ACCOUNT_NO")),
            "holdingsCount": len(info.get("holdings") or []),
            "fetchedAt": info.get("fetchedAt"),
        }
    return statuses


def _parse_snapshot_timestamp(value: Any) -> pd.Timestamp:
    text = str(value or "").strip()
    if not text:
        return pd.NaT
    return pd.to_datetime(text.replace("Z", "+00:00"), errors="coerce", utc=True)


def build_snapshot_chart_data(preferred_stock: str = "042660", *, limit: int = 180) -> dict[str, Any]:
    """Build chart candles from accumulated ka10006 snapshot_1m rows in Supabase.

    This is read-only. If the preferred stock is not present in the current
    snapshot set, choose the stock with the most recent rows so the dashboard
    reflects real collected data instead of fabricating a series.
    """
    key = ("snapshot_1m", preferred_stock, int(limit))
    with _chart_lock:
        now = datetime.now(timezone.utc)
        fetched_at = _chart_cache.get("fetched_at")
        cache_age = (now - fetched_at).total_seconds() if fetched_at else None
        if _chart_cache.get("key") == key and _chart_cache.get("data") is not None and cache_age is not None and cache_age < 60:
            return _chart_cache["data"]

        try:
            from core.supabase_rest import SupabaseRestClient, num

            rows = SupabaseRestClient().get(
                "intraday_prices",
                {
                    "select": "stock_code,timestamp,time_frame,source,open,high,low,close,volume,trading_value",
                    "time_frame": f"eq.{SNAPSHOT_TIME_FRAME}",
                    "source": f"eq.{SNAPSHOT_SOURCE}",
                    "order": "timestamp.desc",
                    "limit": str(max(int(limit) * 12, 500)),
                },
                timeout=30,
            )
            if not rows:
                raise RuntimeError("snapshot_1m rows not found")

            per_code: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                code = str(row.get("stock_code") or "").zfill(6)
                if not code:
                    continue
                per_code.setdefault(code, []).append(row)
            selected_stock = preferred_stock if preferred_stock in per_code else max(per_code, key=lambda code: len(per_code[code]))

            candles = []
            quality_errors = 0
            latest_ts = None
            for row in per_code.get(selected_stock, []):
                ts = _parse_snapshot_timestamp(row.get("timestamp"))
                if pd.isna(ts):
                    quality_errors += 1
                    continue
                open_price = abs(num(row.get("open")))
                high = abs(num(row.get("high")))
                low = abs(num(row.get("low")))
                close = abs(num(row.get("close")))
                volume = abs(num(row.get("volume")))
                if min(open_price, high, low, close) <= 0 or high < max(open_price, close) or low > min(open_price, close):
                    quality_errors += 1
                    continue
                latest_ts = ts if latest_ts is None or ts > latest_ts else latest_ts
                candles.append({
                    "time": int(ts.timestamp()),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": round(volume, 2),
                })
            candles = sorted({item["time"]: item for item in candles}.values(), key=lambda item: item["time"])[-int(limit):]
            latest_lag_minutes = None
            if latest_ts is not None:
                latest_lag_minutes = round((now - latest_ts.to_pydatetime()).total_seconds() / 60, 1)
            data = {
                "env": "supabase",
                "stock": selected_stock,
                "requestedStock": preferred_stock,
                "source": "Supabase intraday_prices · ka10006 snapshot_1m",
                "candles": candles,
                "count": len(candles),
                "activeCodes": len(per_code),
                "availableCodes": sorted(per_code.keys()),
                "qualityErrors": quality_errors,
                "latestTimestamp": latest_ts.isoformat() if latest_ts is not None else None,
                "latestLagMinutes": latest_lag_minutes,
                "state": "live" if latest_lag_minutes is not None and latest_lag_minutes <= 15 else "stale" if latest_lag_minutes is not None else "no_data",
                "fetchedAt": now.isoformat(),
                "error": None,
            }
        except Exception as exc:
            data = {
                "env": "supabase",
                "stock": preferred_stock,
                "source": "Supabase intraday_prices · ka10006 snapshot_1m",
                "candles": [],
                "count": 0,
                "state": "error",
                "fetchedAt": now.isoformat(),
                "error": str(exc),
            }
        _chart_cache.update({"key": key, "data": data, "error": data.get("error"), "fetched_at": now})
        return data


def build_real_chart_data(env_name: str = "mock", stock_code: str = "042660", *, limit: int = 120) -> dict[str, Any]:
    """Fetch real Kiwoom ka10080 candles for dashboard display only."""
    key = ("ka10080", env_name, stock_code, int(limit))
    with _chart_lock:
        now = datetime.now(timezone.utc)
        fetched_at = _chart_cache.get("fetched_at")
        cache_age = (now - fetched_at).total_seconds() if fetched_at else None
        if _chart_cache.get("key") == key and _chart_cache.get("data") is not None and cache_age is not None and cache_age < 180:
            return _chart_cache["data"]

        try:
            env_path = load_environment(env_name)
            client = KiwoomAPIClient.from_env(env_path=env_path) if KiwoomAPIClient is not None else None
            if client is None:
                raise RuntimeError("Kiwoom client import failed")
            from core.market_data_service import MarketDataService

            rows = MarketDataService(client).get_minute_chart_raw(stock_code, minute_scope="1", adjusted_price=True)
            candles = []
            for row in rows:
                ts_text = str(row.get("cntr_tm") or "").strip()
                ts = pd.to_datetime(ts_text, format="%Y%m%d%H%M%S", errors="coerce")
                if pd.isna(ts):
                    continue
                open_price = abs(_to_number(row.get("open_pric")))
                high = abs(_to_number(row.get("high_pric")))
                low = abs(_to_number(row.get("low_pric")))
                close = abs(_to_number(row.get("cur_prc")))
                volume = abs(_to_number(row.get("trde_qty")))
                if not all([open_price, high, low, close]):
                    continue
                candles.append({
                    "time": int(ts.timestamp()),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": round(volume, 2),
                })
            candles = sorted(candles, key=lambda item: item["time"])[-int(limit):]
            data = {
                "env": env_name,
                "stock": stock_code,
                "source": "Kiwoom ka10080 1min",
                "candles": candles,
                "count": len(candles),
                "fetchedAt": now.isoformat(),
                "error": None,
            }
        except Exception as exc:
            data = {
                "env": env_name,
                "stock": stock_code,
                "source": "Kiwoom ka10080 1min",
                "candles": [],
                "count": 0,
                "fetchedAt": now.isoformat(),
                "error": str(exc),
            }
        _chart_cache.update({"key": key, "data": data, "error": data.get("error"), "fetched_at": now})
        return data


def _run_local_command(args: list[str], timeout: int = 3) -> str:
    try:
        completed = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()
    except Exception:
        return ""


def get_n8n_status(*, force: bool = False) -> dict[str, Any]:
    """Return n8n health/workflow/execution status from local HTTP + Docker Postgres.

    This does not require or expose an n8n API key. If the API key is configured
    later, this function can be extended to call `/api/v1/executions` directly.
    """
    now = time.time()
    with _n8n_lock:
        if not force and _n8n_cache["data"] is not None and now - float(_n8n_cache["fetched_at"] or 0) < 60:
            return _n8n_cache["data"]

        health = _check_https("http://127.0.0.1:5678/healthz", timeout=0.8)
        readiness = _check_https("http://127.0.0.1:5678/healthz/readiness", timeout=0.8)
        containers_raw = _run_local_command([
            "docker", "ps", "--format", "{{.Names}}|{{.Status}}", "--filter", "name=n8n",
        ])
        containers = []
        for line in containers_raw.splitlines():
            if "|" in line:
                name, status = line.split("|", 1)
                containers.append({"name": name, "status": status, "running": status.lower().startswith("up")})

        workflow_count = None
        execution_count = None
        latest_executions: list[dict[str, Any]] = []
        db_error = None
        db_script = """
psql -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -Atc \"select 'workflow_count|' || count(*) from workflow_entity; select 'execution_count|' || count(*) from execution_entity; select 'execution|' || id || '|' || coalesce(\\\"workflowId\\\",'-') || '|' || coalesce(status,'-') || '|' || coalesce(\\\"startedAt\\\"::text,'-') || '|' || coalesce(\\\"stoppedAt\\\"::text,'-') from execution_entity order by id desc limit 5;\"
""".strip()
        db_raw = _run_local_command(["docker", "exec", "n8n-postgres-1", "sh", "-lc", db_script], timeout=5)
        if not db_raw:
            db_error = "n8n postgres query returned no data or failed"
        else:
            for line in db_raw.splitlines():
                parts = line.split("|")
                if parts[0] == "workflow_count" and len(parts) > 1:
                    workflow_count = int(parts[1])
                elif parts[0] == "execution_count" and len(parts) > 1:
                    execution_count = int(parts[1])
                elif parts[0] == "execution" and len(parts) >= 6:
                    latest_executions.append({
                        "id": parts[1],
                        "workflowId": parts[2],
                        "status": parts[3],
                        "startedAt": parts[4],
                        "stoppedAt": parts[5],
                    })

        health_ok = bool(health.get("ok")) and bool(readiness.get("ok"))
        containers_ok = containers and all(item["running"] for item in containers)
        state = "healthy" if health_ok and containers_ok else "degraded" if health_ok or containers_ok else "offline"
        data = {
            "role": "장전 뉴스/공시 보조 오케스트레이션",
            "state": state,
            "health": health,
            "readiness": readiness,
            "containers": containers,
            "workflowCount": workflow_count,
            "executionCount": execution_count,
            "latestExecutions": latest_executions,
            "api": "healthz + docker postgres fallback; /api/v1 requires X-N8N-API-KEY",
            "dbError": db_error,
            "fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        _n8n_cache.update({"fetched_at": now, "data": data})
        return data


def build_workflow_status(signals_df: pd.DataFrame) -> dict[str, Any]:
    latest = None
    latest_age_min = None
    if not signals_df.empty:
        latest_ts = signals_df.iloc[0].get("parsed_time")
        if isinstance(latest_ts, pd.Timestamp) and not pd.isna(latest_ts):
            latest = latest_ts.strftime("%Y-%m-%d %H:%M:%S")
            now_kst = datetime.utcnow() + timedelta(hours=9)
            latest_age_min = round((now_kst - latest_ts.to_pydatetime()).total_seconds() / 60, 1)
    return {
        "signalsCsv": {
            "path": str(DATA_FILE),
            "exists": DATA_FILE.exists(),
            "mtime": datetime.fromtimestamp(DATA_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S") if DATA_FILE.exists() else None,
            "rows": int(len(signals_df)),
            "latest": latest,
            "latestAgeMin": latest_age_min,
            "state": "live" if latest_age_min is not None and latest_age_min <= 15 else "stale" if latest_age_min is not None else "no_data",
        },
        "runner": {
            "command": "dash-kiwoom/.venv/bin/python scripts/run_strategy.py --env mock --stock 042660 --lookback 1",
            "mode": "dry-run / no --execute",
            "state": "configured",
        },
        "cron": {
            "name": "kiwoom-signal-dryrun-refresh.timer",
            "schedule": "systemd user timer · KST 장중 09:00-15:59 / 5분 간격",
            "state": "active_systemd_timer",
        },
        "n8n": get_n8n_status(),
    }


def ensure_paper_ledger() -> None:
    PAPER_LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = ",".join(PAPER_LEDGER_COLUMNS) + "\n"
    if not PAPER_LEDGER_FILE.exists():
        PAPER_LEDGER_FILE.write_text(header, encoding="utf-8")
        return
    try:
        df = pd.read_csv(PAPER_LEDGER_FILE)
    except Exception:
        backup = PAPER_LEDGER_FILE.with_suffix(f".csv.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        PAPER_LEDGER_FILE.replace(backup)
        PAPER_LEDGER_FILE.write_text(header, encoding="utf-8")
        return
    missing = [col for col in PAPER_LEDGER_COLUMNS if col not in df.columns]
    if missing or list(df.columns) != PAPER_LEDGER_COLUMNS:
        backup = PAPER_LEDGER_FILE.with_suffix(f".csv.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        PAPER_LEDGER_FILE.replace(backup)
        for col in PAPER_LEDGER_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[PAPER_LEDGER_COLUMNS]
        df.to_csv(PAPER_LEDGER_FILE, index=False)


def build_paper_simulation_preview(signals_df: pd.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
    """Return conservative simulated fills from recent signals without writing orders."""
    if signals_df.empty:
        return []
    preview = []
    fee_bps = 23.0
    slippage_bps = 10.0
    impact_bps = 5.0
    for row in signals_df.head(limit).itertuples(index=False):
        price = getattr(row, "price", None)
        if pd.isna(price) or not price:
            continue
        side = str(getattr(row, "type", "unknown") or "unknown").lower()
        qty = 1
        direction = 1 if side == "buy" else -1 if side == "sell" else 0
        fill_multiplier = 1 + direction * ((slippage_bps + impact_bps) / 10000.0)
        assumed_fill = abs(float(price)) * (fill_multiplier if direction else 1)
        estimated_fee = assumed_fill * qty * (fee_bps / 10000.0)
        cash_effect = -(assumed_fill * qty + estimated_fee) if side == "buy" else assumed_fill * qty - estimated_fee
        ts = getattr(row, "parsed_time", None)
        preview_time = str(getattr(row, "time", ""))
        if not pd.isna(ts):
            try:
                preview_time = pd.Timestamp(ts).strftime("%Y%m%d%H%M%S")
            except Exception:
                pass
        preview.append({
            "time": preview_time,
            "env": "paper-sim",
            "stock": str(getattr(row, "stock", "")).zfill(6),
            "side": side,
            "qty": qty,
            "price": round(abs(float(price)), 2),
            "reference_signal_price": round(abs(float(price)), 2),
            "assumed_fill_price": round(assumed_fill, 2),
            "fee_bps_one_way": fee_bps,
            "slippage_bps_one_way": slippage_bps,
            "impact_bps_one_way": impact_bps,
            "estimated_fee": round(estimated_fee, 2),
            "estimated_cash_effect": round(cash_effect, 2),
            "reason": "read-only preview from latest signal; not persisted; no Kiwoom order API",
            "status": "SIMULATION_PREVIEW_ONLY",
            "mode": "paper_only_no_kiwoom_order_api",
            "pnl": None,
        })
    return preview


def load_paper_ledger(signals_df: pd.DataFrame | None = None, limit: int = 50) -> dict[str, Any]:
    ensure_paper_ledger()
    df = pd.read_csv(PAPER_LEDGER_FILE)
    rows = df.tail(limit).iloc[::-1].to_dict(orient="records") if not df.empty else []
    preview = build_paper_simulation_preview(signals_df, limit=5) if signals_df is not None else []
    return {
        "path": str(PAPER_LEDGER_FILE),
        "columns": PAPER_LEDGER_COLUMNS,
        "rows": rows,
        "previewRows": preview,
        "count": int(len(df)),
        "state": "ready_empty" if df.empty else "ready",
        "mode": "paper_only_no_kiwoom_order_api",
        "assumptions": {
            "fee_bps_one_way": 23.0,
            "slippage_bps_one_way": 10.0,
            "impact_bps_one_way": 5.0,
            "order_api": "disabled",
        },
    }


def load_backtest_readiness_json() -> dict[str, Any] | None:
    """Load latest machine-readable backtest readiness report when available."""
    if not BACKTEST_READINESS_JSON.exists():
        return None
    try:
        data = json.loads(BACKTEST_READINESS_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "sourcePath": str(BACKTEST_READINESS_JSON),
            "sourceName": BACKTEST_READINESS_JSON.name,
            "state": "parse_error",
            "error": str(exc),
        }
    summary = data.get("summary") or {}
    backtest = summary.get("backtest") or {}
    readiness_gate = summary.get("readiness_gate") or {}
    variants_obj = summary.get("backtest_variants") or {}
    variant_rows = []
    for name, row in variants_obj.items():
        if not isinstance(row, dict):
            continue
        variant_rows.append({
            "variant": name,
            "trades": row.get("trades"),
            "winRate": row.get("win_rate"),
            "avgReturnPct": row.get("avg_return_pct"),
            "maxDrawdownPct": row.get("max_drawdown_pct"),
            "exitReasonCounts": row.get("exit_reason_counts") or {},
        })
    numeric_variants = [row for row in variant_rows if isinstance(row.get("avgReturnPct"), (int, float))]
    best = max(numeric_variants, key=lambda row: float(row["avgReturnPct"])) if numeric_variants else None
    total_trades = int(backtest.get("total_variant_trades") or sum(int(row.get("trades") or 0) for row in variant_rows))
    if total_trades > 0 and variant_rows:
        win_rate = round(sum(float(row.get("winRate") or 0) * int(row.get("trades") or 0) for row in variant_rows) / total_trades, 4)
        avg_return = round(sum(float(row.get("avgReturnPct") or 0) * int(row.get("trades") or 0) for row in variant_rows) / total_trades, 4)
    else:
        win_rate = None
        avg_return = None
    mdd_values = [float(row["maxDrawdownPct"]) for row in variant_rows if isinstance(row.get("maxDrawdownPct"), (int, float))]
    mdd = round(min(mdd_values), 4) if mdd_values else None
    performance_ok = bool(readiness_gate.get("backtest_performance_ok"))
    return {
        "sourcePath": str(BACKTEST_READINESS_JSON),
        "sourceName": BACKTEST_READINESS_JSON.name,
        "state": "passed" if performance_ok else "blocked",
        "rowsUsed": backtest.get("rows_used"),
        "rawRows": backtest.get("raw_rows_before_eligibility_filter"),
        "eligibleStockDays": (backtest.get("eligibility") or {}).get("eligible_stock_days"),
        "excludedStockDays": (backtest.get("eligibility") or {}).get("excluded_stock_days"),
        "tradeCount": total_trades,
        "minTradesRequired": backtest.get("min_trades_required"),
        "winRate": win_rate,
        "avgReturnPct": avg_return,
        "netReturn": avg_return,
        "mdd": mdd,
        "bestVariant": best,
        "variants": variant_rows,
        "performanceOk": performance_ok,
        "readinessGate": readiness_gate,
        "blockingConditions": data.get("blocking_conditions") or [],
        "updatedAt": datetime.fromtimestamp(BACKTEST_READINESS_JSON.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def load_backtest_gate_report() -> dict[str, Any]:
    """Load the latest official ka10080 backtest gate report."""
    latest = load_backtest_readiness_json()
    if latest is not None:
        return latest
    if not BACKTEST_REPORT_FILE.exists():
        return {
            "sourcePath": str(BACKTEST_REPORT_FILE),
            "state": "missing_report",
            "error": "backtest report file not found",
        }
    text = BACKTEST_REPORT_FILE.read_text(encoding="utf-8", errors="ignore")

    def grab(pattern: str, cast: Any = str, default: Any = None) -> Any:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if not match:
            return default
        value = match.group(1).strip()
        try:
            return cast(value)
        except Exception:
            return default

    variant_rows = []
    for match in re.finditer(
        r"^\|\s*(OR\d+)\s*\|\s*(\d+)\s*\|\s*([-\d.]+)%\s*\|\s*([-\d.]+)%\s*\|\s*([-\d.]+)%\s*\|",
        text,
        flags=re.MULTILINE,
    ):
        variant_rows.append({
            "variant": match.group(1),
            "trades": int(match.group(2)),
            "winRate": float(match.group(3)),
            "avgReturnPct": float(match.group(4)),
            "maxDrawdownPct": float(match.group(5)),
        })

    total_trades = grab(r"^total_variant_trades\s*=\s*(\d+)", int, None)
    rows_used = grab(r"^rows_used\s*=\s*(\d+)", int, None)
    min_trades_required = grab(r"^min_trades_required\s*=\s*(\d+)", int, None)
    blocking = re.findall(r"backtest_[a-z_]+", text)
    performance_ok = re.search(r"^\|\s*backtest_performance_ok\s*\|\s*false\s*\|", text, flags=re.MULTILINE) is None
    if variant_rows:
        best = max(variant_rows, key=lambda row: row["avgReturnPct"])
        win_rate = round(sum(row["winRate"] * row["trades"] for row in variant_rows) / max(sum(row["trades"] for row in variant_rows), 1), 4)
        avg_return = round(sum(row["avgReturnPct"] * row["trades"] for row in variant_rows) / max(sum(row["trades"] for row in variant_rows), 1), 4)
        mdd = round(min(row["maxDrawdownPct"] for row in variant_rows), 4)
    else:
        best = None
        win_rate = None
        avg_return = None
        mdd = None
    return {
        "sourcePath": str(BACKTEST_REPORT_FILE),
        "sourceName": BACKTEST_REPORT_FILE.name,
        "state": "blocked" if not performance_ok else "passed",
        "rowsUsed": rows_used,
        "tradeCount": total_trades if total_trades is not None else sum(row["trades"] for row in variant_rows),
        "minTradesRequired": min_trades_required,
        "winRate": win_rate,
        "avgReturnPct": avg_return,
        "netReturn": avg_return,
        "mdd": mdd,
        "bestVariant": best,
        "variants": variant_rows,
        "performanceOk": performance_ok,
        "blockingConditions": sorted(set(blocking)) or ([] if performance_ok else ["backtest_performance_not_passed"]),
        "updatedAt": datetime.fromtimestamp(BACKTEST_REPORT_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_gate_summary(signals_df: pd.DataFrame) -> dict[str, Any]:
    report = load_backtest_gate_report()
    trade_count = report.get("tradeCount") or 0
    return {
        "paperGate": "BLOCKED" if report.get("state") != "passed" else "REVIEW_REQUIRED",
        "realGate": "BLOCKED",
        "tradeCount": trade_count,
        "requiredTrades": report.get("minTradesRequired") or "50~100+",
        "signalRows": int(len(signals_df)),
        "winRate": report.get("winRate"),
        "netReturn": report.get("netReturn"),
        "avgReturnPct": report.get("avgReturnPct"),
        "mdd": report.get("mdd"),
        "performanceOk": bool(report.get("performanceOk")),
        "backtestReport": report,
        "reason": "백테스트 rows/trades는 통과했지만 평균 수익률이 음수라 paper/real gate는 계속 차단." if report.get("state") == "blocked" else "성과 gate 통과 후보. 사용자 검토와 paper 승인 필요.",
    }


def _check_tcp(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_https(url: str, timeout: float = 0.45) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        req = urlrequest.Request(url, headers={"User-Agent": "DashKiwoomHealth/1.0"})
        with urlrequest.urlopen(req, timeout=timeout) as res:
            elapsed = round((time.perf_counter() - started) * 1000)
            return {"ok": True, "status": int(res.status), "latencyMs": elapsed, "error": None}
    except Exception as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        status = getattr(exc, "code", None)
        return {"ok": False, "status": status, "latencyMs": elapsed, "error": str(exc)}


def _check_caddy_local_https(domain: str, timeout: float = 1.5) -> dict[str, Any]:
    """Check the Caddy vhost locally via 127.0.0.1:443 + SNI.

    Public DuckDNS self-calls can time out on this host because of hairpin NAT.
    A local SNI check verifies Caddy's HTTPS virtual host and reverse proxy path
    without depending on router loopback behavior.
    """
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [
                "curl",
                "-sS",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--resolve",
                f"{domain}:443:127.0.0.1",
                f"https://{domain}/",
                "--max-time",
                str(timeout),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(timeout + 0.5, 2.0),
        )
        elapsed = round((time.perf_counter() - started) * 1000)
        status_text = completed.stdout.strip()
        status = int(status_text) if status_text.isdigit() else None
        return {"ok": completed.returncode == 0 and status is not None, "status": status, "latencyMs": elapsed, "error": completed.stderr.strip() or None, "method": "local_sni"}
    except Exception as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        return {"ok": False, "status": None, "latencyMs": elapsed, "error": str(exc), "method": "local_sni"}


def get_caddy_status(*, force: bool = False) -> dict[str, Any]:
    """Return Caddy-exposed service inventory and lightweight health checks."""
    now = time.time()
    with _caddy_lock:
        if not force and _caddy_cache["data"] is not None and now - float(_caddy_cache["fetched_at"] or 0) < 20:
            return _caddy_cache["data"]

        services = []
        for site in CADDY_SITES:
            host, port_text = str(site["upstream"]).rsplit(":", 1)
            upstream_online = _check_tcp(host, int(port_text))
            proxy = _check_caddy_local_https(site["domain"])
            expected = set(site.get("expected", [200]))
            proxy_online = proxy["status"] in expected if proxy["status"] is not None else False
            state = "online" if upstream_online and proxy_online else "degraded" if upstream_online or proxy_online else "offline"
            if not upstream_online:
                diagnosis = f"upstream {site['upstream']} is not listening; Caddy returns 502/timeout until the service is started or Caddyfile is updated"
            elif not proxy_online:
                diagnosis = f"upstream is listening, but local Caddy SNI check returned {proxy['status'] or 'ERR'}; inspect Caddy route/TLS for {site['domain']}"
            else:
                diagnosis = "local upstream and Caddy HTTPS vhost are healthy"
            services.append({
                **site,
                "upstreamOnline": upstream_online,
                "proxyOnline": proxy_online,
                "httpStatus": proxy["status"],
                "latencyMs": proxy["latencyMs"],
                "error": proxy["error"],
                "checkMethod": proxy.get("method", "local_sni"),
                "diagnosis": diagnosis,
                "state": state,
            })

        online_count = sum(1 for svc in services if svc["state"] == "online")
        data = {
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "publicIp": "125.248.15.32",
            "caddyfile": "/etc/caddy/Caddyfile",
            "serviceCount": len(services),
            "onlineCount": online_count,
            "degradedCount": sum(1 for svc in services if svc["state"] == "degraded"),
            "offlineCount": sum(1 for svc in services if svc["state"] == "offline"),
            "services": services,
        }
        _caddy_cache.update({"fetched_at": now, "data": data})
        return data


def build_payload(include_account: bool = True, account_env: str = "mock") -> dict[str, Any]:
    signals_df = load_signals()
    snapshot_chart = build_snapshot_chart_data("042660")
    fallback_chart = None
    chart_data = snapshot_chart.get("candles") or []
    chart_meta = snapshot_chart
    if not chart_data:
        fallback_chart = build_real_chart_data(account_env, "042660")
        chart_data = fallback_chart.get("candles") or build_chart_data(signals_df)
        chart_meta = fallback_chart if fallback_chart.get("candles") else {**snapshot_chart, "fallback": "signals.csv synthetic candles"}
    payload = {
        "serverTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "signals": serialize_signals(signals_df),
        "signalMetrics": calculate_signal_metrics(signals_df),
        "marketOverview": build_market_overview(signals_df),
        "chartData": chart_data,
        "chartMeta": chart_meta,
        "masterStatus": MASTER_STATUS,
        "caddyStatus": get_caddy_status(),
        "accountStatuses": build_account_statuses(),
        "workflowStatus": build_workflow_status(signals_df),
        "gateSummary": build_gate_summary(signals_df),
        "paperLedger": load_paper_ledger(signals_df, limit=20),
    }
    if include_account:
        payload["accountData"] = get_account_info(account_env)
    else:
        payload["accountData"] = {"mode": account_env, "holdings": [], "error": None}
    return payload


def background_thread() -> None:
    """Background thread to send realtime updates via Socket.IO."""
    print("=== Dash Kiwoom background_thread started ===", flush=True)
    while True:
        try:
            payload = build_payload(include_account=True)
            print(
                f"[BACKGROUND] Emitting {len(payload['signals'])} signals; "
                f"unique={payload['signalMetrics']['unique_rows']}",
                flush=True,
            )
            socketio.emit("update", payload)
        except Exception as exc:
            print(f"Error in background thread: {exc}", flush=True)
        socketio.sleep(30)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/signals")
def api_signals():
    limit = int(request.args.get("limit", "50"))
    df = load_signals()
    return jsonify(serialize_signals(df, limit=limit))


@app.route("/api/status")
def api_status():
    env = request.args.get("env", "mock")
    if env not in {"mock", "prod"}:
        return jsonify({"error": "env must be mock or prod"}), 400
    return jsonify(build_payload(include_account=request.args.get("account", "1") != "0", account_env=env))


@app.route("/api/account")
def api_account():
    env = request.args.get("env", "mock")
    if env not in {"mock", "prod"}:
        return jsonify({"error": "env must be mock or prod"}), 400
    return jsonify(get_account_info(env, force=request.args.get("force") == "1"))


@app.route("/api/caddy")
def api_caddy():
    return jsonify(get_caddy_status(force=request.args.get("force") == "1"))


@app.route("/api/account-status")
def api_account_status():
    return jsonify(build_account_statuses())


@app.route("/api/chart")
def api_chart():
    env = request.args.get("env", "mock")
    if env not in {"mock", "prod"}:
        return jsonify({"error": "env must be mock or prod"}), 400
    stock = request.args.get("stock", "042660")
    limit = int(request.args.get("limit", "120"))
    return jsonify(build_real_chart_data(env, stock, limit=limit))


@app.route("/api/workflow-status")
def api_workflow_status():
    return jsonify(build_workflow_status(load_signals()))


@app.route("/api/paper-ledger")
def api_paper_ledger():
    return jsonify(load_paper_ledger(limit=int(request.args.get("limit", "50"))))


@socketio.on("connect")
def handle_connect():
    print("Client connected", flush=True)
    socketio.emit("update", build_payload(include_account=True, account_env="mock"))


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected", flush=True)


if __name__ == "__main__":
    thread = threading.Thread(target=background_thread, daemon=True)
    thread.start()
    socketio.run(app, host="0.0.0.0", port=3000, debug=False, allow_unsafe_werkzeug=True)
