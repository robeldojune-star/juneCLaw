"""Account service based on verified Kiwoom account APIs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .kiwoom_client import KiwoomAPIClient, KiwoomAPIError, clean_int


@dataclass(frozen=True)
class Holding:
    code: str
    name: str
    quantity: int
    avg_price: int | None
    current_price: int | None
    evaluation: int | None
    pnl_amount: int | None
    pnl_pct: float | None


@dataclass(frozen=True)
class AccountSummary:
    environment: str
    deposit: int | None
    estimated_asset: int | None
    holdings_count: int
    holdings: list[Holding]
    raw_return_msg: str | None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_stock_code(value: Any) -> str:
    code = str(value or "").strip()
    if code.startswith("A") and len(code) == 7:
        return code[1:]
    return code


def _latest_business_dates(limit: int = 7) -> list[str]:
    dates: list[str] = []
    d = date.today()
    while len(dates) < limit:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return dates


class AccountService:
    """Read-only account APIs.

    kt00004 is the primary account API for mock trading. ka01690 is exposed as a
    probe/optional call because the current mock server rejects it with 8104.
    """

    def __init__(self, client: KiwoomAPIClient):
        self.client = client

    def get_account_evaluation_raw(self, *, qry_tp: str = "1", exchange: str = "KRX") -> dict[str, Any]:
        body: dict[str, Any] = {"qry_tp": qry_tp, "dmst_stex_tp": exchange}
        if self.client.config.account_no:
            # Current verified mock server accepts this. Token also carries auth.
            body["accno"] = self.client.config.account_no
        return self.client.post("kt00004", "/api/dostk/acnt", body).data

    def get_account_summary(self) -> AccountSummary:
        data = self.get_account_evaluation_raw()
        holdings_raw = data.get("stk_acnt_evlt_prst") or []
        holdings: list[Holding] = []
        if isinstance(holdings_raw, list):
            for row in holdings_raw:
                if not isinstance(row, dict):
                    continue
                holdings.append(
                    Holding(
                        code=_normalize_stock_code(row.get("stk_cd")),
                        name=str(row.get("stk_nm") or "").strip(),
                        quantity=clean_int(row.get("rmnd_qty"), abs_value=True) or 0,
                        avg_price=clean_int(row.get("avg_prc"), abs_value=True),
                        current_price=clean_int(row.get("cur_prc"), abs_value=True),
                        evaluation=clean_int(row.get("evlt_amt"), abs_value=True),
                        pnl_amount=clean_int(row.get("pl_amt")),
                        pnl_pct=_as_float(row.get("pl_rt")),
                    )
                )
        return AccountSummary(
            environment=self.client.config.trading_env,
            deposit=clean_int(data.get("entr"), abs_value=True),
            estimated_asset=clean_int(data.get("tot_est_amt"), abs_value=True),
            holdings_count=len(holdings),
            holdings=holdings,
            raw_return_msg=data.get("return_msg"),
        )

    def probe_daily_balance_pnl(self, *, lookback_business_days: int = 7) -> dict[str, Any]:
        """Try ka01690 and report server behavior without raising on known mock unsupported response."""
        attempts: list[dict[str, Any]] = []
        for ymd in _latest_business_dates(lookback_business_days):
            body: dict[str, Any] = {"qry_dt": ymd}
            if self.client.config.account_no:
                body["accno"] = self.client.config.account_no
            response = self.client.post("ka01690", "/api/dostk/acnt", body, raise_on_error=False)
            item = {
                "date": ymd,
                "http_status": response.http_status,
                "return_code": response.return_code,
                "return_msg": response.return_msg,
                "tot_evlt_amt": response.data.get("tot_evlt_amt"),
                "tot_evltv_prft": response.data.get("tot_evltv_prft"),
                "tot_prft_rt": response.data.get("tot_prft_rt"),
            }
            attempts.append(item)
            if response.ok:
                return {"ok": True, "selected_date": ymd, "data": response.data, "attempts": attempts}
            # If mock explicitly says unsupported, no need to keep hammering, but
            # keep old behavior of trying several dates for compatibility? Stop early.
            if response.return_code in (2, "2") and "8104" in str(response.return_msg):
                return {"ok": False, "unsupported_in_mock": True, "selected_date": None, "data": None, "attempts": attempts}
        return {"ok": False, "unsupported_in_mock": False, "selected_date": None, "data": None, "attempts": attempts}

    def assert_mock_account_ready(self) -> AccountSummary:
        if self.client.config.trading_env != "mock":
            raise KiwoomAPIError("Account smoke test expected mock environment")
        return self.get_account_summary()
