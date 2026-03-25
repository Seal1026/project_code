#回测函数
import numpy as np
import pandas as pd

import my_trade_algo as mta


def _i_star_slippage_bps(Q, ADV, sigma, a1, a2, a3):
    """Compute I-Star market impact in basis points.

    Parameters
    ----------
    Q : float
        Order size in shares.
    ADV : float
        Average daily volume in shares (e.g. 30-day ADV).
    sigma : float
        Price volatility (e.g. 30-day volatility of returns).
    a1, a2, a3 : float
        Model parameters.
    """

    if ADV <= 0 or Q <= 0 or sigma <= 0:
        return 0.0

    return a1 * (Q / ADV) ** a2 * (sigma ** a3)


def _ensure_i_star_features(df, adv_col, sigma_col, adv_window=30, vol_window=30):
    """Ensure ADV and volatility columns exist for I-Star cost model.

    This derives:
    - ``adv_col``: rolling average daily volume over ``adv_window`` days
    - ``sigma_col``: rolling volatility (std) of daily returns over ``vol_window`` days
      based on close prices.
    """

    # Require basic fields
    if "Volume" not in df.columns or "Close" not in df.columns:
        return df

    # Use calendar days derived from the index
    day_index = pd.to_datetime(df.index.normalize())

    # --- ADV (average daily volume) ---
    daily_volume = df.groupby(day_index)["Volume"].sum()
    # Use only past information: shift by 1 day
    adv_daily = daily_volume.shift(1).rolling(window=adv_window, min_periods=1).mean()
    df[adv_col] = day_index.map(adv_daily)

    # --- Volatility of daily returns ---
    daily_close = df.groupby(day_index)["Close"].last()
    daily_ret = daily_close.pct_change()
    sigma_daily = daily_ret.shift(1).rolling(window=vol_window, min_periods=1).std(ddof=1)
    df[sigma_col] = day_index.map(sigma_daily)

    return df


def _apply_i_star_cost(df, index, trade_qty, trade_price, cash, realized_pnl, adv_col, sigma_col, i_star_params):
    """Apply I-Star transaction cost to cash and realized PnL.

    Cost is expressed in basis points of traded notional:

        I*_bp = a1 * (Q / ADV) ** a2 * sigma ** a3

    and dollar cost = price * Q * I*_bp / 10,000.
    """

    if trade_qty == 0:
        return cash, realized_pnl

    if adv_col not in df.columns or sigma_col not in df.columns:
        return cash, realized_pnl

    ADV = df.at[index, adv_col]
    sigma = df.at[index, sigma_col]

    if ADV is None or sigma is None:
        return cash, realized_pnl

    try:
        ADV = float(ADV)
        sigma = float(sigma)
    except (TypeError, ValueError):
        return cash, realized_pnl

    if i_star_params is None:
        # Default parameters; can be overridden via backtest(..., i_star_params={...})
        a1, a2, a3 = 1.0, 1.0, 1.0
    else:
        a1 = i_star_params.get("a1", 1.0)
        a2 = i_star_params.get("a2", 1.0)
        a3 = i_star_params.get("a3", 1.0)

    impact_bps = _i_star_slippage_bps(abs(trade_qty), ADV, sigma, a1, a2, a3)

    if impact_bps <= 0:
        return cash, realized_pnl

    cost = trade_price * abs(trade_qty) * impact_bps / 10000.0
    cash -= cost
    realized_pnl -= cost

    return cash, realized_pnl


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


def _enter_position(
    df,
    index,
    side,
    share_today,
    close_price,
    cash,
    realized_pnl,
    use_slippage,
    adv_col,
    sigma_col,
    i_star_params,
):
    if side == "long":
        position_qty = share_today
        cash -= share_today * close_price
        _mark_trade(df, index, "long")
    else:
        position_qty = -share_today
        cash += share_today * close_price
        _mark_trade(df, index, "short")

    if use_slippage:
        cash, realized_pnl = _apply_i_star_cost(
            df,
            index,
            trade_qty=share_today,
            trade_price=close_price,
            cash=cash,
            realized_pnl=realized_pnl,
            adv_col=adv_col,
            sigma_col=sigma_col,
            i_star_params=i_star_params,
        )

    avg_entry_price = close_price
    return position_qty, avg_entry_price, cash, realized_pnl


