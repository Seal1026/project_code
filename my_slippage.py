from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IStarParameters:
    a1: float
    a2: float
    a3: float


ISTAR_PARAMETER_SETS = {
    "all_data": IStarParameters(a1=708.0, a2=0.55, a3=0.71),
    "large_cap": IStarParameters(a1=687.0, a2=0.70, a3=0.72),
    "small_cap": IStarParameters(a1=702.0, a2=0.47, a3=0.69),
}


def prepare_istar_features(
    df,
    lookback=30,
    min_periods=30,
    volume_col="Volume",
    close_col="Close",
):
    """
    Prepare the inputs required by the I-Star market impact model.

    The model uses:
    - Q: shares to transact
    - ADV: rolling average daily volume in shares
    - sigma: rolling daily return volatility

    Features are shifted by one trading day so the backtest does not use
    same-day future information.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df.index.date)

    daily_volume = df.groupby("date")[volume_col].sum()
    daily_close = df.groupby("date")[close_col].last()
    daily_returns = daily_close.pct_change()

    adv_30d = daily_volume.shift(1).rolling(window=lookback, min_periods=min_periods).mean()
    sigma_30d = daily_returns.shift(1).rolling(window=lookback, min_periods=min_periods).std(ddof=1)

    df["adv_30d"] = df["date"].map(adv_30d)
    df["sigma_30d"] = df["date"].map(sigma_30d)
    return df


class IStarSlippageModel:
    """
    I-Star market impact model.

    Impact in basis points:
        I_bp = a1 * (Q / ADV)^a2 * sigma^a3

    where:
    - Q is order size in shares
    - ADV is the 30-day average daily volume in shares
    - sigma is 30-day realized daily return volatility

    The model is applied as one-way adverse execution impact:
    - buys execute above the observed price
    - sells execute below the observed price
    """

    def __init__(
        self,
        parameter_set="large_cap",
        adv_column="adv_30d",
        sigma_column="sigma_30d",
        strict=True,
        max_participation=1.0,
    ):
        if isinstance(parameter_set, str):
            if parameter_set not in ISTAR_PARAMETER_SETS:
                raise ValueError(f"Unknown I-Star parameter set: {parameter_set}")
            self.params = ISTAR_PARAMETER_SETS[parameter_set]
            self.parameter_set = parameter_set
        else:
            self.params = parameter_set
            self.parameter_set = "custom"

        self.adv_column = adv_column
        self.sigma_column = sigma_column
        self.strict = strict
        self.max_participation = max_participation

    def _extract_inputs(self, row):
        adv = getattr(row, self.adv_column, np.nan)
        sigma = getattr(row, self.sigma_column, np.nan)

        if pd.isna(adv) or adv <= 0 or pd.isna(sigma) or sigma <= 0:
            if self.strict:
                raise ValueError(
                    f"Missing or invalid I-Star inputs on {row.Index}: "
                    f"{self.adv_column}={adv}, {self.sigma_column}={sigma}. "
                    "Run prepare_istar_features(...) before backtesting or disable strict mode."
                )
            return np.nan, np.nan

        return float(adv), float(sigma)

    def impact_bps(self, quantity, row):
        quantity = abs(float(quantity))
        if quantity == 0:
            return 0.0

        adv, sigma = self._extract_inputs(row)
        if np.isnan(adv) or np.isnan(sigma):
            return 0.0

        participation = min(quantity / adv, self.max_participation)
        impact_bps = self.params.a1 * (participation ** self.params.a2) * (sigma ** self.params.a3)
        return float(impact_bps)

    def impact_fraction(self, quantity, row):
        return self.impact_bps(quantity, row) / 10000.0

    def fill_price(self, side, quantity, observed_price, row):
        impact = self.impact_fraction(quantity, row)
        if side == "buy":
            return observed_price * (1.0 + impact)
        if side == "sell":
            return observed_price * (1.0 - impact)
        raise ValueError(f"Unknown side: {side}")

    def slippage_cost(self, side, quantity, observed_price, row):
        executed_price = self.fill_price(side, quantity, observed_price, row)
        return abs(quantity) * abs(executed_price - observed_price)
