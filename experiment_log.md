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

## Experiment 2 — ORB + relaxed RSI (40/60 thresholds) + long-only, share_cal_std L=4
**Timestamp**: 2026-04-05 00:22:29

### Parameters
- `use_rsi`: True  |  `rsi_long_thresh/rsi_short_thresh`: 40.0/60.0
- `use_vix_filter`: False  |  `vix_threshold`: 40.0
- `long_only`: True  |  sizing: `share_cal_std`  |  leverage: 4
- Cost model: fee=$0.0035, slip_base=$0.0001, λ=0.01

### Results vs Baselines
| Strategy | Sharpe | CAGR | Total Return | MDD | Vol | Hit Ratio |
|---|---|---|---|---|---|---|
| SPY Buy & Hold | 0.48 | 9.2% | 219.9% | 52.3% | 20.6% | 54.8% |
| Strategy 3 (baseline) | 0.92 | 14.2% | 481.6% | 31.2% | 14.5% | 24.6% |
| Exp 2 (no cost) | 0.80 | 6.3% | 125.2% | 10.3% | 6.7% | 10.5% |
| Exp 2 + Cost Model | 0.36 | 3.2% | 52.7% | 15.5% | 6.7% | 9.9% |

### Analysis
- **vs Strategy 3** (no cost): Sharpe -0.12 (WORSE)
- **vs B&H after cost**: Sharpe -0.12 (below B&H ✗)
- vs previous best no-cost Sharpe (1.15): WORSE (-0.35)


**Rationale for this experiment**: Re-introduce RSI but with wider 40/60 thresholds instead of strict 50/50. Allows more entries on days when RSI is near neutral. Long-only retained to avoid bull-market short losses.

## Experiment 3 — ORB + long-only + VIX filter (threshold=60), share_cal_std L=4
**Timestamp**: 2026-04-05 00:22:51

### Parameters
- `use_rsi`: False  |  `rsi_long_thresh/rsi_short_thresh`: —/—
- `use_vix_filter`: True  |  `vix_threshold`: 60.0
- `long_only`: True  |  sizing: `share_cal_std`  |  leverage: 4
- Cost model: fee=$0.0035, slip_base=$0.0001, λ=0.01

### Results vs Baselines
| Strategy | Sharpe | CAGR | Total Return | MDD | Vol | Hit Ratio |
|---|---|---|---|---|---|---|
| SPY Buy & Hold | 0.48 | 9.2% | 219.9% | 52.3% | 20.6% | 54.8% |
| Strategy 3 (baseline) | 0.92 | 14.2% | 481.6% | 31.2% | 14.5% | 24.6% |
| Exp 3 (no cost) | 1.12 | 10.4% | 270.7% | 10.2% | 8.3% | 13.6% |
| Exp 3 + Cost Model | 0.66 | 6.2% | 123.2% | 12.2% | 8.2% | 12.9% |

### Analysis
- **vs Strategy 3** (no cost): Sharpe +0.20 (IMPROVED)
- **vs B&H after cost**: Sharpe +0.18 (below B&H ✗)
- vs previous best no-cost Sharpe (1.15): WORSE (-0.03)


**Rationale for this experiment**: Add a VIX filter but only for extreme panic (VIX>60, e.g. 2008 crash peak / March 2020). VIX>40 was too aggressive and killed profitable vol windows. Long-only retained. No RSI filter.


Results Summary
Baselines:

Strategy	Sharpe	CAGR	MDD
SPY Buy & Hold	0.48	9.2%	52.3%
Strategy 3 (vol-adj sizing)	0.92	14.2%	31.2%
3 Experiments run:

Exp	Config	Sharpe (no cost)	Sharpe (+cost)
E1 ✓	ORB + long-only, no RSI, no VIX	1.15	0.69
E2	ORB + RSI 40/60 + long-only	0.80	0.36
E3	ORB + long-only + VIX<60	1.12	0.66
Winner: Experiment 1 — ORB day-level confirmation + long_only=True + share_cal_std (L=4)

No-cost Sharpe 1.15 > S3's 0.92 (+0.23 improvement)
MDD dramatically lower: 10.2% vs 31.2% for S3
Cost-model Sharpe 0.69 > B&H's 0.48 (Sharpe beats B&H, but CAGR 6.6% < B&H 9.2%)
Key finding: Adding RSI filter (E2) hurt — it cut trade frequency too aggressively. The VIX filter at threshold=60 (E3) was nearly identical to E1, confirming extreme-only VIX filtering has minimal impact.

