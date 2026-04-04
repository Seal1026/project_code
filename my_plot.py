#图像函数
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

import my_metrics as mme

#画出某一日的价格走势、上下界和交易信号
def plot_line(df, day, vwap=False, ax=None, show_legend=True):
    dt = df[df["date"] == day].copy()
    if dt.empty:
        return ax

    dt.loc[(dt.index.minute == 30) | (dt.index.minute == 0), "trade_time"] = True
    s = dt["short"] & dt["trade_time"] #卖出信号
    b = dt["long"] & dt["trade_time"] #买入信号
    c = dt["close"] & dt["trade_time"] #止损信号

    if ax is None:
        _, ax = plt.subplots(figsize=(14, 7))

    #在画布上画出上界、下界和收盘价的线条
    ax.plot(dt.index, dt["upper"], label="Upper Band", linewidth=2, color="red", linestyle="--")
    ax.plot(dt.index, dt["lower"], label="Lower Band", linewidth=2, color="green", linestyle="--")
    ax.plot(dt.index, dt["Close"], label="Close Price", linewidth=2, color="blue")
    if vwap:
        ax.plot(dt.index, dt["VWAP"], label="VWAP", linewidth=2, color="yellow")

    #画出买入和卖出信号的三角形
    ax.plot(dt.index[s], dt["Close"][s], linestyle="None", marker="^", markersize=8, label="Sell", color="green")
    ax.plot(dt.index[b], dt["Close"][b], linestyle="None", marker="^", markersize=8, label="Buy", color="red")
    ax.plot(dt.index[c], dt["Close"][c], linestyle="None", marker="^", markersize=8, label="Close", color="yellow")

    #x轴设置为30分钟的间隔，并格式化为小时和分钟
    ticks = pd.date_range(dt.index[0], dt.index[-1], freq="30min")
    ax.set_xticks(ticks)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    ax.set_xlabel("Time", fontsize=10)
    ax.set_ylabel("Price", fontsize=10)
    ax.set_title(f"Price Action - {day}", fontsize=11, fontweight="bold")
    if show_legend:
        ax.legend(loc="best", fontsize=8, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis="x", rotation=45)
    return ax

#基于plot_line函数，创建多个日期的图
def plot_line_grid(df, days, vwap=False, ncols=5, figsize_per_plot=(4.6, 3.6)):
    
    days = list(days)
    if len(days) == 0:
        print("No days provided.")
        return

    #自动计算行数和列数，创建子图
    nrows = (len(days) + ncols - 1) // ncols
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(figsize_per_plot[0] * ncols, figsize_per_plot[1] * nrows),
        squeeze=False
    )
    axes_flat = axes.flatten()

    #遍历每个子图和对应的日期，画出价格走势、上下界和交易信号
    for ax, day in zip(axes_flat, days):
        plot_line(df, day, vwap=vwap, ax=ax, show_legend=False)

    for ax in axes_flat[len(days):]:
        ax.axis("off")

    handles, labels = axes_flat[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", ncol=min(5, len(labels)), fontsize=9)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
    else:
        fig.tight_layout()

    plt.show()





def plot_equity_with_halfyear_vix(
    price_index,
    equity_series_dict,
    df_vix,
    title="Strategy Equity Curves with Semiannual Average VIX",
    vix_col="Open",
    save_path=None,
):
    price_index = pd.to_datetime(price_index)
    vix = df_vix.copy()
    vix.index = pd.to_datetime(vix.index)

    start = price_index.min().normalize()
    end = price_index.max().normalize()
    vix = vix.loc[(vix.index >= start) & (vix.index <= end)]

    halfyear_vix = (
        vix[[vix_col]]
        .resample("2QS-JAN")
        .mean()
        .rename(columns={vix_col: "avg_vix"})
    )
    halfyear_vix["period_end"] = halfyear_vix.index + pd.offsets.MonthEnd(5)

    fig, (ax_equity, ax_vix) = plt.subplots(
        2,
        1,
        figsize=(14, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3.5, 1.2], "hspace": 0.08},
    )

    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#4c566a", "#d62728",  "#e377c2", "#7f7f7f", "#bcbd22"]
    for i, (label, series) in enumerate(equity_series_dict.items()):
        series = pd.Series(series, index=price_index) if not isinstance(series, pd.Series) else series
        series.index = pd.to_datetime(series.index)
        print(f" {i}  {palette[i]}")
        ax_equity.plot(
            series.index,
            series.values,
            label=label,
            linewidth=2.1 if "Buy and hold" not in label else 1.8,
            color=palette[i],
            alpha=0.95,
        )

    ax_equity.set_title(title, fontsize=13, fontweight="bold")
    ax_equity.set_ylabel("Portfolio Value", fontsize=10)
    ax_equity.grid(True, axis="y", alpha=0.25, linestyle="--")
    ax_equity.spines["top"].set_visible(False)
    ax_equity.spines["right"].set_visible(False)
    ax_equity.legend(loc="upper left", ncol=2, frameon=False, fontsize=9)

    if not halfyear_vix.empty:
        bar_width = np.diff(mdates.date2num(halfyear_vix["period_end"][:2])).mean() * 0.75 if len(halfyear_vix) > 1 else 120
        bars = ax_vix.bar(
            halfyear_vix.index,
            halfyear_vix["avg_vix"],
            width=bar_width,
            align="edge",
            color="#c9d7e3",
            edgecolor="#5b7285",
            linewidth=0.9,
            label="Avg VIX (Half-Year)",
        )
        ax_vix.plot(
            halfyear_vix.index + pd.offsets.MonthBegin(1),
            halfyear_vix["avg_vix"],
            color="#17324d",
            linewidth=1.6,
            marker="o",
            markersize=4,
        )

        for bar, value in zip(bars, halfyear_vix["avg_vix"]):
            ax_vix.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#17324d",
            )

    ax_vix.set_ylabel("Avg VIX", fontsize=10)
    ax_vix.set_xlabel("Date", fontsize=10)
    ax_vix.grid(True, axis="y", alpha=0.25, linestyle="--")
    ax_vix.spines["top"].set_visible(False)
    ax_vix.spines["right"].set_visible(False)

    locator = mdates.AutoDateLocator(maxticks=8)
    ax_vix.xaxis.set_major_locator(locator)
    ax_vix.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    fig.align_ylabels([ax_equity, ax_vix])
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()
    return fig, (ax_equity, ax_vix)


