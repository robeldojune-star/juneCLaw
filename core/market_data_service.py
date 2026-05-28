"""Market data service based on verified Kiwoom read APIs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from .kiwoom_client import KiwoomAPIClient, KiwoomAPIError, clean_int


@dataclass(frozen=True)
class DailyPrice:
    stock_code: str
    date: str
    open: int | None
    high: int | None
    low: int | None
    close: int | None
    volume: int | None


@dataclass(frozen=True)
class RankingItem:
    stock_code: str
    stock_name: str
    current_price: int | None
    trading_volume: int | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class IntradayBar:
    stock_code: str
    date: str | None
    open: int | None
    high: int | None
    low: int | None
    close: int | None
    volume: int | None
    trading_value: int | None
    raw: dict[str, Any]


def normalize_stock_code(value: Any) -> str:
    code = str(value or "").strip()
    if code.startswith("A") and len(code) == 7:
        code = code[1:]
    return code


def is_stock_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", value))


class MarketDataService:
    """Read-only market data APIs.

    Verified APIs:
    - ka10001: /api/dostk/stkinfo
    - ka10081: /api/dostk/chart, response key stk_dt_pole_chart_qry
    - ka10030: /api/dostk/rkinfo, response key tdy_trde_qty_upper
    """

    def __init__(self, client: KiwoomAPIClient):
        self.client = client

    def get_stock_info(self, stock_code: str) -> dict[str, Any]:
        code = normalize_stock_code(stock_code)
        if not is_stock_code(code):
            raise ValueError(f"Invalid KRX stock code: {stock_code}")
        return self.client.post("ka10001", "/api/dostk/stkinfo", {"stk_cd": code}).data

    def get_daily_chart_raw(self, stock_code: str, *, base_dt: str, adjusted_price: bool = True) -> list[dict[str, Any]]:
        code = normalize_stock_code(stock_code)
        if not is_stock_code(code):
            raise ValueError(f"Invalid KRX stock code: {stock_code}")
        response = self.client.post(
            "ka10081",
            "/api/dostk/chart",
            {"stk_cd": code, "base_dt": base_dt, "upd_stkpc_tp": "1" if adjusted_price else "0"},
        )
        rows = response.data.get("stk_dt_pole_chart_qry")
        if not isinstance(rows, list):
            raise KiwoomAPIError(
                f"ka10081 response missing list key stk_dt_pole_chart_qry; keys={list(response.data.keys())[:12]}",
                api_id="ka10081",
                http_status=response.http_status,
                return_code=response.return_code,
                return_msg=response.return_msg,
                response=response.data,
            )
        return rows

    def get_daily_prices(self, stock_code: str, *, base_dt: str, adjusted_price: bool = True) -> list[DailyPrice]:
        rows = self.get_daily_chart_raw(stock_code, base_dt=base_dt, adjusted_price=adjusted_price)
        code = normalize_stock_code(stock_code)
        out: list[DailyPrice] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            dt = str(row.get("dt") or "").strip()
            if not re.fullmatch(r"\d{8}", dt):
                continue
            out.append(
                DailyPrice(
                    stock_code=code,
                    date=f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}",
                    open=clean_int(row.get("open_pric"), abs_value=True),
                    high=clean_int(row.get("high_pric"), abs_value=True),
                    low=clean_int(row.get("low_pric"), abs_value=True),
                    close=clean_int(row.get("cur_prc"), abs_value=True),
                    volume=clean_int(row.get("trde_qty"), abs_value=True),
                )
            )
        return out

    def get_kospi_volume_ranking_raw(self) -> list[dict[str, Any]]:
        response = self.client.post(
            "ka10030",
            "/api/dostk/rkinfo",
            {
                "mrkt_tp": "001",
                "sort_tp": "1",
                "mang_stk_incls": "0",
                "crd_tp": "0",
                "trde_qty_tp": "0",
                "pric_tp": "0",
                "trde_prica_tp": "0",
                "mrkt_open_tp": "0",
                "stex_tp": "1",
            },
        )
        rows = response.data.get("tdy_trde_qty_upper")
        if not isinstance(rows, list):
            raise KiwoomAPIError(
                f"ka10030 response missing list key tdy_trde_qty_upper; keys={list(response.data.keys())[:12]}",
                api_id="ka10030",
                http_status=response.http_status,
                return_code=response.return_code,
                return_msg=response.return_msg,
                response=response.data,
            )
        return rows

    def get_kospi_volume_ranking(self, *, limit: int = 100) -> list[RankingItem]:
        rows = self.get_kospi_volume_ranking_raw()[:limit]
        out: list[RankingItem] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(
                RankingItem(
                    stock_code=normalize_stock_code(row.get("stk_cd")),
                    stock_name=str(row.get("stk_nm") or "").strip(),
                    current_price=clean_int(row.get("cur_prc"), abs_value=True),
                    trading_volume=clean_int(row.get("trde_qty"), abs_value=True),
                    raw=row,
                )
            )
        return out

    def get_intraday_ohlcv_raw(self, stock_code: str) -> list[dict[str, Any]]:
        """Return candidate intraday/history OHLCV rows via ka10005.

        Kiwoom labels ka10005 as 주식일주월시분요청. The API structure has
        been smoke-tested for OHLCV fields on mock, but the exact time-frame
        semantics should be verified during market hours before using it as
        authoritative 1m/5m data.
        """
        code = normalize_stock_code(stock_code)
        if not is_stock_code(code):
            raise ValueError(f"Invalid KRX stock code: {stock_code}")
        response = self.client.post("ka10005", "/api/dostk/mrkcond", {"stk_cd": code})
        rows = response.data.get("stk_ddwkmm")
        if not isinstance(rows, list):
            raise KiwoomAPIError(
                f"ka10005 response missing list key stk_ddwkmm; keys={list(response.data.keys())[:12]}",
                api_id="ka10005",
                http_status=response.http_status,
                return_code=response.return_code,
                return_msg=response.return_msg,
                response=response.data,
            )
        return [row for row in rows if isinstance(row, dict)]

    def get_intraday_ohlcv(self, stock_code: str) -> list[IntradayBar]:
        code = normalize_stock_code(stock_code)
        bars: list[IntradayBar] = []
        for row in self.get_intraday_ohlcv_raw(code):
            bars.append(
                IntradayBar(
                    stock_code=code,
                    date=str(row.get("date") or "").strip() or None,
                    open=clean_int(row.get("open_pric"), abs_value=True),
                    high=clean_int(row.get("high_pric"), abs_value=True),
                    low=clean_int(row.get("low_pric"), abs_value=True),
                    close=clean_int(row.get("close_pric"), abs_value=True),
                    volume=clean_int(row.get("trde_qty"), abs_value=True),
                    trading_value=clean_int(row.get("trde_prica"), abs_value=True),
                    raw=row,
                )
            )
        return bars

    def get_current_session_snapshot(self, stock_code: str) -> dict[str, Any]:
        """Return current session OHLCV-like snapshot via ka10006."""
        code = normalize_stock_code(stock_code)
        if not is_stock_code(code):
            raise ValueError(f"Invalid KRX stock code: {stock_code}")
        return self.client.post("ka10006", "/api/dostk/mrkcond", {"stk_cd": code}).data
