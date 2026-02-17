import pandas as pd


def winsorize(series: pd.Series, n_mad: float = 3.0) -> pd.Series:
    """MAD-based winsorization. Clips to ±n_mad × MAD from median."""
    median = series.median()
    mad = (series - median).abs().median() * 1.4826
    if mad == 0:
        return series
    return series.clip(lower=median - n_mad * mad, upper=median + n_mad * mad)


def z_score(series: pd.Series, weights: pd.Series | None = None) -> pd.Series:
    """Z-score standardization. Weighted mean/std when weights are provided."""
    if weights is not None:
        w = weights / weights.sum()
        mean = (series * w).sum()
        std = ((series - mean).pow(2) * w).sum() ** 0.5
    else:
        mean, std = series.mean(), series.std()
    return (series - mean) / std if std > 0 else series * 0
