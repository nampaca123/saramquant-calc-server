import pandas as pd


def daily_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change()


def alpha(
    stock_returns: pd.Series,
    market_returns: pd.Series,
    risk_free_rate: float,
    beta_value: float,
    annualize: bool = True,
) -> float:
    aligned = pd.concat([stock_returns, market_returns], axis=1).dropna()
    if len(aligned) < 2:
        return 0.0

    daily_rf = risk_free_rate / 100 / 252
    stock_mean = aligned.iloc[:, 0].mean()
    market_mean = aligned.iloc[:, 1].mean()
    daily_alpha = stock_mean - (daily_rf + beta_value * (market_mean - daily_rf))

    return daily_alpha * 252 if annualize else daily_alpha


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float,
    annualize: bool = True,
) -> float:
    clean_returns = returns.dropna()
    if len(clean_returns) < 2:
        return 0.0

    daily_rf = risk_free_rate / 100 / 252
    excess = clean_returns.mean() - daily_rf
    std = clean_returns.std()

    if std == 0:
        return 0.0

    ratio = excess / std
    return ratio * (252 ** 0.5) if annualize else ratio
