import numpy as np


def constrained_wls(
    y: np.ndarray,
    X: np.ndarray,
    w: np.ndarray,
    industry_mcap_weights: np.ndarray,
    n_styles: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Constrained WLS via Lagrange multiplier: Σ(mcap_j × f_industry_j) = 0.

    KKT system:
        [X'WX  C] [f]   [X'Wy]
        [C'    0] [λ] = [  0  ]

    Parameters:
        y: (N,) excess returns
        X: (N, 1+S+I) design matrix [market(1) | styles(S) | industries(I)]
        w: (N,) weights = sqrt(market_cap)
        industry_mcap_weights: (I,) mcap share per industry
        n_styles: number of style factors actually present in X

    Returns:
        (factor_returns, specific_returns)
    """
    N, K = X.shape
    w_norm = w / w.sum()

    # element-wise weighting: O(N×K) memory, avoids np.diag(N×N)
    Xw = X * w_norm[:, None]
    XtWX = Xw.T @ X
    XtWy = Xw.T @ y

    # constraint vector C: mcap weights at industry factor positions
    # industry columns start at index 1 (market) + n_styles
    C = np.zeros(K)
    C[1 + n_styles:] = industry_mcap_weights

    # build KKT system
    KKT = np.zeros((K + 1, K + 1))
    KKT[:K, :K] = XtWX
    KKT[:K, K] = C
    KKT[K, :K] = C
    rhs = np.zeros(K + 1)
    rhs[:K] = XtWy

    solution = np.linalg.solve(KKT, rhs)
    factor_returns = solution[:K]
    specific_returns = y - X @ factor_returns
    return factor_returns, specific_returns
