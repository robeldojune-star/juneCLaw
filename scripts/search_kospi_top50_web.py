#!/usr/bin/env python3
"""Fetch KOSPI market-cap top 50 from Naver Finance pages."""
from __future__ import annotations

import sys
from datetime import datetime
from io import StringIO

import pandas as pd
import requests


def fetch_page(page: int) -> pd.DataFrame:
    url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page={page}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": "https://finance.naver.com/",
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    # Naver Finance Korean pages are cp949/euc-kr style.
    r.encoding = "euc-kr"
    tables = pd.read_html(StringIO(r.text))
    for table in tables:
        if "종목명" in table.columns and "시가총액" in table.columns:
            return table.dropna(subset=["종목명"])
    raise RuntimeError(f"No market-cap table found on page {page}")


def main() -> int:
    frames = [fetch_page(1), fetch_page(2)]
    df = pd.concat(frames, ignore_index=True)
    # Keep actual rows only.
    df = df[df["N"].notna()].copy()
    df["N"] = df["N"].astype(int)
    df = df.sort_values("N").head(50)

    cols = [c for c in ["N", "종목명", "현재가", "전일비", "등락률", "액면가", "시가총액", "상장주식수", "외국인비율", "거래량", "PER", "ROE"] if c in df.columns]
    df = df[cols]

    out_csv = "kospi_top50_marketcap_naver.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(f"source=Naver Finance KOSPI market cap, fetched_at={datetime.now().isoformat(timespec='seconds')}")
    print(f"rows={len(df)}, csv={out_csv}")
    for _, row in df.iterrows():
        rank = int(row["N"])
        name = str(row["종목명"])
        price = row.get("현재가", "")
        market_cap = row.get("시가총액", "")
        change_rate = row.get("등락률", "")
        print(f"{rank:>2}. {name} | 현재가={price} | 등락률={change_rate} | 시가총액={market_cap}억")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
