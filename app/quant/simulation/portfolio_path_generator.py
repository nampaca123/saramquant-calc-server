import numpy as np
from numpy.linalg import LinAlgError


def generate_portfolio_bootstrap_paths(
    current_prices: np.ndarray,
    historical_returns: np.ndarray,
    shares: np.ndarray,
    days: int,
    num_simulations: int,
) -> np.ndarray:
    rng = np.random.default_rng()
    T = historical_returns.shape[0]

    idx = rng.integers(0, T, size=(num_simulations, days))
    sampled = historical_returns[idx]

    price_paths = np.empty((num_simulations, days + 1, len(current_prices)))
    price_paths[:, 0, :] = current_prices
    price_paths[:, 1:, :] = current_prices * np.cumprod(1.0 + sampled, axis=1)

    portfolio_values = (price_paths * shares).sum(axis=2)
    return portfolio_values


def generate_correlated_gbm_paths(
    current_prices: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    correlation: np.ndarray,
    shares: np.ndarray,
    days: int,
    num_simulations: int,
) -> np.ndarray:
    n = len(current_prices)
    rng = np.random.default_rng()

    try:
        L = np.linalg.cholesky(correlation)
    except LinAlgError:
        correlation = _nearest_positive_definite(correlation)
        L = np.linalg.cholesky(correlation)

    z = rng.standard_normal((num_simulations, days, n))
    correlated_z = z @ L.T

    dt = 1.0
    drift = (mu - 0.5 * sigma ** 2) * dt
    diffusion = sigma * np.sqrt(dt) * correlated_z
    log_returns = drift + diffusion

    price_paths = np.empty((num_simulations, days + 1, n))
    price_paths[:, 0, :] = current_prices
    price_paths[:, 1:, :] = current_prices * np.cumprod(np.exp(log_returns), axis=1)

    portfolio_values = (price_paths * shares).sum(axis=2)
    return portfolio_values


def _nearest_positive_definite(A: np.ndarray) -> np.ndarray:
    B = (A + A.T) / 2
    eigvals, eigvecs = np.linalg.eigh(B)
    eigvals = np.maximum(eigvals, 1e-8)
    result = eigvecs @ np.diag(eigvals) @ eigvecs.T
    result = (result + result.T) / 2
    np.fill_diagonal(result, 1.0)
    return result
