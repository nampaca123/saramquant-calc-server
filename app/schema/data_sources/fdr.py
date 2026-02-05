"""
FinanceDataReader response types.

Tested endpoints:
- StockListing("S&P500"): 502 stocks with Symbol, Name, Sector, Industry
- StockListing("NASDAQ"): 3802 stocks with Symbol, Name, IndustryCode, Industry
- StockListing("KRX"): BLOCKED (403 Forbidden from KRX server)
- DataReader(KR symbol): OHLCV + Change (no Adj Close)
- DataReader(US symbol): OHLCV + Adj Close
"""
from typing import TypedDict


class FdrSP500Stock(TypedDict):
    Symbol: str
    Name: str
    Sector: str
    Industry: str


class FdrNasdaqStock(TypedDict):
    Symbol: str
    Name: str
    IndustryCode: str
    Industry: str


class FdrKrxStock(TypedDict):
    """Currently unavailable due to KRX server blocking (403)."""
    Code: str
    Name: str
    Market: str  # KOSPI, KOSDAQ


class FdrDailyPriceKR(TypedDict):
    """
    Index: Date (datetime)
    No Adj Close for Korean stocks.
    """
    Open: float
    High: float
    Low: float
    Close: float
    Volume: int
    Change: float  # daily change ratio


class FdrDailyPriceUS(TypedDict):
    """Index: Date (datetime)"""
    Open: float
    High: float
    Low: float
    Close: float
    Volume: int
    AdjClose: float  # field name is "Adj Close" in DataFrame
