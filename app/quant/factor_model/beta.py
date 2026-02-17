"""
Beta calculation — single source of truth.

factor_beta : primary (Barra, requires ≥90 days factor history)
ols_beta    : fallback (simple Cov/Var, used when factor history insufficient)
"""

import numpy as np
import pandas as pd

from .exposure import STYLE_FACTORS


# ── Primary: Barra factor beta ──

def factor_beta(
    X_i: np.ndarray, X_m: np.ndarray, cov_matrix: np.ndarray
) -> float:
    """β_i = (X_i' Σ_F X_m) / (X_m' Σ_F X_m)"""
    denom = X_m @ cov_matrix @ X_m
    if denom == 0:
        return 1.0
    return float(X_i @ cov_matrix @ X_m / denom)


# ── Fallback: OLS beta (< 90 days factor history) ──

def ols_beta(stock_returns: pd.Series, market_returns: pd.Series) -> float:
    """β = Cov(R_i, R_m) / Var(R_m)"""
    aligned = pd.concat([stock_returns, market_returns], axis=1).dropna()
    if len(aligned) < 2:
        return 0.0
    cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
    var = aligned.iloc[:, 1].var()
    return cov / var if var != 0 else 0.0


# ── Risk decomposition ──

def risk_decomposition(
    X_i: np.ndarray, cov_matrix: np.ndarray, specific_var: float
) -> dict:
    """Total variance = X_i' Σ_F X_i + σ²_specific"""
    factor_var = float(X_i @ cov_matrix @ X_i)
    total_var = factor_var + specific_var
    factor_pct = factor_var / total_var if total_var > 0 else 0.0
    return {
        "total_var": total_var,
        "factor_var": factor_var,
        "specific_var": specific_var,
        "factor_pct": factor_pct,
    }


# ── Shared utility ──

def build_exposure_vector(
    style_values: np.ndarray,
    sector: str | None,
    factor_names: list[str],
) -> np.ndarray:
    """Build a single stock's full exposure vector [market | styles | industry one-hot]."""
    name_idx = {n: i for i, n in enumerate(factor_names)}
    X = np.zeros(len(factor_names))
    if "market" in name_idx:
        X[name_idx["market"]] = 1.0
    for j, f in enumerate(STYLE_FACTORS):
        if f in name_idx:
            X[name_idx[f]] = style_values[j]
    if sector and sector != "N/A" and sector in name_idx:
        X[name_idx[sector]] = 1.0
    return X
