import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

import statsmodels.api as sm


def groupby_date(equity):
    d = equity.copy()
    return d.groupby(equity.index.date).last()

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
    return excess_ret.mean() / excess_ret.std(ddof=1) * np.sqrt(252)

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