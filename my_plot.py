#图像函数
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

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
    ax.plot(dt.index[b], dt["Close"][c], linestyle="None", marker="^", markersize=8, label="Close", color="yellow")

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



