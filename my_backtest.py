#回测函数
import math
import numpy as np
import pandas as pd
import my_trade_algo as mta


def backtest(df,calc_share_function= None,lvg = None):
    df = df.copy()

    position_qty = 0 
    avg_entry_price = 0 

    share_today = 0 

    cash = 100000

    realized_pnl = 0
    unrealized_pnl = 0

    equity = cash
    trade_count = 0 

    n = df.shape[0]
    
    realized_pnl_arr = np.zeros(n)
    unrealized_pnl_arr = np.zeros(n)
    cash_arr = np.zeros(n)
    equity_arr = np.zeros(n)

    #每日的开盘和收盘时间 US: 9:30-16:00
    day_last_set = set(df.groupby(df.index.normalize())\
                       .tail(1).index)
    day_first_set = set(df.groupby(df.index.normalize())\
                       .head(1).index)
    
    def update_arrays(i):
        realized_pnl_arr[i] = realized_pnl
        unrealized_pnl_arr[i] = unrealized_pnl
        cash_arr[i] = cash
        equity_arr[i] = equity
    
    for i,row in enumerate(df.itertuples()):
        # within the day 
        open,close = row.Open, row.Close
        buy_signal = short_stop = row.buy 
        short_signal = long_stop = row.sell
        datetime = row.Index
        upper = row.upper
        lower = row.lower
  
        # 0. day open, share    
        if datetime in day_first_set:
            if not calc_share_function:
                share_today = equity // open
            else:
                share_today = calc_share_function(cash,row,lvg)

            print("===============================")
            print(f"{datetime}: Start of day. Position quantity: {position_qty}.Unrealized pnl: {unrealized_pnl}. Realized pnl: {realized_pnl}.Calculate share: {share_today}. Cash: {cash}. Open: {open}")
            update_arrays(i)
            continue
        
        if "long_stop" in row._fields and "short_stop" in row._fields:
            long_stop = row.long_stop
            short_stop = row.short_stop

        # 4. end of date [end position] 
        if datetime in day_last_set:
            # close existing position
            if position_qty!=0:
                profit = (close - avg_entry_price) * position_qty
                cash += position_qty * close

                realized_pnl += profit 
                print(f"{datetime}: CLOSE POSITION: Profit: {profit}.Position quantity: {position_qty}.Close:{close}.Cash: {cash}. Avg entry price: {avg_entry_price}.")

                position_qty = 0
                avg_entry_price = 0
                
            
            print(f"{datetime}: End of day. Position quantity: {position_qty}.Unrealized pnl: {unrealized_pnl}. Realized pnl: {realized_pnl}.Close:{close}. Cash: {cash}. Realized PnL: {realized_pnl}")
            update_arrays(i)
            continue

        # Trade only at 30 and 00
        if not mta.trade_time(datetime.minute):
            update_arrays(i)
            continue
        
        # 1. 0 position
        if position_qty == 0:
            # 1.1 0 >> long
            if buy_signal:
                position_qty = share_today
                avg_entry_price = close

                cash -= position_qty * avg_entry_price
                unrealized_pnl = position_qty * (close - avg_entry_price)

                df.loc[df.index[i], "long"] = True
                print(f"{datetime}: ENTER LONG: Position quantity: {position_qty}.Unrealized pnl: {unrealized_pnl}. Realized pnl: {realized_pnl}.Cash: {cash}. Avg entry price: {avg_entry_price}. Equity: {equity}")
            # 1.2 0 >> short
            elif short_signal:
                position_qty = -share_today
                avg_entry_price = close
                cash += share_today * close

                unrealized_pnl = position_qty * (close - avg_entry_price)
                df.loc[df.index[i], "short"] = True
                print(f"{datetime}: ENTER SHORT: Position quantity: {position_qty}.Unrealized pnl: {unrealized_pnl}. Realized pnl: {realized_pnl}.Cash: {cash}. Avg entry price: {avg_entry_price}. Equity: {equity}")
            
            else: 
                unrealized_pnl = position_qty * (close - avg_entry_price) if position_qty != 0 else 0
                equity = cash + position_qty * close
                print(f"{datetime}: FLAT: Close:{close}. Upper: {upper}. Lower: {lower}")
            update_arrays(i)
            continue


        # 2. long >> short, close and then open
        if position_qty > 0:
            if long_stop:
                profit = (close - avg_entry_price) * position_qty 
                realized_pnl += profit
                cash += position_qty * close
                df.loc[df.index[i], "close"] = True
                print(f"{datetime}: EXIT LONG: Profit: {profit}. Close:{close}.Position quantity: {position_qty}. Close:{close}.Unrealized pnl: {unrealized_pnl}. Realized pnl: {realized_pnl}.Cash: {cash}. Avg entry price: {avg_entry_price}. Equity: {equity}")

                position_qty = -share_today 
                avg_entry_price = close 
                cash += share_today * close

                df.loc[df.index[i], "short"] = True

                unrealized_pnl = position_qty * (close - avg_entry_price)
                print(f"{datetime}: ENTER SHORT: Position quantity: {position_qty}.Unrealized pnl: {unrealized_pnl}. Realized pnl: {realized_pnl}.Cash: {cash}. Avg entry price: {avg_entry_price}. Equity: {equity}")
            else:
                unrealized_pnl = position_qty * (close - avg_entry_price) if position_qty != 0 else 0
                equity = cash + position_qty * close
                print(f"{datetime}: REMAIN LONG: Close:{close}.Upper: {upper}. Lower: {lower}")
            update_arrays(i)
            continue

        # 3. short > long 
        if position_qty < 0:
            if short_stop:
                profit = (close - avg_entry_price) * position_qty 
                realized_pnl += profit

                cash += position_qty * close #flat short: reduce money

                print(f"{datetime}: EXIT SHORT: Profit: {profit}.Close:{close}. Position quantity: {position_qty}.Close:{close}.  Unrealized pnl: {unrealized_pnl}.Realized pnl: {realized_pnl}. Cash: {cash}.Avg entry price: {avg_entry_price}. Equity: {equity}")

                df.loc[df.index[i], "close"] = True
                df.loc[df.index[i], "long"] = True
                position_qty = share_today 
                avg_entry_price = close 
                cash -= position_qty * close
                unrealized_pnl = position_qty * (close - avg_entry_price)
                print(f"{datetime}: ENTER LONG: Position quantity: {position_qty}.Unrealized pnl: {unrealized_pnl}. Realized pnl: {realized_pnl}.Cash: {cash}. Avg entry price: {avg_entry_price}.  Equity: {equity}")
            else: 
                unrealized_pnl = position_qty * (close - avg_entry_price) if position_qty != 0 else 0
                equity = cash + position_qty * close
                print(f"{datetime}: REMAIN SHORT: Close:{close}.Upper: {upper}. Lower: {lower}")
            update_arrays(i)
            continue

    df["realized_pnl"] = realized_pnl_arr
    df["unrealized_pnl"] = unrealized_pnl_arr
    df["cash"] = cash_arr
    df["equity"] = equity_arr
    print(f"END OF BACKTEST: Position quantity: {position_qty}.Unrealized pnl: {unrealized_pnl}. Realized pnl: {realized_pnl}.Cash: {cash}. Avg entry price: {avg_entry_price}. Equity: {equity}")

    return realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr, df