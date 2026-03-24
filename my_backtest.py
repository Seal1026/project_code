#回测函数
import numpy as np

import my_trade_algo as mta


def _mark_trade(df, index, column):
    df.loc[index, column] = True


def _log_day_start(timestamp, position_qty, realized_pnl, share_today, cash, open_price):
    print("===============================")
    print(
        f"{timestamp}: Start of day. Position quantity: {position_qty}. "
        f"Realized pnl: {realized_pnl}. Calculate share: {share_today}. "
        f"Cash: {cash}. Open: {open_price}"
    )


def _log_position_entry(side, timestamp, position_qty, realized_pnl, cash, avg_entry_price, equity):
    print(
        f"{timestamp}: ENTER {side}: Position quantity: {position_qty}. "
        f"Realized pnl: {realized_pnl}. Cash: {cash}. "
        f"Avg entry price: {avg_entry_price}. Equity: {equity}"
    )


def _log_position_exit(side, timestamp, profit, position_qty, close_price, realized_pnl, cash, avg_entry_price, equity):
    print(
        f"{timestamp}: EXIT {side}: Profit: {profit}. Close: {close_price}. "
        f"Position quantity: {position_qty}. Realized pnl: {realized_pnl}. "
        f"Cash: {cash}. Avg entry price: {avg_entry_price}. Equity: {equity}"
    )


def _log_position_hold(side, timestamp, close_price, upper, lower):
    print(f"{timestamp}: REMAIN {side}: Close: {close_price}. Upper: {upper}. Lower: {lower}")


def _log_flat(timestamp, close_price, upper, lower):
    print(f"{timestamp}: FLAT: Close: {close_price}. Upper: {upper}. Lower: {lower}")


def _log_day_end(timestamp, position_qty, realized_pnl, close_price, cash):
    print(
        f"{timestamp}: End of day. Position quantity: {position_qty}. "
        f"Realized pnl: {realized_pnl}. Close: {close_price}. Cash: {cash}. "
        f"Realized PnL: {realized_pnl}"
    )


def _log_backtest_end(position_qty, realized_pnl, cash, avg_entry_price, equity):
    print(
        f"END OF BACKTEST: Position quantity: {position_qty}. "
        f"Realized pnl: {realized_pnl}. Cash: {cash}. "
        f"Avg entry price: {avg_entry_price}. Equity: {equity}"
    )


def _enter_position(df, index, side, share_today, close_price, cash):
    if side == "long":
        position_qty = share_today
        cash -= share_today * close_price
        _mark_trade(df, index, "long")
    else:
        position_qty = -share_today
        cash += share_today * close_price
        _mark_trade(df, index, "short")

    avg_entry_price = close_price
    return position_qty, avg_entry_price, cash


def _close_position(position_qty, avg_entry_price, close_price, cash, realized_pnl):
    profit = (close_price - avg_entry_price) * position_qty
    cash += position_qty * close_price
    realized_pnl += profit
    return profit, cash, realized_pnl


def _reset_position():
    return 0, 0


def _mark_to_market(position_qty, avg_entry_price, close_price, cash):
    unrealized_pnl = position_qty * (close_price - avg_entry_price) if position_qty != 0 else 0
    equity = cash + position_qty * close_price
    return unrealized_pnl, equity


def _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr):
    realized_pnl_arr[i] = realized_pnl
    unrealized_pnl_arr[i] = unrealized_pnl
    cash_arr[i] = cash
    equity_arr[i] = equity


def _calculate_share_today(calc_share_function, equity, cash, open_price, row, lvg):
    if calc_share_function is None:
        return equity // open_price
    return calc_share_function(cash, row, lvg)


def _handle_entry(df, index, side, share_today, close_price, realized_pnl, equity, timestamp, cash):
    position_qty, avg_entry_price, cash = _enter_position(df, index, side, share_today, close_price, cash)
    unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
    _log_position_entry(side.upper(), timestamp, position_qty, realized_pnl, cash, avg_entry_price, equity)
    return position_qty, avg_entry_price, cash, unrealized_pnl, equity