def _close_position(
    df,
    index,
    position_qty,
    avg_entry_price,
    close_price,
    cash,
    realized_pnl,
    use_slippage,
    adv_col,
    sigma_col,
    i_star_params,
):
    profit = (close_price - avg_entry_price) * position_qty
    cash += position_qty * close_price
    realized_pnl += profit

    if use_slippage:
        cash, realized_pnl = _apply_i_star_cost(
            df,
            index,
            trade_qty=position_qty,
            trade_price=close_price,
            cash=cash,
            realized_pnl=realized_pnl,
            adv_col=adv_col,
            sigma_col=sigma_col,
            i_star_params=i_star_params,
        )

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


def _handle_entry(
    df,
    index,
    side,
    share_today,
    close_price,
    realized_pnl,
    equity,
    timestamp,
    cash,
    use_slippage,
    adv_col,
    sigma_col,
    i_star_params,
):
    position_qty, avg_entry_price, cash, realized_pnl = _enter_position(
        df,
        index,
        side,
        share_today,
        close_price,
        cash,
        realized_pnl,
        use_slippage,
        adv_col,
        sigma_col,
        i_star_params,
    )
    unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
    _log_position_entry(side.upper(), timestamp, position_qty, realized_pnl, cash, avg_entry_price, equity)
    return position_qty, avg_entry_price, cash, realized_pnl, unrealized_pnl, equity


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
    use_slippage,
    adv_col,
    sigma_col,
    i_star_params,
):
    profit, cash, realized_pnl = _close_position(
        df,
        index,
        position_qty,
        avg_entry_price,
        close_price,
        cash,
        realized_pnl,
        use_slippage,
        adv_col,
        sigma_col,
        i_star_params,
    )
    _mark_trade(df, index, "close")
    _, exit_equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)
    _log_position_exit(current_side.upper(), timestamp, profit, position_qty, close_price, realized_pnl, cash, avg_entry_price, exit_equity)

    if enter_opposite:
        position_qty, avg_entry_price, cash, realized_pnl = _enter_position(
            df,
            index,
            next_side,
            share_today,
            close_price,
            cash,
            realized_pnl,
            use_slippage,
            adv_col,
            sigma_col,
            i_star_params,
        )
    else:
        position_qty, avg_entry_price = _reset_position()

    unrealized_pnl, equity = _mark_to_market(position_qty, avg_entry_price, close_price, cash)

    if enter_opposite:
        _log_position_entry(next_side.upper(), timestamp, position_qty, realized_pnl, cash, avg_entry_price, equity)

    return position_qty, avg_entry_price, cash, realized_pnl, unrealized_pnl, equity


def backtest(
    df,
    calc_share_function=None,
    lvg=None,
    enter_opposite=False,
    use_slippage=False,
    adv_col="ADV",
    sigma_col="sigma_30d",
    i_star_params=None,
):
    df = df.copy()

    # If slippage is enabled but required columns are missing, derive them
    if use_slippage and (adv_col not in df.columns or sigma_col not in df.columns):
        df = _ensure_i_star_features(df, adv_col=adv_col, sigma_col=sigma_col)

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
                profit, cash, realized_pnl = _close_position(
                    df,
                    df.index[i],
                    position_qty,
                    avg_entry_price,
                    close_price,
                    cash,
                    realized_pnl,
                    use_slippage,
                    adv_col,
                    sigma_col,
                    i_star_params,
                )
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
                (
                    position_qty,
                    avg_entry_price,
                    cash,
                    realized_pnl,
                    unrealized_pnl,
                    equity,
                ) = _handle_entry(
                    df,
                    df.index[i],
                    "long",
                    share_today,
                    close_price,
                    realized_pnl,
                    equity,
                    timestamp,
                    cash,
                    use_slippage,
                    adv_col,
                    sigma_col,
                    i_star_params,
                )
            elif short_signal:
                (
                    position_qty,
                    avg_entry_price,
                    cash,
                    realized_pnl,
                    unrealized_pnl,
                    equity,
                ) = _handle_entry(
                    df,
                    df.index[i],
                    "short",
                    share_today,
                    close_price,
                    realized_pnl,
                    equity,
                    timestamp,
                    cash,
                    use_slippage,
                    adv_col,
                    sigma_col,
                    i_star_params,
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
                    use_slippage,
                    adv_col,
                    sigma_col,
                    i_star_params,
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
                use_slippage,
                adv_col,
                sigma_col,
                i_star_params,
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
