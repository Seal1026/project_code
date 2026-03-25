#交易算法函数
import pandas as pd
import numpy as np
from IPython.display import display

import my_slippage as msl


def calculate_orb(df, orb_minutes=30):
    df = df.copy()
    df["date"] = pd.to_datetime(df.index.date)

    # 每日的开盘时间
    day_open_time = df.groupby("date").apply(lambda x: x.index[0], include_groups=False).rename("day_open_time")
    df = df.join(day_open_time, on="date")

    # 开盘范围 opening range window
    df["in_orb_window"] = (
        (df.index >= df["day_open_time"]) &
        (df.index < df["day_open_time"] + pd.Timedelta(minutes=orb_minutes))
    )

    # 计算开盘范围的最高价和最低价
    orb_levels = (
        df[df["in_orb_window"]]
        .groupby("date")
        .agg(orb_high=("High", "max"), orb_low=("Low", "min"))
    )

    df = df.join(orb_levels, on="date")

    # Breakout / breakdown signals — only valid AFTER the ORB window has closed
    df["orb_breakout"] = (~df["in_orb_window"]) & (df["Close"] > df["orb_high"])  # 做多信号
    df["orb_breakdown"] = (~df["in_orb_window"]) & (df["Close"] < df["orb_low"])  # 做空信号

    # Clean up helper column
    df.drop(columns=["day_open_time"], inplace=True)

    return df


def trade_time(minute):
    # TODO: Update and change back.
    return (minute == 30) | (minute == 0)
    # return minute%15==0


# base momentum strategy
def calculate_momentum(df, rolling_window=14, band_multiplier=1.0):
    df = df.copy()

    # 以每天的开盘价为基准，计算每分钟收盘相对开盘的绝对百分比变化
    df["day_open"] = df.groupby(df.index.date)["Open"].transform(lambda x: x.iloc[0])
    df["abs_pct_ch"] = np.abs(df["Close"] / df["day_open"] - 1)

    # 以昨天的收盘价为基准
    df["date"] = pd.to_datetime(df.index.date)
    daily_close = df.groupby("date")["Close"].last()
    prev_close_map = daily_close.shift(1)
    df["prev_day_close"] = df["date"].map(prev_close_map)

    # 计算14天同时段平均波动率，shift防止用到未来数据
    df["tod"] = df.index.strftime("%H:%M")
    df["avg_pct_ch_14d"] = (
        df.groupby("tod")["abs_pct_ch"]
        .transform(lambda s: s.shift(1).rolling(rolling_window).mean())
    )

    anchor_high = df[["prev_day_close", "day_open"]].max(axis=1)
    anchor_low = df[["prev_day_close", "day_open"]].min(axis=1)
    band_width = df["avg_pct_ch_14d"] * band_multiplier

    # 上界和下界
    df["upper"] = anchor_high * (1 + band_width)
    df["lower"] = anchor_low * (1 - band_width)

    # 只在整点和半点进行交易
    minute = df.index.minute
    df["trade_time"] = trade_time(minute)

    df["buy"] = (df["Close"] > df["upper"]) & df["trade_time"]
    df["sell"] = (df["Close"] < df["lower"]) & df["trade_time"]

    return df


# Improvement 1: Trailing Cross current band & VWAP
def cross_boundary_buy_signal_VWAP(df):
    df = df.copy()
    df["typical_price"] = (df["Close"] + df["Low"] + df["High"]) / 3
    df["pv"] = df["typical_price"] * df["Volume"]
    df["cumsum_pv"] = df.groupby(df.index.date)["pv"].cumsum()
    df["cumsum_volume"] = df.groupby(df.index.date)["Volume"].cumsum()
    df["VWAP"] = df["cumsum_pv"] / df["cumsum_volume"]

    df["short_stop"] = df["Close"] > df[["lower", "VWAP"]].min(axis=1)
    df["long_stop"] = df["Close"] < df[["upper", "VWAP"]].max(axis=1)

    return df


# Improvement 2: Trailing Cross current band & VWAP & Dynamic share
def daily_share_by_std(df, lookback=14):
    df = df.copy()
    daily_ret = (
        df.groupby("date")["Close"].last()
        / df.groupby("date")["prev_day_close"].last()
        - 1
    )
    vol_daily_ret_14d = (
        daily_ret
        .shift(1)
        .rolling(window=lookback, min_periods=lookback)
        .std(ddof=1)
    )

    df["vol_daily_ret_14d"] = pd.to_datetime(df["date"]).map(vol_daily_ret_14d)
    return df


