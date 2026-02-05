from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TypedDict


class Market(str, Enum):
    KR_KOSPI = "KR_KOSPI"
    KR_KOSDAQ = "KR_KOSDAQ"
    US_SP500 = "US_SP500"
    US_NASDAQ = "US_NASDAQ"


class DataSource(str, Enum):
    FDR = "FDR"
    YFINANCE = "YFINANCE"
    KIS = "KIS"
    FINNHUB = "FINNHUB"


class IntervalType(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    MINUTE_60 = "60m"
    DAILY = "D"


@dataclass
class OHLCV:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass
class StockInfo:
    symbol: str
    name: str
    market: Market
    sector: str | None = None
    industry: str | None = None


@dataclass
class DailyPrice:
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal | None = None
    data_source: DataSource | None = None


@dataclass
class MinutePrice:
    symbol: str
    datetime: datetime
    interval_type: IntervalType
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    data_source: DataSource | None = None


@dataclass
class RealtimeQuote:
    symbol: str
    price: Decimal
    open: Decimal
    high: Decimal
    low: Decimal
    volume: int
    change: Decimal
    change_percent: Decimal
    timestamp: datetime
    data_source: DataSource | None = None