def plot_yearly_return_sharpe_table(
    equity_series_dict,
    rf_annual=0.01,
    min_obs=2,
    ax=None,
    title="Yearly Return And Sharpe Ratio",
):
    table_df = mme.yearly_metrics_table(
        equity_series_dict,
        rf_annual=rf_annual,
        min_obs=min_obs,
    )

    if table_df.empty:
        raise ValueError("No equity data provided for yearly metrics table")

    display_df = table_df.copy()
    display_df["return"] = display_df["return"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "")
    display_df["sharpe_ratio"] = display_df["sharpe_ratio"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    display_df["observations"] = display_df["observations"].astype(int)
    display_df.columns = ["Strategy", "Year", "Return", "Sharpe", "Obs"]

    nrows = len(display_df) + 1
    fig_height = max(2.2, 0.42 * nrows)

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, fig_height))
    else:
        fig = ax.figure

    ax.axis("off")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)

    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.35)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#dbe7f3")
            cell.set_text_props(weight="bold", color="#17324d")
        else:
            cell.set_facecolor("#f8fbff" if row % 2 else "#edf4fa")
        cell.set_edgecolor("#9eb6c8")

    fig.tight_layout()
    return fig, ax, table_df


def plot_yearly_return_sharpe_heatmap(
    equity_series_dict,
    rf_annual=0.01,
    min_obs=2,
    title="Annual Return And Sharpe Ratio by Strategy",
    return_cmap="RdYlGn",
    sharpe_cmap="RdYlGn",
    annotate=True,
):
    table_df = mme.yearly_metrics_table(
        equity_series_dict,
        rf_annual=rf_annual,
        min_obs=min_obs,
    )

    if table_df.empty:
        raise ValueError("No equity data provided for yearly metrics heatmap")

    return_matrix = table_df.pivot(index="strategy", columns="year", values="return")
    sharpe_matrix = table_df.pivot(index="strategy", columns="year", values="sharpe_ratio")

    # Keep a stable ordering for easier side-by-side comparison.
    strategy_order = list(equity_series_dict.keys())
    year_order = sorted(table_df["year"].unique())
    return_matrix = return_matrix.reindex(index=strategy_order, columns=year_order)
    sharpe_matrix = sharpe_matrix.reindex(index=strategy_order, columns=year_order)

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(max(12, 1.2 * len(year_order) + 4), max(7, 0.9 * len(strategy_order) + 4)),
        gridspec_kw={"hspace": 0.38},
    )
    ax_ret, ax_sharpe = axes

    ret_values = return_matrix.to_numpy(dtype=float)
    sharpe_values = sharpe_matrix.to_numpy(dtype=float)

    ret_abs_max = np.nanmax(np.abs(ret_values)) if np.isfinite(ret_values).any() else 0.1
    ret_abs_max = max(ret_abs_max, 0.1)
    sharpe_abs_max = np.nanmax(np.abs(sharpe_values)) if np.isfinite(sharpe_values).any() else 1.0
    sharpe_abs_max = max(sharpe_abs_max, 1.0)

    im_ret = ax_ret.imshow(
        ret_values,
        aspect="auto",
        cmap=return_cmap,
        vmin=-ret_abs_max,
        vmax=ret_abs_max,
    )
    im_sharpe = ax_sharpe.imshow(
        sharpe_values,
        aspect="auto",
        cmap=sharpe_cmap,
        vmin=-sharpe_abs_max,
        vmax=sharpe_abs_max,
    )

    for ax, matrix, subtitle in [
        (ax_ret, return_matrix, "Annual Return"),
        (ax_sharpe, sharpe_matrix, "Annual Sharpe"),
    ]:
        ax.set_title(subtitle, fontsize=12, fontweight="bold")
        ax.set_xticks(np.arange(len(year_order)))
        ax.set_xticklabels(year_order, rotation=45, ha="right")
        ax.set_yticks(np.arange(len(strategy_order)))
        ax.set_yticklabels(strategy_order)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.set_xticks(np.arange(-0.5, len(year_order), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(strategy_order), 1), minor=True)
        ax.grid(which="minor", color="white", linestyle="-", linewidth=1.3)

        if annotate:
            values = matrix.to_numpy(dtype=float)
            for i in range(values.shape[0]):
                for j in range(values.shape[1]):
                    value = values[i, j]
                    if np.isnan(value):
                        text = "-"
                        text_color = "#10212b"
                    elif subtitle == "Annual Return":
                        text = f"{value:.1%}"
                        text_color = "white" if abs(value) > 0.6 * ret_abs_max else "#10212b"
                    else:
                        text = f"{value:.2f}"
                        text_color = "white" if abs(value) > 0.6 * sharpe_abs_max else "#10212b"
                    ax.text(j, i, text, ha="center", va="center", fontsize=8, color=text_color)

    cbar_ret = fig.colorbar(im_ret, ax=ax_ret, fraction=0.03, pad=0.02)
    cbar_ret.set_label("Return", fontsize=9)
    cbar_ret.ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")

    cbar_sharpe = fig.colorbar(im_sharpe, ax=ax_sharpe, fraction=0.03, pad=0.02)
    cbar_sharpe.set_label("Sharpe", fontsize=9)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)
    fig.subplots_adjust(top=0.90, bottom=0.08, left=0.14, right=0.92, hspace=0.42)
    return fig, axes, {"return": return_matrix, "sharpe": sharpe_matrix}


