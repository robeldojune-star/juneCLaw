#!/usr/bin/env python3
"""Fetch KOSPI market-cap top common stocks excluding ETFs/ETNs/preferred shares."""
from __future__ import annotations

import re
from datetime import datetime
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page={page}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://finance.naver.com/",
}

ETF_ETN_KEYWORDS = (
    "KODEX", "TIGER", "ACE", "SOL", "RISE", "KOSEF", "HANARO", "ARIRANG",
    "KBSTAR", "TREX", "TIMEFOLIO", "PLUS", "FOCUS", "히어로즈", "마이티",
    "ETF", "ETN", "인버스", "레버리지",
)


def is_preferred_share(name: str, code: str) -> bool:
    # Korean preferred shares commonly end with 우/우B/우C, e.g. 삼성전자우.
    if re.search(r"우(B|C)?$", name):
        return True
    # KRX preferred-share codes often end with non-zero in the last digit, but this is
    # not safe alone for all securities, so use it only with name signal above.
    return False


def is_excluded(name: str, code: str) -> bool:
    if any(keyword in name for keyword in ETF_ETN_KEYWORDS):
        return True
    if is_preferred_share(name, code):
        return True
    return False


def fetch_page(page: int) -> pd.DataFrame:
    url = BASE_URL.format(page=page)
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = "euc-kr"

    tables = pd.read_html(StringIO(r.text))
    table = None
    for candidate in tables:
        if "종목명" in candidate.columns and "시가총액" in candidate.columns:
            table = candidate.dropna(subset=["종목명"]).copy()
            break
    if table is None:
        raise RuntimeError(f"No market-cap table found on page {page}")

    soup = BeautifulSoup(r.text, "html.parser")
    code_by_name: dict[str, str] = {}
    for a in soup.select("a.tltle[href*='code=']"):
        name = a.get_text(strip=True)
        href = a.get("href", "")
        m = re.search(r"code=(\d+)", href)
        if name and m:
            code_by_name[name] = m.group(1)

    table["종목코드"] = table["종목명"].map(code_by_name).fillna("")
    return table


def main() -> int:
    rows = []
    page = 1
    while len(rows) < 50 and page <= 10:
        df = fetch_page(page)
        df = df[df["N"].notna()].copy()
        df["N"] = df["N"].astype(int)
        for _, row in df.sort_values("N").iterrows():
            name = str(row["종목명"]).strip()
            code = str(row.get("종목코드", "")).strip()
            if is_excluded(name, code):
                continue
            row_dict = row.to_dict()
            row_dict["원순위"] = int(row["N"])
            row_dict["보통주순위"] = len(rows) + 1
            rows.append(row_dict)
            if len(rows) >= 50:
                break
        page += 1

    if len(rows) < 50:
        raise RuntimeError(f"Only collected {len(rows)} common stocks")

    out = pd.DataFrame(rows)
    cols = [
        "보통주순위", "원순위", "종목코드", "종목명", "현재가", "전일비", "등락률", "액면가",
        "시가총액", "상장주식수", "외국인비율", "거래량", "PER", "ROE",
    ]
    cols = [c for c in cols if c in out.columns]
    out = out[cols]
    out_csv = "kospi_top50_common_stocks_marketcap_naver.csv"
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(f"source=Naver Finance KOSPI market cap, filter=exclude ETF/ETN/preferred, fetched_at={datetime.now().isoformat(timespec='seconds')}")
    print(f"rows={len(out)}, csv={out_csv}")
    for _, row in out.iterrows():
        print(
            f"{int(row['보통주순위']):>2}. {row['종목코드']} {row['종목명']} "
            f"| 원순위={int(row['원순위'])} | 현재가={row.get('현재가', '')} "
            f"| 등락률={row.get('등락률', '')} | 시가총액={row.get('시가총액', '')}억"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
