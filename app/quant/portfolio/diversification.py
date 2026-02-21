import numpy as np


def compute_diversification_metrics(
    weights: np.ndarray,
    individual_vols: np.ndarray | None = None,
    portfolio_vol: float | None = None,
    sectors: list[str | None] | None = None,
) -> dict:
    hhi = float(np.sum(weights ** 2))
    effective_n = 1.0 / hhi if hhi > 0 else 0.0
    max_weight = float(np.max(weights))

    result = {
        "hhi": round(hhi, 6),
        "effective_n": round(effective_n, 2),
        "max_weight": round(max_weight, 6),
        "holdings_count": len(weights),
    }

    if individual_vols is not None and portfolio_vol is not None and portfolio_vol > 0:
        weighted_vol_sum = float(np.sum(weights * individual_vols))
        diversification_ratio = weighted_vol_sum / portfolio_vol
        result["diversification_ratio"] = round(diversification_ratio, 4)

    if sectors:
        sector_weights: dict[str, float] = {}
        for w, s in zip(weights, sectors):
            key = s or "Unknown"
            sector_weights[key] = sector_weights.get(key, 0.0) + float(w)
        result["sector_concentration"] = {
            k: round(v, 6) for k, v in sorted(sector_weights.items(), key=lambda x: -x[1])
        }
        result["sector_hhi"] = round(sum(v ** 2 for v in sector_weights.values()), 6)

    return result
