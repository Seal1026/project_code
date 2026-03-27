#交易算法函数
import pandas as pd
import numpy as np
from IPython.display import display

def calculate_orb(df, orb_minutes=30):
    df = df.copy()
    df["date"] = pd.to_datetime(df.index.date)

    # 每日的开盘时间
    day_open_time = df.groupby("date").apply(lambda x: x.index[0],include_groups=False).rename("day_open_time")
    df = df.join(day_open_time, on="date")

    # 开盘范围 opening range window
    df["in_orb_window"] = (
        (df.index >= df["day_open_time"]) &
        (df.index <  df["day_open_time"] + pd.Timedelta(minutes=orb_minutes))
    )

    # 计算开盘范围的最高价和最低价
    orb_levels = (
        df[df["in_orb_window"]]
        .groupby("date")
        .agg(orb_high=("High", "max"), orb_low=("Low", "min"))
    )

    df = df.join(orb_levels, on="date")

    # # Derived ORB metrics
    # df["orb_mid"]   = (df["orb_high"] + df["orb_low"]) / 2
    # df["orb_range"] = df["orb_high"] - df["orb_low"]

    # Breakout / breakdown signals — only valid AFTER the ORB window has closed
    df["orb_breakout"]  = (~df["in_orb_window"]) & (df["Close"] > df["orb_high"]) #做多信号
    df["orb_breakdown"] = (~df["in_orb_window"]) & (df["Close"] < df["orb_low"])  #做空信号

    # Clean up helper column
    df.drop(columns=["day_open_time"], inplace=True)

    return df

def trade_time(minute):
    #TODO: Update and change back.
    return (minute==30) | (minute == 0)
    # return minute%15==0
    

#base momentum strategy
def calculate_momentum(df):
    df = df.copy()

    #以每天的开盘价为基准，计算每分钟收盘相对开盘的绝对百分比变化
    df["day_open"] = df.groupby(df.index.date)["Open"].transform(lambda x: x.iloc[0])
    df["abs_pct_ch"] = np.abs(df["Close"]/df["day_open"] - 1)

    # TODO: change to last available day.
    #以昨天的收盘价为基准
    df["date"] = pd.to_datetime(df.index.date)
    daily_close = df.groupby("date")["Close"].last()
    prev_close_map = daily_close.shift(1)
    df["prev_day_close"] = df["date"].map(prev_close_map)

    # here we don't have min window >> ignore first 14 data
    #计算14天同时段平均波动率
    rolling_window = 14 #TODO
    df["tod"] = df.index.strftime("%H:%M")
    df["avg_pct_ch_14d"] = (
        df.groupby("tod")["abs_pct_ch"]
        .transform(lambda s: s.shift(1).rolling(rolling_window).mean()) #shift防止用到未来数据
    )

    #上界和下界
    df["upper"] = df[["prev_day_close", "day_open"]].max(axis=1) * (1+ df["avg_pct_ch_14d"])
    df["lower"] = df[["prev_day_close", "day_open"]].min(axis=1) * (1- df["avg_pct_ch_14d"])

    #只在整点和半点进行交易
    minute = df.index.minute
    df.loc[trade_time(minute),["trade_time"]] = True

    df["buy"] = (df["Close"] > df["upper"]) & df["trade_time"]
    df["sell"] = (df["Close"] < df["lower"])& df["trade_time"]
    
    return df



#Improvement 1: Trailing Cross current band & VWAP
def cross_boundary_buy_signal_VWAP(df):
    df = df.copy()
    df["typical_price"] = (df["Close"] + df["Low"] + df["High"])/3 
    df["pv"] = df["typical_price"] * df["Volume"]
    df["cumsum_pv"] = df.groupby(df.index.date)["pv"].cumsum()
    df["cumsum_volume"] = df.groupby(df.index.date)["Volume"].cumsum()
    df["VWAP"] = df["cumsum_pv"]/df["cumsum_volume"]

    df["short_stop"] = df["Close"] > df[["lower","VWAP"]].min(axis=1) 
    df["long_stop"] = df["Close"] < df[["upper","VWAP"]].max(axis=1)

    # TODO: if we loose the condition for stop loss
    # df["short_stop"] = (df["Close"] > df[["lower","VWAP"]].min(axis=1) ) | df["orb_breakout"]
    # df["long_stop"] = (df["Close"] < df[["upper","VWAP"]].max(axis=1)) | df["orb_breakdown"]

    return df



#Improvement 2: Trailing Cross current band & VWAP & Dynamic share
def daily_share_by_std(df):
    daily_ret = (
        df.groupby("date")["Close"].last()
        / df.groupby("date")["prev_day_close"].last()
        - 1
    )
    # 按日算过去14天样本标准差
    vol_daily_ret_14d = (
        daily_ret
        .shift(1)
        .rolling(window=14, min_periods=14)
        .std(ddof=1)
    )

    # 映射回分钟表
    df["vol_daily_ret_14d"] = pd.to_datetime(df["date"]).map(vol_daily_ret_14d)
    return df

def share_cal_std(cash,row,lvg):
    open = row.Open
    std = row.vol_daily_ret_14d
    target_vol = 0.02 

    # calculate position size based on volatility targeting
    target_position_value = cash * min(lvg, target_vol /std )
    position_size = target_position_value / open
    return np.floor(position_size)

# BASELINE: Buy and hold
def buy_and_hold(cash,df):
    shares = cash/df["Open"].iloc[0]
    buy_hold = shares*df["Close"]
    return buy_hold

def orb_baseline(df,orb_minutes=30):
    df = calculate_orb(df, orb_minutes)
    df["buy"]  = df["orb_breakout"]  & df["trade_time"] 
    df["sell"] = df["orb_breakdown"]  & df["trade_time"]
    return df

def mom_orb_combined(df,orb_minutes=30):
    df = calculate_orb(df, orb_minutes)
    df = calculate_momentum(df)
    df["buy"]  = (df["buy"]  & df["orb_breakout"])  & df["trade_time"] 
    df["sell"] = (df["sell"] & df["orb_breakdown"])  & df["trade_time"]
    
    return df