def add_istar_slippage_features(df, lookback=30, min_periods=30):
    return msl.prepare_istar_features(
        df,
        lookback=lookback,
        min_periods=min_periods,
    )


def share_cal_std(cash, row, lvg):
    open_price = row.Open
    std = row.vol_daily_ret_14d
    target_vol = 0.02

    if pd.isna(std) or std <= 0:
        return 0

    target_position_value = cash * min(lvg, target_vol / std)
    position_size = target_position_value / open_price
    return np.floor(position_size)


def add_vix_regime_features(
    df,
    df_vix,
    low_vol_threshold=18,
    medium_vol_threshold=25,
    high_vol_threshold=35,
    extreme_vol_threshold=45,
):
    df = df.copy()
    vix_open = df_vix["Open"].copy()
    vix_open.index = pd.to_datetime(vix_open.index).normalize()

    df["date"] = pd.to_datetime(df.index.date)
    df["vix_open"] = df["date"].map(vix_open)

    conditions = [
        df["vix_open"] < low_vol_threshold,
        (df["vix_open"] >= low_vol_threshold) & (df["vix_open"] < medium_vol_threshold),
        (df["vix_open"] >= medium_vol_threshold) & (df["vix_open"] < high_vol_threshold),
        (df["vix_open"] >= high_vol_threshold) & (df["vix_open"] < extreme_vol_threshold),
        df["vix_open"] >= extreme_vol_threshold,
    ]
    labels = ["low", "medium", "high", "very_high", "extreme"]
    df["vol_regime"] = np.select(conditions, labels, default="unknown")

    # Low-vol days are filtered out. High-vol days get tighter bands and larger size.
    df["trade_enabled"] = df["vix_open"] >= low_vol_threshold
    df["band_scale"] = np.select(
        conditions,
        [1.25, 1.10, 0.95, 0.85, 1.00],
        default=1.10,
    )
    df["size_scale"] = np.select(
        conditions,
        [0.0, 0.75, 1.00, 1.35, 1.15],
        default=0.75,
    )
    return df


def share_cal_vix_regime(cash, row, lvg):
    open_price = row.Open
    std = row.vol_daily_ret_14d
    target_vol = 0.02

    if pd.isna(std) or std <= 0:
        return 0

    size_scale = getattr(row, "size_scale", 1.0)
    effective_leverage = max(0.0, lvg * size_scale)
    if effective_leverage == 0:
        return 0

    target_position_value = cash * min(effective_leverage, target_vol / std)
    position_size = target_position_value / open_price
    return np.floor(position_size)


def volatility_adaptive_momentum(
    df,
    df_vix,
    orb_minutes=30,
    low_vol_threshold=18,
    medium_vol_threshold=25,
    high_vol_threshold=35,
    extreme_vol_threshold=45,
    rolling_window=14,
):
    df = df.copy()
    df = add_vix_regime_features(
        df,
        df_vix,
        low_vol_threshold=low_vol_threshold,
        medium_vol_threshold=medium_vol_threshold,
        high_vol_threshold=high_vol_threshold,
        extreme_vol_threshold=extreme_vol_threshold,
    )
    df = calculate_orb(df, orb_minutes=orb_minutes)
    df = calculate_momentum(df, rolling_window=rolling_window)

    # Rebuild bands using regime-specific band scaling.
    band_width = df["avg_pct_ch_14d"] * df["band_scale"]
    anchor_high = df[["prev_day_close", "day_open"]].max(axis=1)
    anchor_low = df[["prev_day_close", "day_open"]].min(axis=1)
    df["upper"] = anchor_high * (1 + band_width)
    df["lower"] = anchor_low * (1 - band_width)

    df["buy"] = df["trade_enabled"] & df["trade_time"] & (df["Close"] > df["upper"]) & df["orb_breakout"]
    df["sell"] = df["trade_enabled"] & df["trade_time"] & (df["Close"] < df["lower"]) & df["orb_breakdown"]

    df = cross_boundary_buy_signal_VWAP(df)
    df = daily_share_by_std(df, lookback=rolling_window)
    return df


# BASELINE: Buy and hold
def buy_and_hold(cash, df):
    shares = cash / df["Open"].iloc[0]
    buy_hold = shares * df["Close"]
    return buy_hold


def mom_orb_combined(df, orb_minutes=30):
    df = calculate_orb(df, orb_minutes)
    df = calculate_momentum(df)
    df["buy"] = df["buy"] & df["orb_breakout"] & df["trade_time"]
    df["sell"] = df["sell"] & df["orb_breakdown"] & df["trade_time"]

    return df
