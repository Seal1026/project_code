import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


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


def daily_return_by_vix_threshold(equity, df_vix, thresholds=None, min_obs=20):
    if thresholds is None:
        thresholds = range(6, 52, 2)

    combined = daily_returns_with_vix(equity, df_vix)

    results = []
    for threshold in thresholds:
        subset = combined.loc[combined["vix_open"] > threshold, "strategy_return"]
        avg_daily_return = subset.mean() if len(subset) >= min_obs else np.nan
        results.append(
            {
                "threshold": threshold,
                "label": f"VIX > {threshold}",
                "daily_return": avg_daily_return,
                "observations": int(len(subset)),
            }
        )

    return pd.DataFrame(results)


def daily_return_by_vix_bin(equity, df_vix, bins=None, min_obs=20):
    if bins is None:
        bins = [0, 15, 20, 25, 30, np.inf]

    combined = daily_returns_with_vix(equity, df_vix).copy()
    labels = []
    for left, right in zip(bins[:-1], bins[1:]):
        if np.isinf(right):
            labels.append(f"VIX >= {left}")
        else:
            labels.append(f"{left} <= VIX < {right}")

    combined["vix_bin"] = pd.cut(
        combined["vix_open"],
        bins=bins,
        labels=labels,
        right=False,
        include_lowest=True,
    )

    results = []
    for label in labels:
        subset = combined.loc[combined["vix_bin"] == label, "strategy_return"]
        avg_daily_return = subset.mean() if len(subset) >= min_obs else np.nan
        results.append(
            {
                "label": label,
                "daily_return": avg_daily_return,
                "observations": int(len(subset)),
            }
        )

    return pd.DataFrame(results)


def plot_daily_return_by_vix_threshold(
    return_df,
    ax=None,
    title="Market Volatility vs Profitability",
    color="#1f77b4",
    xlabel="VIX Threshold",
):
    plot_df = return_df.copy()
    plot_df = plot_df.dropna(subset=["daily_return"])

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 4.5))

    ax.bar(plot_df["label"], plot_df["daily_return"], color=color, edgecolor="#145a86")
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel("Average Daily Return")
    ax.set_xlabel(xlabel)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.grid(axis="y", alpha=0.2, linestyle="--")
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=90)
    plt.tight_layout()
    return ax


def plot_daily_return_by_vix_bin(
    return_df,
    ax=None,
    title="Average Daily Return by VIX Regime",
    color="#2c7fb8",
    xlabel="VIX Regime",
):
    plot_df = return_df.copy()
    plot_df = plot_df.dropna(subset=["daily_return"])

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 4.5))

    ax.bar(plot_df["label"], plot_df["daily_return"], color=color, edgecolor="#1d4f73")
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel("Average Daily Return")
    ax.set_xlabel(xlabel)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.grid(axis="y", alpha=0.2, linestyle="--")
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=35)
    plt.tight_layout()
    return ax


def plot_daily_return_vs_vix_scatter(
    equity,
    df_vix,
    ax=None,
    title="Daily Return vs VIX Open",
    color="#2c7fb8",
    alpha=0.45,
    point_size=18,
    xlabel="VIX Open",
):
    scatter_df = daily_returns_with_vix(equity, df_vix).copy()

    if ax is None:
        _, ax = plt.subplots(figsize=(11, 5))

    ax.scatter(
        scatter_df["vix_open"],
        scatter_df["strategy_return"],
        s=point_size,
        alpha=alpha,
        color=color,
        edgecolors="none",
        label="Daily observations",
    )
    ax.axhline(0, color="#6b7280", linewidth=1.0, linestyle="--", alpha=0.8)
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Daily Return")
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.grid(True, alpha=0.2, linestyle="--")
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="best")
    plt.tight_layout()
    return ax


def build_vix_regime_report(equity, df_vix, thresholds=None, rf_annual=0.01, min_obs=20, ax=None):
    return_df = daily_return_by_vix_threshold(
        equity=equity,
        df_vix=df_vix,
        thresholds=thresholds,
        min_obs=min_obs,
    )
    plot_daily_return_by_vix_threshold(return_df, ax=ax)
    return return_df


def build_vix_bin_report(equity, df_vix, bins=None, min_obs=20, ax=None):
    return_df = daily_return_by_vix_bin(
        equity=equity,
        df_vix=df_vix,
        bins=bins,
        min_obs=min_obs,
    )
    plot_daily_return_by_vix_bin(return_df, ax=ax)
    return return_df
