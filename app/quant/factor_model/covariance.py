import numpy as np


def ewm_factor_covariance(
    factor_returns: np.ndarray, halflife: int = 90
) -> np.ndarray:
    """
    Exponentially weighted factor covariance matrix (numpy implementation).

    Avoids pd.DataFrame.ewm().cov() which returns a MultiIndex DataFrame
    with version-dependent slicing behavior.

    Parameters:
        factor_returns: (T, K) factor return time series
        halflife: half-life in trading days

    Returns:
        (K, K) covariance matrix
    """
    T, K = factor_returns.shape
    decay = 0.5 ** (1.0 / halflife)
    raw_weights = decay ** np.arange(T - 1, -1, -1)
    weights = raw_weights / raw_weights.sum()

    weighted_mean = weights @ factor_returns
    centered = factor_returns - weighted_mean
    return (centered * weights[:, None]).T @ centered


def ewm_specific_variance(
    specific_returns: np.ndarray, halflife: int = 42
) -> np.ndarray:
    """
    Per-stock EWM variance of specific (idiosyncratic) returns.

    Parameters:
        specific_returns: (T, N) stock-level specific returns
        halflife: half-life in trading days

    Returns:
        (N,) variance per stock
    """
    T, N = specific_returns.shape
    decay = 0.5 ** (1.0 / halflife)
    raw_weights = decay ** np.arange(T - 1, -1, -1)
    weights = raw_weights / raw_weights.sum()

    weighted_mean = weights @ specific_returns
    centered = specific_returns - weighted_mean
    return (centered ** 2 * weights[:, None]).sum(axis=0)
