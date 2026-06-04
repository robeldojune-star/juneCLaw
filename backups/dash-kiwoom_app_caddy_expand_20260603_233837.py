#!/usr/bin/env python3
"""Dash Kiwoom dashboard backend.

This dashboard is intentionally read-only.  The current master trading plan keeps
paper/real orders blocked until the backtest and paper gates pass.  The backend
therefore exposes monitoring/status APIs and Socket.IO updates, but it does not
place orders.
"""
from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
DATA_FILE = APP_ROOT / "data" / "signals.csv"

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


def build_payload(include_account: bool = True) -> dict[str, Any]:
    signals_df = load_signals()
    payload = {
        "serverTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "signals": serialize_signals(signals_df),
        "signalMetrics": calculate_signal_metrics(signals_df),
        "chartData": build_chart_data(signals_df),
        "masterStatus": MASTER_STATUS,
    }
    if include_account:
        payload["accountData"] = get_account_info("mock")
    else:
        payload["accountData"] = {"mode": "mock", "holdings": [], "error": None}
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
    return jsonify(build_payload(include_account=request.args.get("account", "1") != "0"))


@app.route("/api/account")
def api_account():
    env = request.args.get("env", "mock")
    if env not in {"mock", "prod"}:
        return jsonify({"error": "env must be mock or prod"}), 400
    return jsonify(get_account_info(env, force=request.args.get("force") == "1"))


@socketio.on("connect")
def handle_connect():
    print("Client connected", flush=True)
    socketio.emit("update", build_payload(include_account=True))


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected", flush=True)


if __name__ == "__main__":
    thread = threading.Thread(target=background_thread, daemon=True)
    thread.start()
    socketio.run(app, host="0.0.0.0", port=3000, debug=False, allow_unsafe_werkzeug=True)
