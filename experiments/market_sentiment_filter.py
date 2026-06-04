# Market sentiment filter: previous day foreign + institutional net buying > individual net buying
# We'll need to fetch this data from Kiwoom API (e.g., ka10059? or similar).
# Since exact API ID is not known, we'll create a placeholder function that returns a set of symbols
# that satisfy the condition for a given date.

import sys
sys.path.insert(0, '/home/june/trading')
from datetime import datetime, timedelta
from typing import Set, List
import pandas as pd

def get_market_sentiment_symbols(target_date: str) -> Set[str]:
    """
    Return a set of stock codes (6-digit strings) where, on the previous trading day,
    the combined net buying of foreigners and institutions exceeded that of individuals.
    target_date format: 'YYYYMMDD'
    """
    # TODO: Implement actual Kiwoom API call.
    # For now, return an empty set to avoid breaking the backtest.
    # In practice, you would call something like:
    #   api.get_foreign_inst_individual_net_buy(date=prev_date, market='KOSPI')
    # and filter where foreign_net + inst_net > individual_net.
    return set()


def get_kospi_top50_by_marketcap(date: str) -> List[str]:
    """
    Return a list of the top 50 KOSPI stocks by market cap as of the given date.
    """
    # TODO: Implement via Kiwoom API (e.g., rank by market cap or use a pre-defined list).
    # For demonstration, we'll return a static list of some large-cap KOSPI tickers.
    # In a real implementation, you would fetch market cap data and sort.
    return [
        "005930",  # 삼성전자
        "000660",  # SK하이닉스
        "035420",  # NAVER
        "005380",  # 현대차
        "068270",  # 셀트리온
        "035720",  # 카카오
        "005490",  # POSCO
        "012330",  # 현대모비스
        "010140",  # 삼성물산
        "003550",  # LG
        "011200",  # HMM
        "017670",  # SK텔레콤
        "028260",  # 삼성C&T
        "009150",  # 삼성전기
        "010950",  # 소프트웨어
        "015760",  # 한국전력
        "018260",  # 삼성SDI
        "009830",  # 한화솔루션
        "024110",  # 기업은행
        "032830",  # 삼성생명
        "004020",  # 현대로템
        "010130",  # 고려아연
        "009540",  # 한국조선해양
        "010120",  # LG디스플레이
        "009840",  # 코오롱인더
        "003490",  # 대한유화
        "011170",  # 동아쏘시오홀딩스
        "012450",  # 한미사이언스
        "000270",  # 기아
        "003540",  # LG전자
        "000270",  # 기아 (duplicate for illustration)
        # Add more to reach 50...
    ]


if __name__ == '__main__':
    # Example usage
    today = datetime.now().strftime('%Y%m%d')
    ytd = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    sentiment_symbols = get_market_sentiment_symbols(ytd)
    top50 = get_kospi_top50_by_marketcap(today)
    candidates = [code for code in top50 if code in sentiment_symbols]
    print(f"Date {today}: {len(candidates)} symbols pass sentiment filter")
    print("Sample:", candidates[:5])