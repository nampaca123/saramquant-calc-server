import numpy as np
from app.db import get_connection, DailyPriceRepository

MIN_DATA_POINTS = 60


def _build_core(all_series: dict, stock_ids: list[int], weights: np.ndarray, lookback: int):
    date_sets = [set(all_series.get(sid, {}).keys()) for sid in stock_ids]
    if not date_sets or any(not ds for ds in date_sets):
        return {"returns": np.array([]), "effective_lookback": 0, "coverage": "INSUFFICIENT"}

    common_dates = sorted(set.intersection(*date_sets))
    if len(common_dates) < MIN_DATA_POINTS:
        return {"returns": np.array([]), "effective_lookback": len(common_dates), "coverage": "INSUFFICIENT"}

    price_matrix = np.array([
        [all_series[sid][d] for d in common_dates]
        for sid in stock_ids
    ]).T

    stock_returns = np.diff(price_matrix, axis=0) / price_matrix[:-1]
    portfolio_returns = stock_returns @ weights

    return {
        "returns": portfolio_returns,
        "effective_lookback": len(common_dates) - 1,
        "coverage": "FULL" if len(common_dates) >= lookback else "PARTIAL",
    }


def build_hypothetical_returns(
    stock_ids: list[int],
    weights: np.ndarray,
    lookback: int = 252,
) -> dict:
    with get_connection() as conn:
        price_repo = DailyPriceRepository(conn)
        all_series = {}
        for sid in stock_ids:
            prices = price_repo.get_prices(sid, limit=lookback)
            all_series[sid] = {p.date: float(p.close) for p in prices}

    return _build_core(all_series, stock_ids, weights, lookback)


def build_from_prices(
    all_series: dict[int, dict],
    stock_ids: list[int],
    weights: np.ndarray,
    lookback: int = 252,
) -> dict:
    return _build_core(all_series, stock_ids, weights, lookback)
