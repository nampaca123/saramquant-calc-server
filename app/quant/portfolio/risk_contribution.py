import numpy as np


def compute_mcar(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
) -> dict:
    portfolio_var = float(weights @ cov_matrix @ weights)
    portfolio_vol = np.sqrt(portfolio_var) if portfolio_var > 0 else 0.0

    if portfolio_vol == 0:
        n = len(weights)
        return {
            "portfolio_vol": 0.0,
            "mcar": [0.0] * n,
            "contribution_pct": [1.0 / n] * n if n > 0 else [],
        }

    marginal = cov_matrix @ weights / portfolio_vol
    contribution = weights * marginal
    total_contribution = float(contribution.sum())

    pct = contribution / total_contribution if total_contribution > 0 else contribution

    return {
        "portfolio_vol": round(float(portfolio_vol), 8),
        "mcar": [round(float(m), 8) for m in marginal],
        "contribution": [round(float(c), 8) for c in contribution],
        "contribution_pct": [round(float(p), 6) for p in pct],
    }
