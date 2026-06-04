#!/usr/bin/env python3
"""Profit-taking monitor: sell holdings at +5% profit, ignore stop-loss.

Read-only until --execute is passed.  Designed for cron during market hours.
Logs every run to logs/profit_taking_monitor.log.

Safety:
  - 손절 무시: pl_rt < 0 → skip, no sell order
  - +5% 강제 청산: pl_rt >= 5.0 → sell
  - 0% ≤ pl_rt < 5%: hold (not sold, not a loss)
  - --execute required to actually place orders; default is dry-run.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.kiwoom_client import KiwoomAPIClient

LOG_FILE = PROJECT_ROOT / "logs" / "profit_taking_monitor.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("profit_taking")

TELEGRAM_SCRIPT = """\
hermes send --message "{msg}" telegram 2>/dev/null || true\
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Profit-taking monitor")
    p.add_argument("--env", choices=["mock", "prod"], default="prod")
    p.add_argument("--profit-threshold", type=float, default=5.0,
                   help="Sell when profit % >= this value (default 5.0)")
    p.add_argument("--execute", action="store_true",
                   help="Actually place sell orders (default: dry-run)")
    p.add_argument("--delay", type=float, default=1.0,
                   help="Delay between orders in seconds")
    return p.parse_args()


def load_env(env_name: str) -> Path:
    env_path = PROJECT_ROOT / "envs" / env_name / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")
    return env_path


def sell_position(client: KiwoomAPIClient, stock_code: str, qty: int,
                  name: str, pl_rt: float, dry_run: bool) -> dict[str, Any]:
    """Place a market sell order for the given stock. Returns order result."""
    code = stock_code.lstrip("A")  # Kiwoom holdings prefix "A", orders need pure digits
    if dry_run:
        logger.info(f"[DRY-RUN] Would SELL {name}({code}) x{qty} at market (pl={pl_rt:.2f}%)")
        return {"dry_run": True, "stock": code, "qty": qty, "pl_rt": pl_rt}

    try:
        body = {
            "dmst_stex_tp": "KRX",
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": "0",          # market order
            "trde_tp": "3",         # 시장가
            "cond_uv": "",
        }
        resp = client.post("kt10001", "/api/dostk/ordr", body, retries=1, raise_on_error=False)
        result = {
            "stock": code,
            "name": name,
            "qty": qty,
            "pl_rt": pl_rt,
            "ok": resp.ok,
            "return_code": resp.return_code,
            "return_msg": resp.return_msg,
            "raw": str(resp.data)[:200],
        }
        if resp.ok:
            logger.info(f"SELL {name}({code}) x{qty} at market — pl={pl_rt:.2f}% — OK")
        else:
            logger.error(f"SELL {name}({code}) FAILED: {resp.return_msg}")
        return result
    except Exception as exc:
        logger.exception(f"SELL {name}({code}) exception: {exc}")
        return {"stock": code, "name": name, "qty": qty, "pl_rt": pl_rt, "ok": False, "error": str(exc)}


def notify_telegram(msg: str) -> None:
    """Send a telegram message via Hermes CLI. Non-fatal on failure."""
    import subprocess
    try:
        subprocess.run(
            ["hermes", "send", "--message", msg, "telegram"],
            capture_output=True,
            timeout=15,
        )
    except Exception:
        logger.warning("Telegram notification failed (non-fatal)")


def main() -> None:
    args = parse_args()
    env_path = load_env(args.env)
    client = KiwoomAPIClient.from_env(env_path=env_path)
    token = client.issue_token(force=True)
    if not token:
        logger.error("OAuth token issue failed — aborting")
        return

    # Fetch holdings
    resp = client.post("kt00004", "/api/dostk/acnt",
                       {"qry_tp": "1", "dmst_stex_tp": "KRX"},
                       retries=2, raise_on_error=False)
    if not resp.ok:
        logger.error(f"kt00004 failed: {resp.return_msg}")
        return

    data = resp.data if isinstance(resp.data, dict) else {}
    holdings = data.get("stk_acnt_evlt_prst") or []
    if not isinstance(holdings, list):
        holdings = []

    now_utc = datetime.now(timezone.utc)
    logger.info(f"Run {now_utc.isoformat()} | env={args.env} | holdings={len(holdings)} | "
                f"threshold=+{args.profit_threshold}% | execute={args.execute}")

    sold = []
    skipped_loss = []
    skipped_hold = []
    errors = []

    for h in holdings:
        if not isinstance(h, dict):
            continue
        code = str(h.get("stk_cd", "")).strip()
        name = str(h.get("stk_nm", "")).strip()
        qty_raw = str(h.get("rmnd_qty", "0")).strip()
        pl_rt_raw = str(h.get("pl_rt", "0")).strip()

        # Parse
        try:
            qty = int(qty_raw)
        except (ValueError, TypeError):
            qty = 0
        try:
            pl_rt = float(pl_rt_raw)
        except (ValueError, TypeError):
            pl_rt = 0.0

        if qty <= 0:
            continue   # empty position

        if pl_rt >= args.profit_threshold:
            # Profit taking!
            result = sell_position(client, code, qty, name, pl_rt, dry_run=not args.execute)
            if result.get("ok") or result.get("dry_run"):
                sold.append(result)
            else:
                errors.append(result)
            if args.execute:
                time.sleep(args.delay)
        elif pl_rt < 0:
            skipped_loss.append({"code": code, "name": name, "pl_rt": pl_rt, "qty": qty})
        else:
            skipped_hold.append({"code": code, "name": name, "pl_rt": pl_rt, "qty": qty})

    # Summary
    summary = {
        "ts": now_utc.isoformat(),
        "env": args.env,
        "execute": args.execute,
        "threshold": args.profit_threshold,
        "total_holdings": len(holdings),
        "sold": len(sold),
        "skipped_loss": len(skipped_loss),
        "skipped_hold": len(skipped_hold),
        "errors": len(errors),
    }
    logger.info(f"Summary: {json.dumps(summary, ensure_ascii=False)}")

    # Telegram notification
    if sold:
        lines = [f"[{args.env.upper()}] 익절 청산 {len(sold)}건"]
        for s in sold:
            nm = s.get("name", s.get("stock", "?"))
            pr = s.get("pl_rt", 0)
            lines.append(f"  ✅ {nm} +{pr:.2f}%")
        notify_telegram("\n".join(lines))

    if errors:
        lines = [f"[{args.env.upper()}] 청산 오류 {len(errors)}건"]
        for e in errors:
            lines.append(f"  ❌ {e.get('name', e.get('stock', '?'))}: {e.get('return_msg', e.get('error', '?'))}")
        notify_telegram("\n".join(lines))

    # Print summary to stdout for cron output
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
