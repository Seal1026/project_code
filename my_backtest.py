#回测函数
import numpy as np

import my_trade_algo as mta


def _mark_trade(df, index, column):
    df.loc[index, column] = True


def _log_day_start(verbose, timestamp, position_qty, realized_pnl, share_today, cash, open_price):
    if not verbose:
        return
    print("===============================")
    print(
        f"{timestamp}: Start of day. Position quantity: {position_qty}. "
        f"Realized pnl: {realized_pnl}. Calculate share: {share_today}. "
        f"Cash: {cash}. Open: {open_price}"
    )


def _log_position_entry(verbose, side, timestamp, position_qty, realized_pnl, cash, avg_entry_price, equity):
    if not verbose:
        return
    print(
        f"{timestamp}: ENTER {side}: Position quantity: {position_qty}. "
        f"Realized pnl: {realized_pnl}. Cash: {cash}. "
        f"Avg entry price: {avg_entry_price}. Equity: {equity}"
    )


def _log_position_exit(verbose, side, timestamp, profit, position_qty, close_price, realized_pnl, cash, avg_entry_price, equity):
    if not verbose:
        return
    print(
        f"{timestamp}: EXIT {side}: Profit: {profit}. Close: {close_price}. "
        f"Position quantity: {position_qty}. Realized pnl: {realized_pnl}. "
        f"Cash: {cash}. Avg entry price: {avg_entry_price}. Equity: {equity}"
    )


def _log_position_hold(verbose, side, timestamp, close_price, upper, lower):
    if not verbose:
        return
    print(f"{timestamp}: REMAIN {side}: Close: {close_price}. Upper: {upper}. Lower: {lower}")


def _log_flat(verbose, timestamp, close_price, upper, lower):
    if not verbose:
        return
    print(f"{timestamp}: FLAT: Close: {close_price}. Upper: {upper}. Lower: {lower}")


def _log_day_end(verbose, timestamp, position_qty, realized_pnl, close_price, cash):
    if not verbose:
        return
    print(
        f"{timestamp}: End of day. Position quantity: {position_qty}. "
        f"Realized pnl: {realized_pnl}. Close: {close_price}. Cash: {cash}. "
        f"Realized PnL: {realized_pnl}"
    )


def _log_backtest_end(verbose, position_qty, realized_pnl, cash, avg_entry_price, equity):
    if not verbose:
        return
    print(
        f"END OF BACKTEST: Position quantity: {position_qty}. "
        f"Realized pnl: {realized_pnl}. Cash: {cash}. "
        f"Avg entry price: {avg_entry_price}. Equity: {equity}"
    )


def _enter_position(df, index, side, share_today, close_price, cash, fill_price=None):
    price = fill_price if fill_price is not None else close_price
    if side == "long":
        position_qty = share_today
        cash -= share_today * price
        _mark_trade(df, index, "long")
    else:
        position_qty = -share_today
        cash += share_today * price
        _mark_trade(df, index, "short")

    avg_entry_price = price
    return position_qty, avg_entry_price, cash


def _close_position(position_qty, avg_entry_price, close_price, cash, realized_pnl, fill_price=None):
    price = fill_price if fill_price is not None else close_price
    profit = (price - avg_entry_price) * position_qty
    cash += position_qty * price
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


def _handle_entry(verbose, df, index, side, share_today, close_price, realized_pnl, equity, timestamp, cash, fill_price=None):
    position_qty, avg_entry_price, cash = _enter_position(df, index, side, share_today, close_price, cash, fill_price)
    unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
    _log_position_entry(verbose, side.upper(), timestamp, position_qty, realized_pnl, cash, avg_entry_price, equity)
    return position_qty, avg_entry_price, cash, unrealized_pnl, equity


def _close_and_optionally_reverse(
    verbose,
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
    close_fill_price=None,
    entry_fill_price=None,
):
    profit, cash, realized_pnl = _close_position(position_qty, avg_entry_price, close_price, cash, realized_pnl, close_fill_price)
    _mark_trade(df, index, "close")
    _, exit_equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
    _log_position_exit(verbose, current_side.upper(), timestamp, profit, position_qty, close_price, realized_pnl, cash, avg_entry_price, exit_equity)

    if enter_opposite:
        position_qty, avg_entry_price, cash = _enter_position(df, index, next_side, share_today, close_price, cash, entry_fill_price)
    else:
        position_qty, avg_entry_price = _reset_position()

    unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)

    if enter_opposite:
        _log_position_entry(verbose, next_side.upper(), timestamp, position_qty, realized_pnl, cash, avg_entry_price, equity)

    return position_qty, avg_entry_price, cash, realized_pnl, unrealized_pnl, equity