def _close_and_optionally_reverse(
    df,
    index,
    current_side,
    next_side,
    position_qty,
    avg_entry_price,
    close_price,
    cash,
    realized_pnl,
    share_today,
    enter_opposite,
    timestamp,
):
    profit, cash, realized_pnl = _close_position(position_qty, avg_entry_price, close_price, cash, realized_pnl)
    _mark_trade(df, index, "close")
    _, exit_equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
    _log_position_exit(current_side.upper(), timestamp, profit, position_qty, close_price, realized_pnl, cash, avg_entry_price, exit_equity)

    if enter_opposite:
        position_qty, avg_entry_price, cash = _enter_position(df, index, next_side, share_today, close_price, cash)
    else:
        position_qty, avg_entry_price = _reset_position()

    unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)

    if enter_opposite:
        _log_position_entry(next_side.upper(), timestamp, position_qty, realized_pnl, cash, avg_entry_price, equity)

    return position_qty, avg_entry_price, cash, realized_pnl, unrealized_pnl, equity


def backtest(df, calc_share_function=None, lvg=None, enter_opposite=False):
    df = df.copy()

    position_qty = 0
    avg_entry_price = 0
    share_today = 0

    cash = 100000
    realized_pnl = 0
    unrealized_pnl = 0
    equity = cash

    n = df.shape[0]
    realized_pnl_arr = np.zeros(n)
    unrealized_pnl_arr = np.zeros(n)
    cash_arr = np.zeros(n)
    equity_arr = np.zeros(n)

    # 每日的开盘和收盘时间 US: 9:30-16:00
    day_last_set = set(df.groupby(df.index.normalize()).tail(1).index)
    day_first_set = set(df.groupby(df.index.normalize()).head(1).index)

    for i, row in enumerate(df.itertuples()):
        open_price = row.Open
        close_price = row.Close
        timestamp = row.Index
        upper = row.upper
        lower = row.lower

        buy_signal = row.buy
        short_stop = row.buy
        short_signal = row.sell
        long_stop = row.sell

        if "long_stop" in row._fields and "short_stop" in row._fields:
            long_stop = row.long_stop
            short_stop = row.short_stop

        if timestamp in day_first_set:
            share_today = _calculate_share_today(calc_share_function, equity, cash, open_price, row, lvg)
            _log_day_start(timestamp, position_qty, realized_pnl, share_today, cash, open_price)
            unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if timestamp in day_last_set:
            if position_qty != 0:
                profit, cash, realized_pnl = _close_position(position_qty, avg_entry_price, close_price, cash, realized_pnl)
                # _mark_trade(df, i, "close")
                print(
                    f"{timestamp}: CLOSE POSITION: Profit: {profit}. Position quantity: {position_qty}. "
                    f"Close: {close_price}. Cash: {cash}. Avg entry price: {avg_entry_price}."
                )
                position_qty, avg_entry_price = _reset_position()

            unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
            _log_day_end(timestamp, position_qty, realized_pnl, close_price, cash)
            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if not mta.trade_time(timestamp.minute):
            unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if position_qty == 0:
            if buy_signal:
                position_qty, avg_entry_price, cash, unrealized_pnl, equity = _handle_entry(
                    df, df.index[i], "long", share_today, close_price, realized_pnl, equity, timestamp, cash
                )
            elif short_signal:
                position_qty, avg_entry_price, cash, unrealized_pnl, equity = _handle_entry(
                    df, df.index[i], "short", share_today, close_price, realized_pnl, equity, timestamp, cash
                )
            else:
                unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
                _log_flat(timestamp, close_price, upper, lower)

            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if position_qty > 0:
            if long_stop:
                position_qty, avg_entry_price, cash, realized_pnl, unrealized_pnl, equity = _close_and_optionally_reverse(
                    df,
                    df.index[i],
                    "long",
                    "short",
                    position_qty,
                    avg_entry_price,
                    close_price,
                    cash,
                    realized_pnl,
                    share_today,
                    enter_opposite,
                    timestamp,
                )
            else:
                unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
                _log_position_hold("LONG", timestamp, close_price, upper, lower)

            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if short_stop:
            position_qty, avg_entry_price, cash, realized_pnl, unrealized_pnl, equity = _close_and_optionally_reverse(
                df,
                df.index[i],
                "short",
                "long",
                position_qty,
                avg_entry_price,
                close_price,
                cash,
                realized_pnl,
                share_today,
                enter_opposite,
                timestamp,
            )
        else:
            unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
            _log_position_hold("SHORT", timestamp, close_price, upper, lower)

        _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)

    df["realized_pnl"] = realized_pnl_arr
    df["unrealized_pnl"] = unrealized_pnl_arr
    df["cash"] = cash_arr
    df["equity"] = equity_arr

    _log_backtest_end(position_qty, realized_pnl, cash, avg_entry_price, equity)
    return realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr, df
