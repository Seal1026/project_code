import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

import statsmodels.api as sm


def groupby_date(equity):
    d = equity.copy()
    return d.groupby(equity.index.date).last()


def _as_daily_equity(equity):
    equity_series = equity.copy() if isinstance(equity, pd.Series) else pd.Series(equity)
    if not isinstance(equity_series.index, pd.DatetimeIndex):
        raise ValueError("equity must use a DatetimeIndex")

    equity_daily = equity_series.groupby(equity_series.index.normalize()).last().dropna()
    equity_daily.index = pd.to_datetime(equity_daily.index)
    return equity_daily

def daily_pct_change(equity):
    return groupby_date(equity).pct_change().dropna()

def total_return(equity):
    equity_daily = groupby_date(equity)
    return equity_daily.iloc[-1] / equity_daily.iloc[0] - 1

def irr_cagr(equity):
    equity_daily = groupby_date(equity)
    first_date = pd.to_datetime(equity_daily.index[0])
    last_date = pd.to_datetime(equity_daily.index[-1])
    years = (last_date - first_date).days / 365.25
    return (equity_daily.iloc[-1] / equity_daily.iloc[0]) ** (1 / years) - 1

def vol(equity):
    daily_ret = daily_pct_change(equity)
    return daily_ret.std(ddof=1) * np.sqrt(252)

def sharpe(equity, rf_annual=0.01):
    daily_ret = daily_pct_change(equity)
    rf_daily = (1 + rf_annual) ** (1 / 252) - 1
    excess_ret = daily_ret - rf_daily
    std = excess_ret.std(ddof=1)
    if std == 0 or np.isnan(std):
        return np.nan
    return excess_ret.mean() / std * np.sqrt(252)

def hit_ratio(equity):
    daily_ret = daily_pct_change(equity)
    return (daily_ret > 0).mean()

def mdd(equity):
    equity_daily = groupby_date(equity)
    dd = equity_daily / equity_daily.cummax() - 1
    return abs(dd.min())

def alpha_beta(equity, spy_equity, rf_annual=0.0):
    strat_ret = daily_pct_change(equity)
    spy_ret = daily_pct_change(spy_equity)

    df = pd.concat([strat_ret, spy_ret], axis=1).dropna()
    df.columns = ["strategy", "spy"]

    rf_daily = (1 + rf_annual) ** (1 / 252) - 1
    y = df["strategy"] - rf_daily
    x = df["spy"] - rf_daily

    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit()

    alpha_daily = model.params["const"]
    beta = model.params["spy"]
    alpha_annual = (1 + alpha_daily) ** 252 - 1

    return alpha_annual, beta


def yearly_return_sharpe(equity, rf_annual=0.01, min_obs=2):
    equity_daily = _as_daily_equity(equity)
    daily_returns = equity_daily.pct_change().dropna()
    rf_daily = (1 + rf_annual) ** (1 / 252) - 1

    results = []
    for year, equity_year in equity_daily.groupby(equity_daily.index.year):
        year_start = equity_year.iloc[0]
        year_end = equity_year.iloc[-1]
        year_return = year_end / year_start - 1 if len(equity_year) > 0 else np.nan

        ret_year = daily_returns.loc[daily_returns.index.year == year]
        obs = int(len(ret_year))
        if obs >= min_obs:
            excess_ret_year = ret_year - rf_daily
            year_std = excess_ret_year.std(ddof=1)
            sharpe_year = np.nan if year_std == 0 or np.isnan(year_std) else excess_ret_year.mean() / year_std * np.sqrt(252)
        else:
            sharpe_year = np.nan

        results.append(
            {
                "year": int(year),
                "return": year_return,
                "sharpe_ratio": sharpe_year,
                "observations": obs,
            }
        )

    return pd.DataFrame(results)


def yearly_metrics_table(equity_series_dict, rf_annual=0.01, min_obs=2):
    frames = []
    for name, equity in equity_series_dict.items():
        yearly_df = yearly_return_sharpe(equity, rf_annual=rf_annual, min_obs=min_obs).copy()
        yearly_df.insert(0, "strategy", name)
        frames.append(yearly_df)

    if not frames:
        return pd.DataFrame(columns=["strategy", "year", "return", "sharpe_ratio", "observations"])

    return pd.concat(frames, ignore_index=True)

def print_metrics(name, equity, spy_equity=None):
    print(f"\n{name}")
    print(f"Total Return: {total_return(equity):.1%}")
    print(f"IRR/CAGR:     {irr_cagr(equity):.1%}")
    print(f"Vol:          {vol(equity):.1%}")
    print(f"Sharpe:       {sharpe(equity):.2f}")
    print(f"Hit Ratio:    {hit_ratio(equity):.1%}")
    print(f"MDD:          {mdd(equity):.1%}")

    if spy_equity is not None:
        alpha, beta = alpha_beta(equity, spy_equity)
        print(f"Alpha:        {alpha:.1%}")
        print(f"Beta:         {beta:.2f}")