def backtest(df, calc_share_function=None, lvg=None, enter_opposite=False,
             slippage_model=None, verbose=False):
    """
    Run backtest on a prepared signals dataframe.

    Parameters
    ----------
    df : DataFrame with columns: Open, Close, upper, lower, buy, sell,
         optionally long_stop, short_stop (for VWAP-based exits).
    calc_share_function : callable(cash, row, lvg) -> int, or None (uses equity//open)
    lvg : leverage cap passed to calc_share_function
    enter_opposite : if True, reverse position instead of just closing
    slippage_model : HybridLinearCostModel instance (or compatible), or None
    verbose : if False (default) suppresses all trade-level print output
    """
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

        # Compute slippage-adjusted fill prices for this bar (if cost model is provided)
        if slippage_model is not None:
            _buy_fill = slippage_model.fill_price("buy", max(1, share_today), close_price, row)
            _sell_fill = slippage_model.fill_price("sell", max(1, share_today), close_price, row)
            _close_long_fill = slippage_model.fill_price("sell", max(1, abs(position_qty)), close_price, row)
            _close_short_fill = slippage_model.fill_price("buy", max(1, abs(position_qty)), close_price, row)
        else:
            _buy_fill = _sell_fill = _close_long_fill = _close_short_fill = None

        if timestamp in day_first_set:
            share_today = _calculate_share_today(calc_share_function, equity, cash, open_price, row, lvg)
            _log_day_start(verbose, timestamp, position_qty, realized_pnl, share_today, cash, open_price)
            unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if timestamp in day_last_set:
            if position_qty != 0:
                eod_fill = _close_long_fill if position_qty > 0 else _close_short_fill
                profit, cash, realized_pnl = _close_position(position_qty, avg_entry_price, close_price, cash, realized_pnl, eod_fill)
                if verbose:
                    print(
                        f"{timestamp}: CLOSE POSITION: Profit: {profit}. Position quantity: {position_qty}. "
                        f"Close: {close_price}. Cash: {cash}. Avg entry price: {avg_entry_price}."
                    )
                position_qty, avg_entry_price = _reset_position()

            unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
            _log_day_end(verbose, timestamp, position_qty, realized_pnl, close_price, cash)
            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if not mta.trade_time(timestamp.minute):
            unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if position_qty == 0:
            if buy_signal:
                position_qty, avg_entry_price, cash, unrealized_pnl, equity = _handle_entry(
                    verbose, df, df.index[i], "long", share_today, close_price, realized_pnl, equity, timestamp, cash, _buy_fill
                )
            elif short_signal:
                position_qty, avg_entry_price, cash, unrealized_pnl, equity = _handle_entry(
                    verbose, df, df.index[i], "short", share_today, close_price, realized_pnl, equity, timestamp, cash, _sell_fill
                )
            else:
                unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
                _log_flat(verbose, timestamp, close_price, upper, lower)

            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if position_qty > 0:
            if long_stop:
                position_qty, avg_entry_price, cash, realized_pnl, unrealized_pnl, equity = _close_and_optionally_reverse(
                    verbose,
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
                    close_fill_price=_close_long_fill,
                    entry_fill_price=_sell_fill,
                )
            else:
                unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
                _log_position_hold(verbose, "LONG", timestamp, close_price, upper, lower)

            _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)
            continue

        if short_stop:
            position_qty, avg_entry_price, cash, realized_pnl, unrealized_pnl, equity = _close_and_optionally_reverse(
                verbose,
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
                close_fill_price=_close_short_fill,
                entry_fill_price=_buy_fill,
            )
        else:
            unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
            _log_position_hold(verbose, "SHORT", timestamp, close_price, upper, lower)

        _update_arrays(i, realized_pnl, unrealized_pnl, cash, equity, realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr)

    df["realized_pnl"] = realized_pnl_arr
    df["unrealized_pnl"] = unrealized_pnl_arr
    df["cash"] = cash_arr
    df["equity"] = equity_arr

    _log_backtest_end(verbose, position_qty, realized_pnl, cash, avg_entry_price, equity)
    return realized_pnl_arr, unrealized_pnl_arr, cash_arr, equity_arr, df
