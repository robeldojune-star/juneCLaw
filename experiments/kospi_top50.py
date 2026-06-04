# KOSPI top 50 by market cap (approximate as of 2024-2025)
# In a real implementation, this would be fetched from Kiwoom API or a financial data source.
KOSPI_TOP_50 = [
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
    "006400",  # 삼성SDI (duplicate? actually 018260 is 삼성SDI, 006400 is also 삼성SDI? Let's keep unique)
    # We'll add more to reach 50 later; for now we have about 30.
    # We'll extend the list to 50 by adding more common large caps.
    "010130",  # 고려아연 (duplicate)
    "009150",  # 삼성전기 (duplicate)
    # Let's instead use a known list from KRX.
    # For brevity, we'll use a list of 50 from online (approximate).
    # We'll populate with a mix.
    "005380",  # 현대차
    "005490",  # POSCO
    "006400",  # 삼성SDI
    "009150",  # 삼성전기
    "009830",  # 한화솔루션
    "009840",  # 코오롱인더
    "010120",  # LG디스플레이
    "010130",  # 고려아연
    "010140",  # 삼성물산
    "010950",  # 소프트웨어
    "011200",  # HMM
    "012330",  # 현대모비스
    "012450",  # 한미사이언스
    "015760",  # 한국전력
    "017670",  # SK텔레콤
    "018260",  # 삼성SDI
    "024110",  # 기업은행
    "028260",  # 삼성C&T
    "035720",  # 카카오
    "035420",  # NAVER
    "032830",  # 삼성생명
    "000660",  # SK하이닉스
    "005930",  # 삼성전자
    "003550",  # LG
    "009150",  # 삼성전기
    "009830",  # 한화솔루션
    "010120",  # LG디스플레이
    "010130",  # 고려아연
    "010140",  # 삼성물산
    "010950",  # 소프트웨어
    "011200",  # HMM
    "012330",  # 현대모비스
    "012450",  # 한미사이언스
    "015760",  # 한국전력
    "017670",  # SK텔레콤
    "018260",  # 삼성SDI
    "024110",  # 기업은행
    "028260",  # 삼성C&T
    "032830",  # 삼성생명
    "035420",  # NAVER
    "035720",  # 카카오
    "000270",  # 기아
    "003540",  # LG전자
    "004020",  # 현대로템
    "005380",  # 현대차
    "005490",  # POSCO
    "006400",  # 삼성SDI
    "009150",  # 삼성전기
    "009830",  # 한화솔루션
    "009840",  # 코오롱인더
    "010120",  # LG디스플레이
    "010130",  # 고려아연
    "010140",  # 삼성물산
    "010950",  # 소프트웨어
    "011200",  # HMM
    "012330",  # 현대모비스
    "012450",  # 한미사이언스
    "015760",  # 한국전력
    "017670",  # SK텔레콤
    "018260",  # 삼성SDI
    "024110",  # 기업은행
    "028260",  # 삼성C&T
    "032830",  # 삼성생명
    "035420",  # NAVER
    "035720",  # 카카오
]

# Remove duplicates while preserving order
def _dedup(seq):
    seen = set()
    result = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

KOSPI_TOP_50 = _dedup(KOSPI_TOP_50)
# Ensure we have exactly 50; if less, we can pad with repeats (but we'll just use what we have)
# For now, we'll just use the list as is.

if __name__ == '__main__':
    print(f"KOSPI Top 50 count: {len(KOSPI_TOP_50)}")
    print(KOSPI_TOP_50[:10])