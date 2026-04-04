"""
Automated experiment runner for Strategy 4 optimization.

Runs ≥3 configurations of best_strategy(), logs metrics to experiment_log.md,
commits improvements to git (branch: workaround), and updates the notebook
with the winning configuration.

Usage:
    python run_experiments.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")           # non-interactive backend — no GUI windows needed
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# ── Ensure we are in the project root ─────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
os.makedirs("result", exist_ok=True)

import my_trade_algo as mta
import my_backtest as mbt
import my_metrics as mme
import my_slippage as msl
import my_plot as mpl

# ── Load data (once) ──────────────────────────────────────────────────────────
print("Loading data …", flush=True)
df_spy = pd.read_csv(
    "processed_data/prc_1_min_SPY_2008-2021.csv",
    encoding="utf-8-sig", index_col="Datetime", parse_dates=["Datetime"],
)
df_vix = pd.read_csv(
    "processed_data/prc_vix_daily_1990-2024.csv",
    encoding="utf-8-sig", index_col="Datetime", parse_dates=["Datetime"],
)
df_vix = df_vix.sort_index()
df_vix = df_vix[~df_vix.index.duplicated(keep="last")]

CASH = 100_000
LEVERAGE = 4
COST_FEE = 0.0035
COST_SLIP_BASE = 0.0001
COST_LAMBDA = 0.01

# ── Helper: run one backtest configuration ────────────────────────────────────
def run_strategy(df_prepared, sizing_fn, leverage, cost=False):
    """Return equity Series. Uses verbose=False so no print flood."""
    if cost:
        df_slip = msl.prepare_hybrid_features(df_prepared.copy())
        model = msl.HybridLinearCostModel(
            fee_fixed=COST_FEE,
            slippage_base=COST_SLIP_BASE,
            lambda_=COST_LAMBDA,
        )
        _, _, _, eq_arr, _ = mbt.backtest(
            df_slip, calc_share_function=sizing_fn, lvg=leverage,
            slippage_model=model, verbose=False,
        )
    else:
        _, _, _, eq_arr, _ = mbt.backtest(
            df_prepared, calc_share_function=sizing_fn, lvg=leverage,
            verbose=False,
        )
    return pd.Series(eq_arr, index=df_prepared.index)


def get_metrics(equity, bh_equity):
    return {
        "sharpe":       round(mme.sharpe(equity), 3),
        "cagr":         round(mme.irr_cagr(equity) * 100, 2),   # %
        "total_return": round(mme.total_return(equity) * 100, 2),
        "mdd":          round(mme.mdd(equity) * 100, 2),
        "vol":          round(mme.vol(equity) * 100, 2),
        "hit_ratio":    round(mme.hit_ratio(equity) * 100, 2),
    }


# ── Baselines ─────────────────────────────────────────────────────────────────
print("Running baselines …", flush=True)

df_base = mta.calculate_momentum(df_spy)

bh_equity = pd.Series(mta.buy_and_hold(CASH, df_base), index=df_base.index)
bh_m = get_metrics(bh_equity, bh_equity)
print(f"  B&H      Sharpe={bh_m['sharpe']:.2f}  CAGR={bh_m['cagr']:.1f}%")

# Strategy 3 baseline (same logic as notebook)
df2 = mta.cross_boundary_buy_signal_VWAP(mta.calculate_momentum(df_spy.copy()))
df3 = mta.daily_share_by_std(df2)
s3_equity = run_strategy(df3, mta.share_cal_std, LEVERAGE)
s3_m = get_metrics(s3_equity, bh_equity)
print(f"  S3       Sharpe={s3_m['sharpe']:.2f}  CAGR={s3_m['cagr']:.1f}%")

# ── Experiment configurations ─────────────────────────────────────────────────
EXPERIMENTS = [
    {
        "id": 1,
        "name": "ORB-only + long-only (no RSI, no VIX filter), share_cal_std L=4",
        "rationale": (
            "Remove all extra filters. long_only=True suits SPY's structural uptrend "
            "(2008-2021 bull market makes short signals net-negative). "
            "Isolates whether day-level ORB alone adds value over Strategy 3."
        ),
        "strategy_kwargs": dict(
            use_rsi=False,
            use_vix_filter=False,
            long_only=True,
        ),
        "sizing_fn": mta.share_cal_std,
        "leverage": LEVERAGE,
    },
    {
        "id": 2,
        "name": "ORB + relaxed RSI (40/60 thresholds) + long-only, share_cal_std L=4",
        "rationale": (
            "Re-introduce RSI but with wider 40/60 thresholds instead of strict 50/50. "
            "Allows more entries on days when RSI is near neutral. "
            "Long-only retained to avoid bull-market short losses."
        ),
        "strategy_kwargs": dict(
            use_rsi=True,
            rsi_long_thresh=40.0,
            rsi_short_thresh=60.0,
            use_vix_filter=False,
            long_only=True,
        ),
        "sizing_fn": mta.share_cal_std,
        "leverage": LEVERAGE,
    },
    {
        "id": 3,
        "name": "ORB + long-only + VIX filter (threshold=60), share_cal_std L=4",
        "rationale": (
            "Add a VIX filter but only for extreme panic (VIX>60, e.g. 2008 crash peak / "
            "March 2020). VIX>40 was too aggressive and killed profitable vol windows. "
            "Long-only retained. No RSI filter."
        ),
        "strategy_kwargs": dict(
            use_rsi=False,
            use_vix_filter=True,
            vix_threshold=60.0,
            long_only=True,
        ),
        "sizing_fn": mta.share_cal_std,
        "leverage": LEVERAGE,
    },
]

# ── Logging helpers ───────────────────────────────────────────────────────────
LOG_FILE = "experiment_log.md"

def _metrics_row(label, m):
    return (f"| {label} | {m['sharpe']:.2f} | {m['cagr']:.1f}% | "
            f"{m['total_return']:.1f}% | {m['mdd']:.1f}% | {m['vol']:.1f}% | {m['hit_ratio']:.1f}% |")

def append_log(exp_id, name, rationale, strategy_kwargs, sizing_name, leverage,
               no_cost_m, cost_m, bh_m, s3_m, prev_best_sharpe, analysis):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"\n## Experiment {exp_id} — {name}\n",
        f"**Timestamp**: {ts}\n\n",
        "### Parameters\n",
        f"- `use_rsi`: {strategy_kwargs.get('use_rsi', True)}"
        f"  |  `rsi_long_thresh/rsi_short_thresh`: "
        f"{strategy_kwargs.get('rsi_long_thresh','—')}/{strategy_kwargs.get('rsi_short_thresh','—')}\n",
        f"- `use_vix_filter`: {strategy_kwargs.get('use_vix_filter', True)}"
        f"  |  `vix_threshold`: {strategy_kwargs.get('vix_threshold', 40.0)}\n",
        f"- `long_only`: {strategy_kwargs.get('long_only', False)}"
        f"  |  sizing: `{sizing_name}`  |  leverage: {leverage}\n",
        f"- Cost model: fee=${COST_FEE}, slip_base=${COST_SLIP_BASE}, λ={COST_LAMBDA}\n",
        "\n### Results vs Baselines\n",
        "| Strategy | Sharpe | CAGR | Total Return | MDD | Vol | Hit Ratio |\n",
        "|---|---|---|---|---|---|---|\n",
        _metrics_row("SPY Buy & Hold", bh_m) + "\n",
        _metrics_row("Strategy 3 (baseline)", s3_m) + "\n",
        _metrics_row(f"Exp {exp_id} (no cost)", no_cost_m) + "\n",
        _metrics_row(f"Exp {exp_id} + Cost Model", cost_m) + "\n",
        "\n### Analysis\n",
        analysis + "\n",
        f"\n**Rationale for this experiment**: {rationale}\n",
    ]
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.writelines(lines)


def git_commit(msg, files):
    subprocess.run(["git", "add"] + files, check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)


def save_equity_chart(equity_dict, bh_equity, timestamp, name):
    """Save equity curves comparison chart."""
    fig, ax = plt.subplots(figsize=(14, 5))
    palette = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#d62728", "#17becf"]
    for (label, eq), color in zip(equity_dict.items(), palette):
        daily = eq.groupby(eq.index.date).last()
        daily.index = pd.to_datetime(daily.index)
        ax.plot(daily.index, daily.values, label=label, color=color, linewidth=1.4)
    locator = mdates.AutoDateLocator(maxticks=8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.set_title(f"Equity Curves — {name}", fontsize=12, fontweight="bold")
    ax.set_ylabel("Portfolio Value ($)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = f"result/exp{timestamp}_{name.replace(' ','_')[:30]}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {path}")
    return path


# ── Main experiment loop ───────────────────────────────────────────────────────
# Initialise log file header
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("# Experiment Log — Strategy 4 Optimization\n\n")
        f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Baselines\n\n")
        f.write("| Strategy | Sharpe | CAGR | Total Return | MDD | Vol | Hit Ratio |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        f.write(_metrics_row("SPY Buy & Hold", bh_m) + "\n")
        f.write(_metrics_row("Strategy 3", s3_m) + "\n\n")
        f.write("---\n")

best_no_cost_sharpe = s3_m["sharpe"]
best_cost_sharpe    = -999.0
best_exp_id         = None
best_kwargs         = None
best_sizing_fn      = None

STOP_REACHED = False

for exp in EXPERIMENTS:
    if STOP_REACHED:
        break

    eid         = exp["id"]
    name        = exp["name"]
    rationale   = exp["rationale"]
    skw         = exp["strategy_kwargs"]
    sizing_fn   = exp["sizing_fn"]
    leverage    = exp["leverage"]
    sizing_name = sizing_fn.__name__

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*60}", flush=True)
    print(f"Experiment {eid}: {name}", flush=True)
    print(f"{'='*60}", flush=True)

    # Build signal dataframe
    print("  Building signals …", flush=True)
    df_exp = mta.best_strategy(df_spy.copy(), df_vix=df_vix, **skw)

    # Run without cost
    print("  Backtesting (no cost) …", flush=True)
    nc_equity = run_strategy(df_exp, sizing_fn, leverage, cost=False)
    nc_m = get_metrics(nc_equity, bh_equity)
    print(f"  No-cost  → Sharpe={nc_m['sharpe']:.2f}  CAGR={nc_m['cagr']:.1f}%  MDD={nc_m['mdd']:.1f}%")

    # Run with cost model
    print("  Backtesting (+ cost model) …", flush=True)
    c_equity = run_strategy(df_exp, sizing_fn, leverage, cost=True)
    c_m = get_metrics(c_equity, bh_equity)
    print(f"  With cost → Sharpe={c_m['sharpe']:.2f}  CAGR={c_m['cagr']:.1f}%  MDD={c_m['mdd']:.1f}%")

    # Save chart
    chart_data = {
        "SPY Buy & Hold": bh_equity,
        "Strategy 3":     s3_equity,
        f"Exp {eid} (no cost)": nc_equity,
        f"Exp {eid} + Cost":    c_equity,
    }
    save_equity_chart(chart_data, bh_equity, ts, f"Exp{eid}")

    # Build analysis text
    vs_s3  = nc_m['sharpe'] - s3_m['sharpe']
    vs_bh  = c_m['sharpe']  - bh_m['sharpe']
    vs_s3_str = f"+{vs_s3:.2f}" if vs_s3 >= 0 else f"{vs_s3:.2f}"
    vs_bh_str = f"+{vs_bh:.2f}" if vs_bh >= 0 else f"{vs_bh:.2f}"
    beat_bh = c_m["sharpe"] > bh_m["sharpe"] and c_m["cagr"] > bh_m["cagr"]

    analysis = (
        f"- **vs Strategy 3** (no cost): Sharpe {vs_s3_str} "
        f"({'IMPROVED' if vs_s3 >= 0 else 'WORSE'})\n"
        f"- **vs B&H after cost**: Sharpe {vs_bh_str} "
        f"({'BEATS B&H ✓' if beat_bh else 'below B&H ✗'})\n"
    )
    if beat_bh:
        analysis += "- **STOP CONDITION MET**: Strategy 4 + Cost Model beats SPY Buy & Hold.\n"
    if eid > 1:
        analysis += f"- vs previous best no-cost Sharpe ({best_no_cost_sharpe:.2f}): "
        diff = nc_m['sharpe'] - best_no_cost_sharpe
        analysis += f"{'IMPROVED' if diff >= 0 else 'WORSE'} ({diff:+.2f})\n"

    append_log(
        eid, name, rationale, skw, sizing_name, leverage,
        nc_m, c_m, bh_m, s3_m, best_no_cost_sharpe, analysis,
    )

    # Decide whether to commit
    improved = nc_m["sharpe"] > best_no_cost_sharpe - 0.01  # commit if within 0.01 of best
    if improved or beat_bh:
        best_no_cost_sharpe = max(best_no_cost_sharpe, nc_m["sharpe"])
        best_cost_sharpe    = c_m["sharpe"]
        best_exp_id         = eid
        best_kwargs         = skw
        best_sizing_fn      = sizing_fn

        commit_msg = (
            f"Exp {eid}: {name[:60]} | "
            f"Sharpe={nc_m['sharpe']:.2f} CAGR={nc_m['cagr']:.1f}% "
            f"(+cost: Sharpe={c_m['sharpe']:.2f})"
        )
        files_to_commit = [
            "my_backtest.py", "my_trade_algo.py", "my_plot.py",
            "my_slippage.py", "momentum.ipynb",
            "run_experiments.py", "experiment_log.md",
        ]
        print(f"\n  Committing: {commit_msg[:80]}")
        git_commit(commit_msg, files_to_commit)
    else:
        print(f"  No improvement over best Sharpe={best_no_cost_sharpe:.2f} — skipping commit.")

    if beat_bh:
        print(f"\n*** STOP CONDITION MET at Experiment {eid}: cost-model Sharpe > B&H ***")
        STOP_REACHED = True

# ── Update notebook with best experiment config ───────────────────────────────
print(f"\n{'='*60}")
print(f"Best experiment: Exp {best_exp_id}  Sharpe(no cost)={best_no_cost_sharpe:.2f}")
print("Updating notebook Cell 17 with best configuration …")

with open("momentum.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

# Build the best_strategy kwargs string for the notebook
kw = best_kwargs or {}
kw_lines = []
if "use_rsi" in kw:
    kw_lines.append(f"    use_rsi={kw['use_rsi']},\n")
if "rsi_long_thresh" in kw:
    kw_lines.append(f"    rsi_long_thresh={kw['rsi_long_thresh']},\n")
if "rsi_short_thresh" in kw:
    kw_lines.append(f"    rsi_short_thresh={kw['rsi_short_thresh']},\n")
if "use_vix_filter" in kw:
    kw_lines.append(f"    use_vix_filter={kw['use_vix_filter']},\n")
if "vix_threshold" in kw:
    kw_lines.append(f"    vix_threshold={kw['vix_threshold']},\n")
if "long_only" in kw:
    kw_lines.append(f"    long_only={kw['long_only']},\n")
kw_str = "".join(kw_lines)

sizing_fn_name = (best_sizing_fn or mta.share_cal_std).__name__

nb["cells"][17]["source"] = [
    f"# Best config from run_experiments.py — Experiment {best_exp_id}\n",
    f"# Sharpe (no cost) = {best_no_cost_sharpe:.2f}  |  Sharpe (with cost) = {best_cost_sharpe:.2f}\n",
    "LEVERAGE_BEST = 4\n",
    "\n",
    "df_best = mta.best_strategy(\n",
    "    df, df_vix=df_vix,\n",
    *kw_lines,
    ")\n",
    "realized_pnl_arr4, unrealized_pnl_arr4, cash_arr4, equity_arr4, df_best = mbt.backtest(\n",
    f"    df_best, calc_share_function=mta.{sizing_fn_name}, lvg=LEVERAGE_BEST, verbose=False,\n",
    ")\n",
    "equity4 = pd.Series(equity_arr4, index=df.index)\n",
]

# Cell 19: cost model cell — update sizing fn to match best
nb["cells"][19]["source"] = [
    "importlib.reload(msl)\n",
    "importlib.reload(mbt)\n",
    "\n",
    "df_slip = msl.prepare_hybrid_features(df_best.copy())\n",
    "\n",
    "cost_model = msl.HybridLinearCostModel(\n",
    f"    fee_fixed={COST_FEE},\n",
    f"    slippage_base={COST_SLIP_BASE},\n",
    f"    lambda_={COST_LAMBDA},\n",
    ")\n",
    "\n",
    "realized_pnl_arr5, unrealized_pnl_arr5, cash_arr5, equity_arr5, df_slip = mbt.backtest(\n",
    "    df_slip,\n",
    f"    calc_share_function=mta.{sizing_fn_name},\n",
    "    lvg=LEVERAGE_BEST,\n",
    "    slippage_model=cost_model,\n",
    "    verbose=False,\n",
    ")\n",
    "equity5 = pd.Series(equity_arr5, index=df.index)\n",
]

# Also add verbose=False to other backtest cells to suppress output in notebook
for cell_idx in [9, 11, 13, 15]:
    src = "".join(nb["cells"][cell_idx]["source"])
    if "verbose=False" not in src and "mbt.backtest(" in src:
        nb["cells"][cell_idx]["source"] = [
            line.replace("mbt.backtest(", "mbt.backtest(", 1) for line in nb["cells"][cell_idx]["source"]
        ]
        # Insert verbose=False as the last argument
        new_src = []
        for line in nb["cells"][cell_idx]["source"]:
            if line.strip().startswith("realized_pnl") and "mbt.backtest(" in line:
                # single-line backtest call
                line = line.replace("mbt.backtest(", "mbt.backtest(").rstrip()
                if line.endswith(")"):
                    line = line[:-1] + ", verbose=False)\n"
                new_src.append(line)
            else:
                new_src.append(line)
        nb["cells"][cell_idx]["source"] = new_src

with open("momentum.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("Notebook updated with best experiment configuration.")

# ── Try to run notebook via nbconvert ─────────────────────────────────────────
print("\nAttempting to run notebook via jupyter nbconvert …")
result = subprocess.run(
    [sys.executable, "-m", "jupyter", "nbconvert",
     "--to", "notebook", "--execute", "--inplace",
     "--ExecutePreprocessor.timeout=1200",
     "momentum.ipynb"],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("Notebook executed successfully.")
else:
    print(f"nbconvert failed (returncode={result.returncode}).")
    print("stderr:", result.stderr[:500])
    print("Notebook code has been updated — please re-run cells manually in Jupyter.")

# ── Final commit ───────────────────────────────────────────────────────────────
print("\nFinal commit with notebook update …")
final_msg = (
    f"Final: notebook updated with Exp {best_exp_id} best config | "
    f"Sharpe={best_no_cost_sharpe:.2f} CAGR — see experiment_log.md"
)
git_commit(final_msg, [
    "momentum.ipynb", "run_experiments.py", "experiment_log.md",
])

print("\nDone. Check experiment_log.md for full results.")
print(f"Best experiment: #{best_exp_id}  |  No-cost Sharpe={best_no_cost_sharpe:.2f}"
      f"  |  With-cost Sharpe={best_cost_sharpe:.2f}"
      f"  |  B&H Sharpe={bh_m['sharpe']:.2f}")