def plot_yearly_return_sharpe_vix_heatmap(
    equity_series_dict,
    df_vix,
    rf_annual=0.01,
    min_obs=2,
    title="Annual Return, Sharpe Ratio, And Market Volatility",
    return_cmap="RdYlGn",
    sharpe_cmap="RdYlGn",
    vix_cmap="YlOrRd",
    vix_col="Open",
    annotate=True,
):
    table_df = mme.yearly_metrics_table(
        equity_series_dict,
        rf_annual=rf_annual,
        min_obs=min_obs,
    )

    if table_df.empty:
        raise ValueError("No equity data provided for yearly metrics heatmap")

    return_matrix = table_df.pivot(index="strategy", columns="year", values="return")
    sharpe_matrix = table_df.pivot(index="strategy", columns="year", values="sharpe_ratio")

    strategy_order = list(equity_series_dict.keys())
    year_order = sorted(table_df["year"].unique())
    return_matrix = return_matrix.reindex(index=strategy_order, columns=year_order)
    sharpe_matrix = sharpe_matrix.reindex(index=strategy_order, columns=year_order)

    vix = df_vix.copy()
    vix.index = pd.to_datetime(vix.index)
    if vix_col not in vix.columns:
        raise ValueError(f"df_vix must contain '{vix_col}' column")

    yearly_vix = vix[vix_col].dropna().groupby(vix.index.year).mean().reindex(year_order)
    vix_matrix = pd.DataFrame([yearly_vix.values], index=["Avg VIX"], columns=year_order)

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(max(12, 1.2 * len(year_order) + 4), max(9, 0.9 * len(strategy_order) + 6)),
        gridspec_kw={"hspace": 0.48, "height_ratios": [len(strategy_order), len(strategy_order), 1.2]},
    )
    ax_ret, ax_sharpe, ax_vix = axes

    ret_values = return_matrix.to_numpy(dtype=float)
    sharpe_values = sharpe_matrix.to_numpy(dtype=float)
    vix_values = vix_matrix.to_numpy(dtype=float)

    ret_abs_max = np.nanmax(np.abs(ret_values)) if np.isfinite(ret_values).any() else 0.1
    ret_abs_max = max(ret_abs_max, 0.1)
    sharpe_abs_max = np.nanmax(np.abs(sharpe_values)) if np.isfinite(sharpe_values).any() else 1.0
    sharpe_abs_max = max(sharpe_abs_max, 1.0)
    vix_min = np.nanmin(vix_values) if np.isfinite(vix_values).any() else 10.0
    vix_max = np.nanmax(vix_values) if np.isfinite(vix_values).any() else 40.0

    im_ret = ax_ret.imshow(
        ret_values,
        aspect="auto",
        cmap=return_cmap,
        vmin=-ret_abs_max,
        vmax=ret_abs_max,
    )
    im_sharpe = ax_sharpe.imshow(
        sharpe_values,
        aspect="auto",
        cmap=sharpe_cmap,
        vmin=-sharpe_abs_max,
        vmax=sharpe_abs_max,
    )
    im_vix = ax_vix.imshow(
        vix_values,
        aspect="auto",
        cmap=vix_cmap,
        vmin=vix_min,
        vmax=vix_max,
    )

    panels = [
        (ax_ret, return_matrix, "Annual Return"),
        (ax_sharpe, sharpe_matrix, "Annual Sharpe"),
        (ax_vix, vix_matrix, "Average VIX"),
    ]

    for ax, matrix, subtitle in panels:
        row_labels = matrix.index.tolist()
        col_labels = matrix.columns.tolist()
        ax.set_title(subtitle, fontsize=12, fontweight="bold")
        ax.set_xticks(np.arange(len(col_labels)))
        ax.set_xticklabels(col_labels, rotation=45, ha="right")
        ax.set_yticks(np.arange(len(row_labels)))
        ax.set_yticklabels(row_labels)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.set_xticks(np.arange(-0.5, len(col_labels), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(row_labels), 1), minor=True)
        ax.grid(which="minor", color="white", linestyle="-", linewidth=1.3)

        if annotate:
            values = matrix.to_numpy(dtype=float)
            for i in range(values.shape[0]):
                for j in range(values.shape[1]):
                    value = values[i, j]
                    if np.isnan(value):
                        text = "-"
                        text_color = "#10212b"
                    elif subtitle == "Annual Return":
                        text = f"{value:.1%}"
                        text_color = "white" if abs(value) > 0.6 * ret_abs_max else "#10212b"
                    elif subtitle == "Annual Sharpe":
                        text = f"{value:.2f}"
                        text_color = "white" if abs(value) > 0.6 * sharpe_abs_max else "#10212b"
                    else:
                        text = f"{value:.1f}"
                        threshold = vix_min + 0.6 * (vix_max - vix_min) if vix_max > vix_min else vix_max
                        text_color = "white" if value >= threshold else "#10212b"
                    ax.text(j, i, text, ha="center", va="center", fontsize=8, color=text_color)

    cbar_ret = fig.colorbar(im_ret, ax=ax_ret, fraction=0.03, pad=0.02)
    cbar_ret.set_label("Return", fontsize=9)
    cbar_ret.ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.0%}")

    cbar_sharpe = fig.colorbar(im_sharpe, ax=ax_sharpe, fraction=0.03, pad=0.02)
    cbar_sharpe.set_label("Sharpe", fontsize=9)

    cbar_vix = fig.colorbar(im_vix, ax=ax_vix, fraction=0.03, pad=0.02)
    cbar_vix.set_label("VIX", fontsize=9)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)
    fig.subplots_adjust(top=0.92, bottom=0.08, left=0.14, right=0.92, hspace=0.52)
    return fig, axes, {"return": return_matrix, "sharpe": sharpe_matrix, "vix": vix_matrix}



