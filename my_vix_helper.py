import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _as_daily_equity(equity):
    if isinstance(equity, pd.Series):
        equity_series = equity.copy()
    else:
        equity_series = pd.Series(equity)

    if not isinstance(equity_series.index, pd.DatetimeIndex):
        raise ValueError("equity must use a DatetimeIndex so it can be aligned with VIX dates")

    equity_daily = equity_series.groupby(equity_series.index.normalize()).last().dropna()
    equity_daily.index = pd.to_datetime(equity_daily.index)
    return equity_daily


def _prepare_vix_open(df_vix):
    if "Open" not in df_vix.columns:
        raise ValueError("df_vix must contain an 'Open' column")

    vix_open = df_vix["Open"].copy().dropna()
    vix_open.index = pd.to_datetime(vix_open.index).normalize()
    vix_open.name = "vix_open"
    return vix_open


def daily_returns_with_vix(equity, df_vix):
    equity_daily = _as_daily_equity(equity)
    daily_returns = equity_daily.pct_change().dropna()
    daily_returns.name = "strategy_return"

    vix_open = _prepare_vix_open(df_vix)

    combined = pd.concat([daily_returns, vix_open], axis=1, join="inner").dropna()
    combined.index.name = "date"
    return combined


def conditional_sharpe_ratio(returns, rf_annual=0.01):
    returns = pd.Series(returns).dropna()
    if len(returns) < 2:
        return np.nan

    rf_daily = (1 + rf_annual) ** (1 / 252) - 1
    excess_returns = returns - rf_daily
    std = excess_returns.std(ddof=1)
    if std == 0 or np.isnan(std):
        return np.nan

    return excess_returns.mean() / std * np.sqrt(252)


def sharpe_by_vix_threshold(equity, df_vix, thresholds=None, rf_annual=0.01, min_obs=20):
    if thresholds is None:
        thresholds = range(6, 52, 2)

    combined = daily_returns_with_vix(equity, df_vix)

    results = []
    for threshold in thresholds:
        subset = combined.loc[combined["vix_open"] > threshold, "strategy_return"]
        sharpe_value = conditional_sharpe_ratio(subset, rf_annual=rf_annual) if len(subset) >= min_obs else np.nan
        results.append(
            {
                "threshold": threshold,
                "label": f"VIX > {threshold}",
                "sharpe_ratio": sharpe_value,
                "observations": int(len(subset)),
            }
        )

    return pd.DataFrame(results)


def plot_sharpe_by_vix_threshold(
    sharpe_df,
    ax=None,
    title="Market Volatility vs Profitability",
    color="#1f77b4",
):
    plot_df = sharpe_df.copy()
    plot_df = plot_df.dropna(subset=["sharpe_ratio"])

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 4.5))

    ax.bar(plot_df["label"], plot_df["sharpe_ratio"], color=color, edgecolor="#145a86")
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel("Sharpe Ratio")
    ax.set_xlabel("VIX @ Open")
    ax.grid(axis="y", alpha=0.2, linestyle="--")
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=90)
    plt.tight_layout()
    return ax


def build_vix_regime_report(equity, df_vix, thresholds=None, rf_annual=0.01, min_obs=20, ax=None):
    sharpe_df = sharpe_by_vix_threshold(
        equity=equity,
        df_vix=df_vix,
        thresholds=thresholds,
        rf_annual=rf_annual,
        min_obs=min_obs,
    )
    plot_sharpe_by_vix_threshold(sharpe_df, ax=ax)
    return sharpe_df
