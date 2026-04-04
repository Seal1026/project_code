# Experiment Log — Strategy 4 Optimization

Started: 2026-04-05 00:21:43

## Baselines

| Strategy | Sharpe | CAGR | Total Return | MDD | Vol | Hit Ratio |
|---|---|---|---|---|---|---|
| SPY Buy & Hold | 0.48 | 9.2% | 219.9% | 52.3% | 20.6% | 54.8% |
| Strategy 3 | 0.92 | 14.2% | 481.6% | 31.2% | 14.5% | 24.6% |

---

## Experiment 1 — ORB-only + long-only (no RSI, no VIX filter), share_cal_std L=4
**Timestamp**: 2026-04-05 00:22:06

### Parameters
- `use_rsi`: False  |  `rsi_long_thresh/rsi_short_thresh`: —/—
- `use_vix_filter`: False  |  `vix_threshold`: 40.0
- `long_only`: True  |  sizing: `share_cal_std`  |  leverage: 4
- Cost model: fee=$0.0035, slip_base=$0.0001, λ=0.01

### Results vs Baselines
| Strategy | Sharpe | CAGR | Total Return | MDD | Vol | Hit Ratio |
|---|---|---|---|---|---|---|
| SPY Buy & Hold | 0.48 | 9.2% | 219.9% | 52.3% | 20.6% | 54.8% |
| Strategy 3 (baseline) | 0.92 | 14.2% | 481.6% | 31.2% | 14.5% | 24.6% |
| Exp 1 (no cost) | 1.15 | 10.8% | 288.5% | 10.2% | 8.3% | 13.9% |
| Exp 1 + Cost Model | 0.69 | 6.6% | 132.7% | 12.2% | 8.3% | 13.1% |

### Analysis
- **vs Strategy 3** (no cost): Sharpe +0.23 (IMPROVED)
- **vs B&H after cost**: Sharpe +0.21 (below B&H ✗)


**Rationale for this experiment**: Remove all extra filters. long_only=True suits SPY's structural uptrend (2008-2021 bull market makes short signals net-negative). Isolates whether day-level ORB alone adds value over Strategy 3.