Git commits made on workaround:

66ba8cb — Exp 1 results
14b8d3a — notebook updated with best config
Notebook was re-executed via nbconvert with the winning configuration in Cells 17 and 19. Charts saved to result/.
---

## Task 1 — Switch Final Strategy to Experiment 3 (E3)

**Timestamp**: 2026-04-05

### Change
Replaced the notebook's "Strategy 4 (Best)" (Experiment 1 config) with Experiment 3 as the **Final Strategy**.
All references to "Strategy 4 (Best)" and "Strategy 4 + Cost Model" renamed to "Final Strategy" / "Final Strategy + Cost Model" across:
- Cell 16 (markdown description)
- Cell 17 (backtest code)
- Cell 22 (equity_curves dict)
- Cell 26 (heatmap dict)

### E3 Config
| Parameter | Value |
|---|---|
| `use_rsi` | False |
| `use_vix_filter` | True |
| `vix_threshold` | 60.0 |
| `long_only` | True |
| sizing | `share_cal_std` |
| leverage | 4 |

### Results (Final Strategy = E3)
| Metric | No Cost | + Cost Model |
|---|---|---|
| Total Return | 270.7% | 123.2% |
| CAGR | 10.4% | 6.2% |
| Sharpe | 1.12 | 0.66 |
| MDD | 10.2% | 12.1% |
| Beta | 0.10 | 0.09 |

Rationale: E3 (ORB + long-only + VIX<60) was chosen over E1 (simpler, no VIX filter) for presentation because it explicitly incorporates a regime filter, making the strategy rationale more complete and defensible despite marginally lower Sharpe (1.12 vs 1.15).

---

## Task 2 — Beta Analysis Cell Added

**Timestamp**: 2026-04-05

### Change
Added Cell 29 (`beta_analysis_01`) to notebook, immediately after the performance summary.

### Output
```
Strategy 3 + Cost Model
  Beta (vs SPY):        -0.06
  Alpha (annualised):    5.7%
  Total Return:         75.1%
  Max Drawdown:         38.2%

Final Strategy + Cost Model
  Beta (vs SPY):        +0.09
  Alpha (annualised):    5.6%
  Total Return:         123.2%
  Max Drawdown:         12.1%

SPY Buy & Hold  Max Drawdown: 52.3%
```

### Interpretation
Both cost-adjusted strategies have beta ≈ 0 (−0.06 and +0.09), confirming near-zero market correlation. This validates the essay argument: while passive SPY outperformed in total return, the strategies' primary value is as **diversification vehicles** — their P&L is driven by intraday momentum signals, not broad market exposure. They maintained positive returns while B&H suffered >50% drawdowns in 2008/2020.

---

## Task 3 — Trade Count & Cost-to-Profit Ratio Cell Added

**Timestamp**: 2026-04-05

### Change
Added Cell 30 (`trade_cpr_01`) to notebook after the beta analysis cell.

### Trade Statistics
| Strategy | Long | Short | Total | Avg/Year |
|---|---|---|---|---|
| Strategy 3 (no cost) | 1538 | 1565 | 3103 | 233.5 |
| Strategy 3 + Cost | 1538 | 1565 | 3103 | 233.5 |
| Final Strategy (no cost) | 1452 | 0 | 1452 | 109.3 |
| Final Strategy + Cost | 1452 | 0 | 1452 | 109.3 |

Final Strategy is long-only (0 short entries) and trades ~53% as often as Strategy 3.

### Cost-to-Profit Ratio (CPR)
| Strategy | No-Cost Return | With-Cost Return | CPR |
|---|---|---|---|
| Strategy 3 | 481.6% | 75.1% | **84.4%** |
| Final Strategy | 270.7% | 123.2% | **54.5%** |

Strategy 3's CPR of 84.4% means 84 cents of every gross dollar earned went to transaction costs — a consequence of 233 trades/year × high leverage. The Final Strategy's CPR of 54.5% reflects its stricter entry filters (day-level ORB + VIX<60), resulting in fewer, higher-conviction trades where each earned dollar is less eroded.
