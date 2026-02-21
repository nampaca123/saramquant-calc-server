import numpy as np
from app.db import get_connection, BenchmarkRepository
from app.schema import Benchmark


def compute_risk_score(
    portfolio_returns: np.ndarray,
    market_group: str,
    effective_lookback: int,
) -> dict:
    if len(portfolio_returns) < 20:
        return {"score": None, "tier": "UNKNOWN", "reason": "Insufficient data"}

    portfolio_vol = float(np.std(portfolio_returns, ddof=1) * np.sqrt(252))

    benchmark = Benchmark.KR_KOSPI if market_group == "KR" else Benchmark.US_SP500
    benchmark_vol = _get_benchmark_vol(benchmark, lookback=min(effective_lookback, 252))

    if benchmark_vol is None or benchmark_vol == 0:
        return {"score": None, "tier": "UNKNOWN", "reason": "Benchmark data unavailable"}

    score = (portfolio_vol / benchmark_vol) * 50
    score = min(score, 100.0)

    tier = _score_to_tier(score)

    return {
        "score": round(score, 2),
        "tier": tier,
        "portfolio_vol": round(portfolio_vol, 6),
        "benchmark_vol": round(benchmark_vol, 6),
        "effective_lookback": effective_lookback,
    }


def _score_to_tier(score: float) -> str:
    if score <= 40:
        return "STABLE"
    elif score <= 70:
        return "CAUTION"
    else:
        return "WARNING"


def _get_benchmark_vol(benchmark: Benchmark, lookback: int) -> float | None:
    with get_connection() as conn:
        repo = BenchmarkRepository(conn)
        prices = repo.get_prices(benchmark, limit=lookback + 1)

    if len(prices) < 20:
        return None

    closes = np.array([float(p.close) for p in prices])[::-1]
    returns = np.diff(closes) / closes[:-1]
    return float(np.std(returns, ddof=1) * np.sqrt(252))
