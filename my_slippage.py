import numpy as np
import pandas as pd


def prepare_istar_features(
    df,
    lookback=30,
    min_periods=30,
    price_col="Close",
    volume_col="Volume",
):
    """
    Prepare daily liquidity and volatility features required by the I-Star model.

    The model uses:
    - Q: order size in shares
    - ADV: trailing average daily volume
    - sigma: trailing daily return volatility

    Features are estimated on daily data, shifted by one day, and then mapped
    back to each intraday row so the backtest does not use future information.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df.index.date)

    daily_volume = df.groupby("date")[volume_col].sum()
    daily_close = df.groupby("date")[price_col].last()
    daily_return = daily_close.pct_change()

    adv = daily_volume.shift(1).rolling(window=lookback, min_periods=min_periods).mean()
    sigma = daily_return.shift(1).rolling(window=lookback, min_periods=min_periods).std(ddof=1)

    df["adv_30d"] = df["date"].map(adv)
    df["sigma_30d"] = df["date"].map(sigma)
    return df


class IStarSlippageModel:
    """
    I-Star market-impact model based on Kissell and Malamut style parameters.

    Impact is modeled in basis points as:

        I*_bp = a1 * (Q / ADV) ** a2 * sigma ** a3

    where:
    - Q is order size in shares
    - ADV is trailing average daily volume
    - sigma is trailing daily return volatility (decimal form)
    """

    PARAMETER_SETS = {
        "all_data": {"a1": 708.0, "a2": 0.55, "a3": 0.71},
        "large_cap": {"a1": 687.0, "a2": 0.70, "a3": 0.72},
        "small_cap": {"a1": 702.0, "a2": 0.47, "a3": 0.69},
    }

    def __init__(
        self,
        parameter_set="large_cap",
        a1=None,
        a2=None,
        a3=None,
        adv_col="adv_30d",
        sigma_col="sigma_30d",
        strict=True,
    ):
        if parameter_set not in self.PARAMETER_SETS:
            raise ValueError(
                f"Unknown parameter_set '{parameter_set}'. "
                f"Expected one of {sorted(self.PARAMETER_SETS)}."
            )

        params = self.PARAMETER_SETS[parameter_set].copy()
        if a1 is not None:
            params["a1"] = float(a1)
        if a2 is not None:
            params["a2"] = float(a2)
        if a3 is not None:
            params["a3"] = float(a3)

        self.a1 = params["a1"]
        self.a2 = params["a2"]
        self.a3 = params["a3"]
        self.adv_col = adv_col
        self.sigma_col = sigma_col
        self.strict = strict

    def _require_feature(self, row, name):
        value = getattr(row, name, np.nan)
        if pd.isna(value) or value <= 0:
            if self.strict:
                raise ValueError(
                    f"Missing or invalid I-Star feature '{name}' on row {getattr(row, 'Index', 'unknown')}."
                )
            return np.nan
        return float(value)

    def impact_bps(self, quantity, row):
        quantity = abs(float(quantity))
        if quantity == 0:
            return 0.0

        adv = self._require_feature(row, self.adv_col)
        sigma = self._require_feature(row, self.sigma_col)
        if pd.isna(adv) or pd.isna(sigma):
            return 0.0

        participation = quantity / adv
        if participation <= 0:
            return 0.0

        return self.a1 * (participation ** self.a2) * (sigma ** self.a3)

    def slippage_cost(self, side, quantity, observed_price, row):
        impact_fraction = self.impact_bps(quantity, row) / 10000.0
        return abs(float(quantity)) * float(observed_price) * impact_fraction

    def fill_price(self, side, quantity, observed_price, row):
        impact_fraction = self.impact_bps(quantity, row) / 10000.0
        observed_price = float(observed_price)

        if side == "buy":
            return observed_price * (1 + impact_fraction)
        if side == "sell":
            return observed_price * (1 - impact_fraction)

        raise ValueError("side must be 'buy' or 'sell'")
