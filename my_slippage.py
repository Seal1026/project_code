import numpy as np
import pandas as pd


def prepare_hybrid_features(df, price_col="Close", abs_pct_ch_col="abs_pct_ch"):
    """
    Ensure the dataframe has the columns needed by HybridLinearCostModel.

    Required columns (must already exist or be computable):
    - abs_pct_ch : absolute intraday % change from day open (produced by calculate_momentum)

    If abs_pct_ch is missing, it is recomputed from scratch so this function
    can be used on any OHLCV dataframe.
    """
    df = df.copy()

    if abs_pct_ch_col not in df.columns:
        day_open = df.groupby(df.index.date)[price_col].transform("first")
        df[abs_pct_ch_col] = (df[price_col] / day_open - 1).abs()

    return df


class HybridLinearCostModel:
    """
    Hybrid Linear Transaction Cost Model.

    Total cost per trade:

        C_t = (Fee_fixed + Slippage_dynamic_t) * Q_t

    where:

        Slippage_dynamic_t = Slippage_base + lambda_ * |pct_ch_t| * P_t

    Parameters
    ----------
    fee_fixed : float
        Fixed brokerage commission per share (default $0.0035, typical retail broker).
    slippage_base : float
        Minimum execution friction per share (default $0.0001, ~0.5 bp on a $20 stock).
    lambda_ : float
        Sensitivity coefficient scaling slippage with instantaneous volatility
        (default 0.01 — 1 % of the current-bar absolute move added as slippage).
    abs_pct_ch_col : str
        Column name holding |pct_ch_t|, the per-bar absolute % change from day open.
        Produced automatically by calculate_momentum().
    """

    def __init__(
        self,
        fee_fixed=0.0035,
        slippage_base=0.0001,
        lambda_=0.01,
        abs_pct_ch_col="abs_pct_ch",
    ):
        self.fee_fixed = fee_fixed
        self.slippage_base = slippage_base
        self.lambda_ = lambda_
        self.abs_pct_ch_col = abs_pct_ch_col

    def _dynamic_slippage_per_share(self, observed_price, row):
        """
        Slippage_dynamic_t = Slippage_base + lambda * |pct_ch_t| * P_t
        """
        abs_pct_ch = getattr(row, self.abs_pct_ch_col, 0.0)
        if pd.isna(abs_pct_ch):
            abs_pct_ch = 0.0
        return self.slippage_base + self.lambda_ * float(abs_pct_ch) * float(observed_price)

    def cost_per_trade(self, quantity, observed_price, row):
        """
        Total cost of a trade:
            C_t = (fee_fixed + slippage_dynamic_t) * Q_t
        """
        q = abs(float(quantity))
        dyn_slip = self._dynamic_slippage_per_share(observed_price, row)
        return (self.fee_fixed + dyn_slip) * q

    def fill_price(self, side, quantity, observed_price, row):
        """
        Adjust the observed price by the per-share cost to obtain the effective fill price.

        Buys fill higher (cost added), sells fill lower (cost deducted).
        """
        dyn_slip = self._dynamic_slippage_per_share(observed_price, row)
        cost_per_share = self.fee_fixed + dyn_slip
        observed_price = float(observed_price)

        if side == "buy":
            return observed_price + cost_per_share
        if side == "sell":
            return observed_price - cost_per_share

        raise ValueError("side must be 'buy' or 'sell'")

    def slippage_cost(self, side, quantity, observed_price, row):
        """Alias matching the I-Star API for drop-in compatibility."""
        return self.cost_per_trade(quantity, observed_price, row)
