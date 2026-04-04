# Plan: Automated Experiment Loop for Strategy 4 Optimization

## Context

Strategy 4 (Best) underperforms Strategy 3 on the equity curve. Root cause analysis:

1. **`share_cal_vix_regime` over-reduces position sizes**: VIX > 20 → 80%, VIX > 25 → 60%, VIX > 35 → 30%. SPY's 2008-2021 history averages VIX ~18-22, meaning positions are *always* reduced. This kills returns during the same high-vol windows where momentum is strongest.

2. **Strict filter conjunction kills trade frequency**: ORB AND daily RSI AND VIX < 40 — all must fire simultaneously at a :00/:30 bar. Daily RSI shifted 1 day further delays signal confirmation.

3. **Cost model amplifies the problem**: With reduced position sizes from VIX scaling, the *fixed* $0.0035/share commission takes a proportionally larger bite.

4. **Shorts hurt in a bull market**: Strategy 3 (and 4) takes shorts in a SPY 2008-2021 dataset that trended strongly upward after 2009. Short signals systematically lose during the 12-year bull run.

**Goal**: Run ≥ 3 optimization experiments, stop when `Strategy 4 + Cost Model` beats `SPY Buy & Hold`. Log every run in `experiment_log.md`. Git commit each improvement on branch `workaround`.

---

## Files to Modify / Create

| File | Change |
|------|--------|
| `my_backtest.py` | Add `verbose=False` param — wrap all `_log_*` and `print` calls with `if verbose:` |
| `my_trade_algo.py` | Add params to `best_strategy()`: `use_rsi`, `rsi_long_thresh`, `rsi_short_thresh`, `use_vix_filter`, `vix_threshold`, `long_only` |
| `momentum.ipynb` | Task 0: add `save_show()` helper + replace all `plt.show()` with `save_show('name')`; update Strategy 4 cells with best experiment config |
| `run_experiments.py` | **New**: automated experiment runner script |
| `experiment_log.md` | **New**: results log, appended after each experiment |
| `result/` | Directory (ensure exists) |

---

## Step-by-Step Implementation

### Step 1 – `my_backtest.py`: Add `verbose=False`

Change `backtest()` signature to:
```python
def backtest(df, calc_share_function=None, lvg=None, enter_opposite=False,
             slippage_model=None, verbose=False):
```
Pass `verbose` down to all `_log_*` helpers. Wrap every `print(...)` and `_log_*(...)` call with `if verbose:`.

### Step 2 – `my_trade_algo.py`: Parameterize `best_strategy()`

New signature:
```python
def best_strategy(df, df_vix=None, orb_minutes=30,
                  use_rsi=True, rsi_long_thresh=50.0, rsi_short_thresh=50.0,
                  use_vix_filter=True, vix_threshold=40.0,
                  long_only=False):
```

Logic changes:
- `buy` signal: add `& (df["daily_rsi"] > rsi_long_thresh)` only if `use_rsi`
- `sell` signal: add `& (df["daily_rsi"] < rsi_short_thresh)` only if `use_rsi`
- `vix_ok`: filter by `< vix_threshold` only if `use_vix_filter`; else `Series(True)`
- If `long_only=True`: set `df["sell"] = False` after signal calculation
- Keep day-level ORB and VWAP stops in all cases

### Step 3 – `momentum.ipynb`: Task 0 – Plot Saving

In Cell 0, add after imports:
```python
import os
from datetime import datetime
os.makedirs('result', exist_ok=True)
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')

def save_show(name):
    """Save current figure then display it."""
    plt.savefig(f'result/{name}_{TIMESTAMP}.png', dpi=150, bbox_inches='tight')
    plt.show()
```

Replace every `plt.show()` in plot cells with `save_show('<descriptive_name>')`:
- equity curves → `save_show('equity_curves')`
- drawdown → `save_show('drawdown')`
- rolling sharpe → `save_show('rolling_sharpe')`
- monthly returns → `save_show('monthly_returns')`
- vix scatter → `save_show('vix_scatter')`
- vix bin report → `save_show('vix_bin')`
- annual heatmap → `save_show('annual_heatmap')`

### Step 4 – `run_experiments.py`: Automated Experiment Runner

Structure:
```python
# 1. Suppress stdout from backtest via verbose=False
# 2. Load data ONCE (df_spy, df_vix)
# 3. Run baselines: B&H, Strategy 3
# 4. Define 3 experiments as dicts of best_strategy() kwargs + sizing config
# 5. For each experiment:
#    a. Build df_exp via mta.best_strategy(df, df_vix, **exp_kwargs)
#    b. Run mbt.backtest(df_exp, sizing_fn, leverage, verbose=False)
#    c. Compute metrics (sharpe, cagr, mdd, hit_ratio, total_return)
#    d. Run same config + HybridLinearCostModel
#    e. Append to experiment_log.md
#    f. If improves on S3 Sharpe: git add + git commit
#    g. If cost-model Sharpe > B&H Sharpe: stop early
# 6. After all experiments, update notebook Cell 17 & 19 with best config
# 7. Run notebook via: python -m jupyter nbconvert --execute --inplace momentum.ipynb
#    (or skip nbconvert if unavailable, print instructions)
```

### Step 5 – Experiment Configurations

| Exp | use_rsi | use_vix_filter | long_only | sizing_fn | leverage | Rationale |
|-----|---------|---------------|-----------|-----------|----------|-----------|
| E1 | False | False | **True** | share_cal_std | 4 | Remove all filters; long-only suits SPY uptrend |
| E2 | **True** (40/60) | False | True | share_cal_std | 4 | Relaxed RSI thresholds allow more entries than 50/50 |
| E3 | False | **True** (vix<60) | True | share_cal_std | 4 | Extreme-only VIX cutoff (replaces 40 with 60) |

Stop condition: If any experiment's cost-model Sharpe > B&H Sharpe, stop and commit.

### Step 6 – `experiment_log.md` Format (append each run)

```markdown
## Experiment N – <name> – <timestamp>

### Parameters
- use_rsi: ...  rsi_long_thresh / rsi_short_thresh: ...
- use_vix_filter: ...  vix_threshold: ...
- long_only: ...  sizing: ...  leverage: ...

### Results vs Baselines
| Strategy | Sharpe | CAGR | MDD | Hit Ratio |
|---|---|---|---|---|
| SPY B&H | ... | ... | ... | ... |
| Strategy 3 | ... | ... | ... | ... |
| This Exp (no cost) | ... | ... | ... | ... |
| This Exp + Cost | ... | ... | ... | ... |

### Analysis
- vs S3: [better/worse, by how much]
- vs B&H after cost: [better/worse]
- Reason for change: ...
- Next step: ...
```

### Step 7 – Git Commit Policy

- Only commit if Sharpe improves vs Strategy 3 OR improves vs previous experiment
- Branch: `workaround` (current branch, no switching)
- Message: `Exp {N}: {description} | Sharpe={X:.2f} CAGR={X:.1f}%`
- Files to stage: `my_trade_algo.py`, `my_backtest.py`, `momentum.ipynb`, `run_experiments.py`, `experiment_log.md`

---

## Verification

1. After `run_experiments.py` completes, check `experiment_log.md` has ≥3 entries
2. Check `result/` has PNG files with timestamps
3. Check `git log --oneline` shows ≥1 new commit on `workaround`
4. Check final notebook Cell 17 parameters match the best experiment
5. Confirm `Strategy 4 + Cost Model` Sharpe and CAGR are logged in the final experiment entry
