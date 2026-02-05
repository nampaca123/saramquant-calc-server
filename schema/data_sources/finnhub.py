"""
Finnhub API response types.

Base URL: https://finnhub.io/api/v1
Rate limit: 60 requests/minute (free tier)
API key required: https://finnhub.io/register

Free tier limitations:
- Quote: OK (realtime)
- Company Profile: OK
- Market Status: OK
- Symbol Search: OK
- Candles (OHLCV): REQUIRES PAID PLAN (403 Forbidden)

For historical OHLCV data, use yfinance instead.
"""
from typing import TypedDict


class FinnhubQuote(TypedDict):
    """
    GET /quote?symbol={symbol}
    Realtime quote. Note: Volume not included.
    """
    c: float   # current price
    d: float   # change (absolute)
    dp: float  # change percent
    h: float   # high of day
    l: float   # low of day
    o: float   # open
    pc: float  # previous close
    t: int     # timestamp (unix seconds)


class FinnhubProfile(TypedDict):
    """GET /stock/profile2?symbol={symbol}"""
    country: str
    currency: str
    estimateCurrency: str
    exchange: str
    finnhubIndustry: str
    ipo: str                    # IPO date (YYYY-MM-DD)
    logo: str                   # logo URL
    marketCapitalization: float # in millions
    name: str
    phone: str
    shareOutstanding: float     # in millions
    ticker: str
    weburl: str


class FinnhubMarketStatus(TypedDict):
    """GET /stock/market-status?exchange={exchange}"""
    exchange: str
    holiday: str | None
    isOpen: bool
    session: str | None  # "pre-market", "regular", "post-market"
    t: int               # timestamp (unix seconds)
    timezone: str


class FinnhubSearchResult(TypedDict):
    """Single result item from symbol search."""
    description: str
    displaySymbol: str
    symbol: str
    type: str  # "Common Stock", "ETF", etc.


class FinnhubSearchResponse(TypedDict):
    """GET /search?q={query}"""
    count: int
    result: list[FinnhubSearchResult]


class FinnhubCandle(TypedDict):
    """
    GET /stock/candle (PAID PLAN ONLY)
    Resolution: 1, 5, 15, 30, 60, D, W, M
    Free tier returns 403 Forbidden.
    """
    c: list[float]  # close prices
    h: list[float]  # high prices
    l: list[float]  # low prices
    o: list[float]  # open prices
    v: list[int]    # volumes
    t: list[int]    # timestamps (unix)
    s: str          # status: "ok" or "no_data"
