"""
yfinance response types.

Tested endpoints:
- Ticker.info: 182 fields (subset defined below)
- Ticker.history(interval="1d"): daily OHLCV + Dividends, Stock Splits
- Ticker.history(interval="5m"): 5-min OHLCV (max 60 days)
- Ticker.history(interval="1m"): 1-min OHLCV (max 7 days)

Notes:
- Close is already adjusted (split-adjusted)
- Korean stocks accessible via suffix: 005930.KS (KOSPI), 005930.KQ (KOSDAQ)
"""
from typing import TypedDict


class YfTickerInfo(TypedDict, total=False):
    """Subset of 182 available fields. All fields are optional."""
    # Identification
    symbol: str
    shortName: str
    longName: str

    # Classification
    sector: str
    sectorKey: str
    industry: str
    industryKey: str
    quoteType: str  # "EQUITY", "ETF", etc.

    # Market info
    exchange: str
    market: str
    currency: str
    financialCurrency: str

    # Price data
    currentPrice: float
    previousClose: float
    open: float
    dayLow: float
    dayHigh: float
    volume: int
    averageVolume: int
    averageVolume10days: int

    # 52-week range
    fiftyTwoWeekLow: float
    fiftyTwoWeekHigh: float
    fiftyDayAverage: float
    twoHundredDayAverage: float

    # Fundamentals
    marketCap: int
    enterpriseValue: int
    trailingPE: float
    forwardPE: float
    priceToBook: float
    priceToSalesTrailing12Months: float

    # Earnings
    trailingEps: float
    forwardEps: float
    earningsQuarterlyGrowth: float
    earningsGrowth: float
    revenueGrowth: float

    # Dividends
    dividendRate: float
    dividendYield: float
    payoutRatio: float
    exDividendDate: int  # timestamp

    # Risk metrics
    beta: float

    # Financial health
    totalCash: int
    totalDebt: int
    quickRatio: float
    currentRatio: float
    debtToEquity: float
    returnOnAssets: float
    returnOnEquity: float

    # Analyst
    recommendationKey: str  # "buy", "hold", "sell"
    recommendationMean: float
    numberOfAnalystOpinions: int
    targetMeanPrice: float
    targetHighPrice: float
    targetLowPrice: float


class YfDailyPrice(TypedDict):
    """Index: Date (datetime with timezone)"""
    Open: float
    High: float
    Low: float
    Close: float  # already adjusted
    Volume: int
    Dividends: float
    StockSplits: float  # field name is "Stock Splits" in DataFrame


class YfMinutePrice(TypedDict):
    """Index: Datetime (datetime with timezone)"""
    Open: float
    High: float
    Low: float
    Close: float
    Volume: int
    Dividends: float
    StockSplits: float  # field name is "Stock Splits" in DataFrame
