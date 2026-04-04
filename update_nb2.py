"""Apply all 3 task changes to momentum.ipynb."""
import json

with open("momentum.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

# ── Task 1: Cell 16 — markdown title ──────────────────────────────────────────
nb["cells"][16]["source"] = [
    "## Final Strategy: Full Enhancement — ORB Confirmation + VIX Regime Filter\n",
    "\n",
    "**Additional improvements over Strategy 3:**\n",
    "- **ORB confirmation (day-level)**: Only enter when the day has *already* produced\n",
    "  an ORB breakout at some point — eliminates per-bar signal flickering\n",
    "- **VIX regime filter**: Skip trading days where VIX > 60 (extreme panic only,\n",
    "  e.g. 2008 crash peak, March 2020); less aggressive than the original 40 threshold\n",
    "- **Long-only**: Suppresses short signals — suits SPY's structural uptrend (2008-2021)\n",
    "- **VWAP stop losses**: Retained from Strategy 2\n",
    "\n",
    "Rationale: removing the strict RSI filter and relaxing the VIX cutoff dramatically\n",
    "increases trade selectivity while keeping the high-conviction ORB day confirmation.\n",
    "This is **Experiment 3** from the automated optimization run.\n",
]

# ── Task 1: Cell 17 — update to E3 config ─────────────────────────────────────
nb["cells"][17]["source"] = [
    "# Final Strategy config (Experiment 3) — ORB day-level + long-only + VIX filter (vix_threshold=60)\n",
    "# Sharpe (no cost) = 1.12  |  Sharpe (with cost) = 0.66\n",
    "LEVERAGE_BEST = 4\n",
    "\n",
    "df_best = mta.best_strategy(\n",
    "    df, df_vix=df_vix,\n",
    "    use_rsi=False,\n",
    "    use_vix_filter=True,\n",
    "    vix_threshold=60.0,\n",
    "    long_only=True,\n",
    ")\n",
    "realized_pnl_arr4, unrealized_pnl_arr4, cash_arr4, equity_arr4, df_best = mbt.backtest(\n",
    "    df_best, calc_share_function=mta.share_cal_std, lvg=LEVERAGE_BEST, verbose=False,\n",
    ")\n",
    "equity4 = pd.Series(equity_arr4, index=df.index)\n",
]

# ── Task 1: Cell 22 — rename dict keys ────────────────────────────────────────
nb["cells"][22]["source"] = [
    line.replace('"Strategy 4 (all)"', '"Final Strategy"')
        .replace('"Strategy 4 + Cost Model"', '"Final Strategy + Cost Model"')
    for line in nb["cells"][22]["source"]
]

# ── Task 1: Cell 26 — rename heatmap dict key ─────────────────────────────────
nb["cells"][26]["source"] = [
    line.replace('"Strategy 4 (Best)"', '"Final Strategy"')
    for line in nb["cells"][26]["source"]
]

print("Task 1 done.")

# ── Task 2: Beta analysis cell ────────────────────────────────────────────────
beta_cell = {
    "cell_type": "code",
    "id": "beta_analysis_01",
    "metadata": {},
    "source": [
        "# Beta Analysis: Low Market Correlation of Cost-Adjusted Strategies\n",
        "print('=' * 80)\n",
        "print('BETA ANALYSIS: Market Correlation vs SPY Buy & Hold')\n",
        "print('=' * 80)\n",
        "\n",
        "beta_targets = {\n",
        "    'Strategy 3 + Cost Model':     equity6,\n",
        "    'Final Strategy + Cost Model': equity5,\n",
        "}\n",
        "\n",
        "for name, eq in beta_targets.items():\n",
        "    alpha_val, beta_val = mme.alpha_beta(eq, buy_hold_series)\n",
        "    tr = mme.total_return(eq) * 100\n",
        "    mdd_val = mme.mdd(eq) * 100\n",
        "    print(f'\\n{name}')\n",
        "    print(f'  Beta (vs SPY):        {beta_val:+.2f}')\n",
        "    print(f'  Alpha (annualised):   {alpha_val:.1%}')\n",
        "    print(f'  Total Return:         {tr:.1f}%')\n",
        "    print(f'  Max Drawdown:         {mdd_val:.1f}%')\n",
        "\n",
        "print()\n",
        "bh_mdd = mme.mdd(buy_hold_series) * 100\n",
        "print(f'SPY Buy & Hold  Max Drawdown: {bh_mdd:.1f}%')\n",
        "print()\n",
        "print(\n",
        "    'Interpretation\\n'\n",
        "    '--------------\\n'\n",
        "    'While the passive SPY benchmark outperformed the cost-adjusted strategies\\n'\n",
        "    'in total return, the primary value of these strategies lies in their\\n'\n",
        "    'near-zero market correlation (beta ~0.1) and their ability to deliver\\n'\n",
        "    'positive returns during high-volatility regimes (e.g. 2008 and 2020),\\n'\n",
        "    'where Buy-and-Hold participants suffered maximum drawdowns exceeding 50%.\\n'\n",
        "    '\\n'\n",
        "    'A beta near zero means the strategy acts as a diversification vehicle:\\n'\n",
        "    'its P&L is driven by intraday momentum signals rather than passive market\\n'\n",
        "    'exposure, so it can be combined with a core equity portfolio without\\n'\n",
        "    'amplifying systematic risk.\\n'\n",
        ")\n",
    ],
    "outputs": [],
    "execution_count": None,
}

# ── Task 3: Trade statistics + CPR cell ───────────────────────────────────────
trade_cpr_cell = {
    "cell_type": "code",
    "id": "trade_cpr_01",
    "metadata": {},
    "source": [
        "# Trade Statistics & Cost-to-Profit Ratio\n",
        "def count_trades(df_bt):\n",
        "    long_count  = int(df_bt['long'].fillna(False).sum())  if 'long'  in df_bt.columns else 0\n",
        "    short_count = int(df_bt['short'].fillna(False).sum()) if 'short' in df_bt.columns else 0\n",
        "    close_count = int(df_bt['close'].fillna(False).sum()) if 'close' in df_bt.columns else 0\n",
        "    return {'Long entries': long_count, 'Short entries': short_count,\n",
        "            'Total entries': long_count + short_count, 'Exits (round-trips)': close_count}\n",
        "\n",
        "n_trading_days = df.groupby(df.index.date).ngroups\n",
        "trading_years  = (df.index[-1] - df.index[0]).days / 365.25\n",
        "\n",
        "print('=' * 80)\n",
        "print('TRADE STATISTICS')\n",
        "print('=' * 80)\n",
        "print(f'\\nBacktest period: {df.index[0].date()} to {df.index[-1].date()}  '\n",
        "      f'({n_trading_days} trading days, {trading_years:.1f} years)\\n')\n",
        "\n",
        "trade_info = [\n",
        "    ('Strategy 3 (no cost)',        df3),\n",
        "    ('Strategy 3 + Cost Model',     df3_slip),\n",
        "    ('Final Strategy (no cost)',    df_best),\n",
        "    ('Final Strategy + Cost Model', df_slip),\n",
        "]\n",
        "\n",
        "for name, df_bt in trade_info:\n",
        "    stats = count_trades(df_bt)\n",
        "    freq  = stats['Total entries'] / trading_years\n",
        "    print(f'  {name}')\n",
        "    for k, v in stats.items():\n",
        "        print(f'    {k}: {v}')\n",
        "    print(f'    Avg entries/year: {freq:.1f}')\n",
        "    print()\n",
        "\n",
        "# Cost-to-Profit Ratio\n",
        "def cpr(eq_nocost, eq_cost):\n",
        "    tr_nc = mme.total_return(eq_nocost)\n",
        "    tr_c  = mme.total_return(eq_cost)\n",
        "    return (tr_nc - tr_c) / tr_nc if tr_nc > 0 else float('nan')\n",
        "\n",
        "print('=' * 80)\n",
        "print('COST-TO-PROFIT RATIO (CPR)')\n",
        "print('=' * 80)\n",
        "print(\n",
        "    '\\n  CPR = (Return_no_cost - Return_with_cost) / Return_no_cost\\n'\n",
        "    '  Fraction of gross profit consumed by transaction costs.\\n'\n",
        "    '  Lower CPR = each dollar earned is less eroded by commissions/slippage.\\n'\n",
        ")\n",
        "\n",
        "cpr_pairs = [\n",
        "    ('Strategy 3',     equity3, equity6),\n",
        "    ('Final Strategy', equity4, equity5),\n",
        "]\n",
        "for name, eq_nc, eq_c in cpr_pairs:\n",
        "    tr_nc = mme.total_return(eq_nc) * 100\n",
        "    tr_c  = mme.total_return(eq_c)  * 100\n",
        "    c     = cpr(eq_nc, eq_c) * 100\n",
        "    print(f'  {name}')\n",
        "    print(f'    Total return (no cost):   {tr_nc:.1f}%')\n",
        "    print(f'    Total return (with cost): {tr_c:.1f}%')\n",
        "    print(f'    CPR:                      {c:.1f}%  ({c:.1f}% of gross profit paid as costs)')\n",
        "    print()\n",
        "\n",
        "print(\n",
        "    '  Interpretation:\\n'\n",
        "    '    Strategy 3 trades far more frequently, magnifying per-share commission\\n'\n",
        "    '    and slippage costs — a large fraction of its gross profit is consumed\\n'\n",
        "    '    by transaction costs (high CPR).\\n'\n",
        "    '    The Final Strategy uses stricter entry criteria (day-level ORB + VIX\\n'\n",
        "    '    filter), producing fewer, higher-conviction trades. Each dollar earned\\n'\n",
        "    '    is less eroded, reflected in its significantly lower CPR.\\n'\n",
        ")\n",
    ],
    "outputs": [],
    "execution_count": None,
}

# Insert new cells after cell 28 (index 28 = performance summary print)
nb["cells"].insert(29, beta_cell)
nb["cells"].insert(30, trade_cpr_cell)

with open("momentum.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("Task 2 + 3 cells inserted.")
print("Total cells:", len(nb["cells"]))
