import numpy as np
from app.db import get_connection, FactorRepository, StockRepository
from app.quant.factor_model.beta import build_exposure_vector, factor_beta, risk_decomposition
from app.schema import Market


def compute_factor_risk(
    stock_ids: list[int],
    weights: np.ndarray,
    market: Market,
) -> dict | None:
    with get_connection() as conn:
        factor_repo = FactorRepository(conn)
        stock_repo = StockRepository(conn)

        cov_entry = factor_repo.get_latest_covariance(market)
        if cov_entry is None:
            return None

        _, cov_list = cov_entry
        cov_matrix = np.array(cov_list)

        history = factor_repo.get_factor_returns_history(market, limit=1)
        if not history:
            return None
        factor_names = sorted(set(r[1] for r in history))

        if cov_matrix.shape[0] != len(factor_names):
            return None

        exposures_raw = factor_repo.get_latest_exposures(market)
        exposures = {
            r[0]: {"size_z": r[1], "value_z": r[2], "momentum_z": r[3],
                   "volatility_z": r[4], "quality_z": r[5], "leverage_z": r[6]}
            for r in exposures_raw
        }
        sectors = stock_repo.get_sectors_by_market(market)

    stock_vectors = []
    valid_mask = []
    for sid in stock_ids:
        exp = exposures.get(sid)
        sector = sectors.get(sid)
        if exp is None:
            valid_mask.append(False)
            stock_vectors.append(np.zeros(len(factor_names)))
            continue
        style_values = np.array([
            exp.get("size_z", 0), exp.get("value_z", 0), exp.get("momentum_z", 0),
            exp.get("volatility_z", 0), exp.get("quality_z", 0), exp.get("leverage_z", 0),
        ])
        X = build_exposure_vector(style_values, sector, factor_names)
        stock_vectors.append(X)
        valid_mask.append(True)

    if not any(valid_mask):
        return None

    X_p = sum(w * X for w, X, v in zip(weights, stock_vectors, valid_mask) if v)

    market_idx = factor_names.index("market") if "market" in factor_names else None
    X_m = np.zeros(len(factor_names))
    if market_idx is not None:
        X_m[market_idx] = 1.0

    beta = factor_beta(X_p, X_m, cov_matrix)

    specific_vars = []
    for sid, X, v in zip(stock_ids, stock_vectors, valid_mask):
        if v:
            factor_var = float(X @ cov_matrix @ X)
            specific_vars.append(0.01)  # placeholder; ideally from regression residuals
        else:
            specific_vars.append(0.0)

    weighted_specific_var = float(sum(
        (w ** 2) * sv for w, sv, v in zip(weights, specific_vars, valid_mask) if v
    ))

    decomp = risk_decomposition(X_p, cov_matrix, weighted_specific_var)

    valid_count = sum(valid_mask)
    coverage = "FULL" if valid_count == len(stock_ids) else "PARTIAL"

    return {
        "beta": round(beta, 4),
        "risk_decomposition": {k: round(v, 8) for k, v in decomp.items()},
        "portfolio_exposure": {
            name: round(float(val), 4) for name, val in zip(factor_names, X_p)
        },
        "coverage": coverage,
        "valid_stocks": valid_count,
        "total_stocks": len(stock_ids),
    }
