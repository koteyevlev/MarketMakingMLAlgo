import pandas as pd
import numpy as np
import sys
import os
import matplotlib.pyplot as plt
from sortedcontainers import SortedDict
import warnings
import math
from copy import deepcopy
from tqdm import tqdm
import matplotlib as mpl
from collections import Counter
warnings.filterwarnings('ignore')
pd.options.display.max_rows = 10000
import matplotlib.dates as mdates
from config_default import *
from helpers import *
import platform
from helpers import myround


def get_deal(raw):
    active_exec = raw[raw["NO"] == "mm"]
    passive_exec = raw[raw["NO"] != "mm"]

    bid_deal = pd.concat([active_exec[active_exec["BUYSELL"] == "B"], \
                          passive_exec[passive_exec["BUYSELL"] == "S"]])
    ask_deal = pd.concat([active_exec[active_exec["BUYSELL"] == "S"], \
                          passive_exec[passive_exec["BUYSELL"] == "B"]])

    return bid_deal["TIME"] // 100000, ask_deal["TIME"] // 100000, bid_deal["PRICE"], ask_deal["PRICE"]


def p_l_calc(raw, fair_price, share):
    # PL = Bought*(FP-AvgBid) + Sold*(AvgAsk-FP)
    active_exec = raw[raw["NO"] == "mm"]
    passive_exec = raw[raw["NO"] != "mm"]

    bought_vol = sum(active_exec[active_exec["BUYSELL"] == "B"]["VOLUME"]) + \
                 sum(passive_exec[passive_exec["BUYSELL"] == "S"]["VOLUME"])
    sold_vol = sum(active_exec[active_exec["BUYSELL"] == "S"]["VOLUME"]) + \
               sum(passive_exec[passive_exec["BUYSELL"] == "B"]["VOLUME"])

    if bought_vol >= 1:
        avg_bought = (sum(active_exec[active_exec["BUYSELL"] == "B"]["TURNOVER"]) + \
                      sum(passive_exec[passive_exec["BUYSELL"] == "S"]["TURNOVER"])) / bought_vol
    else:
        avg_bought = 0
    if sold_vol >= 1:
        avg_sold = (sum(active_exec[active_exec["BUYSELL"] == "S"]["TURNOVER"]) + \
                    sum(passive_exec[passive_exec["BUYSELL"] == "B"]["TURNOVER"])) / sold_vol
    else:
        avg_sold = 0

    return round(bought_vol * (fair_price - avg_bought) + sold_vol * (avg_sold - fair_price), 1), \
           bought_vol, sold_vol, myround(avg_bought, base=price_step[share]), myround(avg_sold, base=price_step[share])


def algo_stats(raw, fair_price, first_trade, algo, date, trade_log, dom, share="LKOH", bid_ask=False, show_deals=False):
    print("Stats for date -", date)
    print("Algo Params: ")
    print(algo.algo_params)
    print()
    print("Num of trades - ", raw.shape[0])
    print("Algo turnover - ", round(sum(raw["PRICE"] * raw["VOLUME"]), 1))
    p_l, bought_vol, sold_vol, avg_bought, avg_sold = p_l_calc(raw, fair_price, share)
    print("P&L Gross - ", p_l)
    print("P&L Net(with commision) -", round(p_l - sum(raw["PRICE"] * raw["VOLUME"]) * 0.00008, 1))
    print("Num of bought - ", bought_vol)
    print("Weighted average bought price - ", avg_bought)
    print("Num of sold - ", sold_vol)
    print("Weighted average sold price - ", avg_sold)
    print("Open Price - ", first_trade)
    print("Close price - ", dom.trade_log[-1][0])
    print("Initial cash - ", algo.first_cash)
    print("Total Return - ", round(100 * p_l / algo.first_cash, 2), "%", sep="")
    mpl.style.use("seaborn")
    fig, axs = plt.subplots(nrows=2, ncols=2, figsize=(20, 12))
    axs[0, 0].set_title(
        algo.name + ' - Algo Equity in % at ' + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:], size=16)
    if algo.name[:4] != "Hard":
        print("End Cash - ", round(algo.cash))
        print("End Equity - ", round(algo.cash + (bought_vol - sold_vol) * fair_price))
        print("Max day Drawdown - ", round((min(algo.equity) / algo.first_cash - 1) * 100, 2), "%", sep='')
        #print(pd.to_datetime(pd.Series(algo.time).astype(str).str[:4], format="%H%M"))
        axs[0, 0].plot(pd.to_datetime(pd.Series(algo.time).astype(str).str[:4], format="%H%M"),
                       np.array(algo.equity) / algo.first_cash * 100)
        axs[0, 1].set_title(share + " Price at " + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:], size=16)
        axs[1, 0].plot(pd.to_datetime(pd.Series(algo.time).astype(str).str[:4], format="%H%M"), np.array(algo.volume_lst))

    else:
        print("End Cash - ", round(algo.cash[share]))
        print("End Equity - ", round(algo.cash[share] + (bought_vol - sold_vol) * fair_price))
        print("Max day Drawdown - ", round((min(algo.equity[share]) / algo.first_cash - 1) * 100, 2), "%", sep='')
        axs[0, 0].plot(pd.to_datetime(pd.Series(algo.time[share]).astype(str).str[:4], format="%H%M"),
                       np.array(algo.equity[share]) / algo.first_cash * 100)
        axs[0, 1].set_title(share + " Bid/Ask Pricing at " + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:],
                            size=16)
        axs[1, 0].plot(pd.to_datetime(pd.Series(algo.time[share]).astype(str).str[:4], format="%H%M"),
                       np.array(algo.volume_lst[share]))

    axs[0, 1].plot(pd.to_datetime(trade_log["TIME"], format="%H%M%S%f"), trade_log["PRICE"])
    if bid_ask:
        if algo.name[:4] == "Hard":
            axs[0, 1].plot(pd.to_datetime(pd.Series(algo.time[share]).astype(str).str[:4], format="%H%M"),
                           np.array(algo.bid_lst[share]), color="green", label="Bid")
            axs[0, 1].plot(pd.to_datetime(pd.Series(algo.time[share]).astype(str).str[:4], format="%H%M"),
                           np.array(algo.ask_lst[share]), color="red", label="Ask")
        else:
            axs[0, 1].plot(pd.to_datetime(pd.Series(algo.time).astype(str).str[:4], format="%H%M"), np.array(algo.bid_lst),
                           color="green", label="Bid")
            axs[0, 1].plot(pd.to_datetime(pd.Series(algo.time).astype(str).str[:4], format="%H%M"), np.array(algo.ask_lst),
                           color="red", label="Ask")

        # axs[0, 1].scatter(pd.to_datetime(pd.Series(algo.time[share]).astype(str), format="%H%M"), np.array(algo.baseline_lst[share]))
    axs[1, 0].set_title(share + ' - Algo Volume in cash ' + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:],
                        size=16)
    axs[0, 0].set_xlabel('Time')
    axs[0, 0].set_ylabel('% of equity')
    axs[0, 1].set_xlabel('Time')
    axs[0, 1].set_ylabel('Price')
    axs[1, 0].set_xlabel('Time')
    axs[1, 0].set_ylabel('Portfolio equity')
    axs[1, 1].set_xlabel('Time')
    axs[1, 1].set_ylabel('Price')
    axs[1, 1].set_title(share + ' - Bid/Ask Deal ' + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:],
                        size=16)
    time_bid, time_ask, bid_deal, ask_deal = get_deal(raw)
    axs[1, 1].scatter(pd.to_datetime(pd.Series(time_bid).astype(str).str[:4], format="%H%M"), np.array(bid_deal), color="green",
                      label="Bid")
    axs[1, 1].scatter(pd.to_datetime(pd.Series(time_ask).astype(str).str[:4], format="%H%M"), np.array(ask_deal), color="red",
                      label="Ask")
    axs[1, 1].legend(fontsize=13)
    if show_deals:
        axs[0, 1].scatter(pd.to_datetime(pd.Series(time_bid).astype(str).str[:4], format="%H%M"), np.array(bid_deal),
                          color="darkgreen", label="Bid deal")
        axs[0, 1].scatter(pd.to_datetime(pd.Series(time_ask).astype(str).str[:4], format="%H%M"), np.array(ask_deal),
                          color="darkred", label="Ask deal")
    axs[0, 1].legend(fontsize=13)
    myFmt = mdates.DateFormatter('%H:%M')
    axs[0, 0].xaxis.set_major_formatter(myFmt)
    axs[0, 1].xaxis.set_major_formatter(myFmt)
    axs[1, 0].xaxis.set_major_formatter(myFmt)
    axs[1, 1].xaxis.set_major_formatter(myFmt)
    """
    if platform.system() == "Darwin":
        if algo.name == "Hard Correlation MM":
            try:
                os.mkdir("png_res/" + algo.name + share_corr[0] + algo.sma_type[share_corr[0]] + str(algo.sma_len[share_corr[1]]) + share_corr[1] + algo.sma_type[share_corr[1]] \
                        + str(algo.sma_len[share_corr[1]]) + algo.sigmoid_type)
            except:
                print("Dir exist")
            #plt.savefig("png_res/" + algo.name + share_corr[0]  + algo.sma_type[share_corr[0]] + str(algo.sma_len[share_corr[0]]) + share_corr[1] + algo.sma_type[share_corr[1]] \
            #            + str(algo.sma_len[share_corr[0]]) + algo.sigmoid_type + "/" + share + str(date) + " P&L - " + str(p_l) +'.png')
        else:
            try:
                #os.mkdir("png_res/" + algo.algo_params[14:114])
                print("create_dir")
            except:
                print("Dir exist")
            #plt.savefig("png_res/" + algo.algo_params[14:114] + '/' + share + date + " P&L - " + str(p_l) +'.png')
    #else:
        #plt.savefig("D:\\tsclientMMzip\\png_res\\" + algo.name + share + date + "P&L-" + str(p_l) + '.png')
        """

    plt.show()
    plt.clf()
    plt.close()


def day_stats(raw, fair_price, first_trade, algo, date, dom, share=None):
    output = dict()
    output["Date"] = date
    output["Num_of_trades"] = raw.shape[0]
    output["Algo_turnover"] = round(sum(raw["PRICE"] * raw["VOLUME"]), 1)
    p_l, bought_vol, sold_vol, avg_bought, avg_sold = p_l_calc(raw, fair_price, share)
    output["P&L"] = p_l
    output["Num_of_bought"] = bought_vol
    output["WA_bought_price"] = avg_bought
    output["Num_of_sold"] = sold_vol
    output["WA_sold_price"] = avg_sold
    output["Open_Price"] = first_trade
    output["Close_price"] = dom.trade_log[-1][0]
    output["Initial_cash"] = algo.first_cash

    if algo.name[:4] != "Hard":
        try:
            output["Mean_position"] = sum(algo.volume_lst) / len(algo.volume_lst)
        except:
            print("problem with mean position")
        output["End_Cash"] = algo.cash
        output["End_Equity"] = algo.cash + (bought_vol - sold_vol) * fair_price
        try:
            output["Max_day_drawdown"] = round((min(algo.equity) / algo.first_cash - 1) * 100, 2)
        except:
            print("Trouble with max day drawdown")
            output["Max_day_drawdown"] = 0
    else:
        output["End_Cash"] = algo.cash[share]
        output["End_Equity"] = algo.cash[share] + (bought_vol - sold_vol) * fair_price
        output["Max_day_drawdown"] = round((min(algo.equity[share]) / algo.first_cash - 1) * 100, 2)

    output["Total_Return"] = 100 * p_l / algo.first_cash
    return output


def advance_stats(res_log, risk_free=0.000):
    df = res_log.copy()
    df['downside_returns'] = 0
    df.loc[df['Total_Return'] < risk_free, 'downside_returns'] = df['Total_Return'] ** 2
    expected_return = df['Total_Return'].mean()
    down_stdev = np.sqrt(df['downside_returns'].mean())
    sortino_ratio = (expected_return - risk_free) / down_stdev
    sharp_ratio = (res_log["Total_Return"].mean() - risk_free) / res_log["Total_Return"].std()
    total_return = (np.prod(np.array((100 + res_log["Total_Return"]) / 100)) - 1) * 100
    duration = (pd.to_datetime(res_log.index, format="%Y%m%d")[-1] - pd.to_datetime(res_log.index, format="%Y%m%d")[
        0]).days
    geom_return = ((1 + total_return / 100) ** (1 / duration) - 1) * 100
    p_l = res_log["P&L"].sum()
    buy_and_hold = ((res_log["Open_Price"][res_log.index[-1]] - res_log["Open_Price"][res_log.index[0]]) /
                    res_log["Open_Price"][res_log.index[0]]) * 100
    return sharp_ratio, sortino_ratio, geom_return, total_return, duration, p_l, buy_and_hold


def year_stats(res_log, algo, risk_free=0.00, share=None):
    print("Stats for date -", res_log.index[0], '-', res_log.index[-1])
    sharp_ratio, sortino_ratio, geom_return, \
    total_return, duration, p_l, buy_and_hold = advance_stats(res_log, risk_free)
    actual_equity = algo.first_cash
    equity_lst = []
    for i in res_log["Total_Return"]:
        equity_lst.append(actual_equity * (1 + i / 100))
        actual_equity = equity_lst[-1]
    max_draw_lst = [None] * len(equity_lst)
    for i in range(len(equity_lst)):
        max_draw_lst[i] = 100 * (min(equity_lst[i:]) - equity_lst[i]) / equity_lst[i]
        # peak_valley = 100*(min(equity_lst) - max(equity_lst)) / max(equity_lst)
    peak_valley = min(max_draw_lst)

    print("Algo Params: ")
    print(algo.algo_params)
    print("Duration -", duration, "days")
    print("Initial cash -", algo.first_cash)
    print()
    print("Algo Turnover -", round(res_log["Algo_turnover"].sum()))
    print("P&L Net -", round(p_l - round(res_log["Algo_turnover"].sum()) * 0.00008))
    print("P&L Gross -", round(p_l))
    print("Total algo return gross - ", round(total_return, 2), "%", sep='')
    print("Buy & Hold Return - ", round(buy_and_hold, 2), "%", sep='')
    if not share:
        share = algo.share_name
    print("Begin price of", share, "-", res_log["Open_Price"][res_log.index[0]])
    print("End price of", share, "-", res_log["Open_Price"][res_log.index[-1]])
    print("Geometric mean Day Return - ", round(geom_return, 2), "%", sep='')
    print("Sharp ratio -", round(sharp_ratio, 2))
    print("Sortino ratio -", round(sortino_ratio, 2))
    print("Calmar ratio -", -round(geom_return / peak_valley, 2))
    print("Max Drawdown at day - ", min(res_log["Max_day_drawdown"]), "%", sep='')
    print("Peak to Valley Drawdown - ", round(min(total_return, peak_valley), 2), '%', sep='')
    print("Equity final -", round(equity_lst[-1]))
    print("Equity peak -", round(max(equity_lst)))
    fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(20, 10))
    date = res_log.index[0]
    end_date = res_log.index[-1]
    axs[0].set_title(algo.name + ' - Algo Equity in % at ' + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:] \
                     + "-" + str(end_date)[:4] + "/" + str(end_date)[4:6] + "/" + str(end_date)[6:], size=16)
    axs[0].plot(pd.to_datetime(res_log.index, format="%Y%m%d"), np.array(equity_lst) / algo.first_cash * 100)
    axs[1].set_title(share + " Price at " + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:] \
                     + "-" + str(end_date)[:4] + "/" + str(end_date)[4:6] + "/" + str(end_date)[6:], size=16)
    axs[1].plot(pd.to_datetime(res_log.index, format="%Y%m%d"), res_log["Open_Price"])
    axs[0].set_xlabel('')
    axs[0].set_ylabel('% of equity')
    axs[1].set_xlabel('Time')
    axs[1].set_ylabel('Price')
    plt.show()
    plt.clf()


def compare_algo(res_lst, algo_lst, risk_free=0.00, share="LKOH"):
    print("Stats for date -", res_lst[0].index[0], '-', res_lst[0].index[-1])
    print("Algo Info: ")
    for i in range(len(algo_lst)):
        print(i + 1, ') ', algo_lst[i].algo_params, sep='')
        print()
    stat_res = dict()
    for i in range(len(res_lst)):
        res_log = res_lst[i]
        algo = algo_lst[i]
        algo_res = dict()
        sharp_ratio, sortino_ratio, geom_return, \
        total_return, duration, p_l, buy_and_hold = advance_stats(res_log, risk_free)
        actual_equity = algo.first_cash
        equity_lst = [actual_equity]
        for i in res_log["Total_Return"]:
            equity_lst.append(actual_equity * (1 + i / 100))
            actual_equity = equity_lst[-1]
        max_draw_lst = [None] * len(equity_lst)
        for i in range(len(equity_lst)):
            max_draw_lst[i] = 100 * (min(equity_lst[i:]) - equity_lst[i]) / equity_lst[i]
            # peak_valley = 100*(min(equity_lst) - max(equity_lst)) / max(equity_lst)
        peak_valley = min(max_draw_lst)

        algo_res["Duration"] = duration
        algo_res["Initial cash"] = algo.first_cash
        algo_res["Algo Turnover"] = str(int(res_log["Algo_turnover"].sum()))
        algo_res["P&L Net"] = round(p_l - round(res_log["Algo_turnover"].sum()) * 0.00008)
        algo_res["P&L Gross"] = round(p_l)
        algo_res["Total algo return gross"] = str(round(total_return, 2)) + "%"
        algo_res["Buy & Hold Return"] = str(round(buy_and_hold, 2)) + "%"
        if not share:
            share = algo.share_name
        algo_res["Geometric mean Day Return"] = str(round(geom_return, 2)) + "%"
        algo_res["Sharp ratio"] = round(sharp_ratio, 2)
        algo_res["Sortino ratio"] = round(sortino_ratio, 2)
        algo_res["Calmar ratio"] = -round(geom_return / peak_valley, 2)
        algo_res["Max Drawdown at day"] = str(min(res_log["Max_day_drawdown"])) + "%"
        algo_res["Peak to Valley Drawdown"] = str(round(min(total_return, peak_valley), 2)) + '%'
        algo_res["Equity final"] = round(equity_lst[-1])
        algo_res["Equity peak"] = round(max(equity_lst))
        stat_res[algo.name] = algo_res

    fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(20, 10))
    date = res_log.index[0]
    end_date = res_log.index[-1]
    axs[0].set_title('Comparing Algo Equity in % at ' + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:] \
                     + "-" + str(end_date)[:4] + "/" + str(end_date)[4:6] + "/" + str(end_date)[6:], size=16)
    for i in range(len(res_lst)):
        actual_equity = algo_lst[i].first_cash
        equity_lst = [actual_equity]
        for j in res_lst[i]["Total_Return"]:
            equity_lst.append(actual_equity * (1 + j / 100))
            actual_equity = equity_lst[-1]
        times = pd.to_datetime(pd.concat([pd.Series(int(res_lst[i].index[0]) - 1), pd.Series(res_lst[i].index)]),
                               format="%Y%m%d")
        axs[0].plot(times, np.array(equity_lst) / algo_lst[i].first_cash * 100, label=algo_lst[i].name)
    axs[1].set_title(share + " Price at " + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:] \
                     + "-" + str(end_date)[:4] + "/" + str(end_date)[4:6] + "/" + str(end_date)[6:], size=16)
    axs[1].plot(pd.to_datetime(res_log.index, format="%Y%m%d"), res_log["Open_Price"])
    axs[0].set_xlabel('')
    axs[0].legend()
    axs[0].set_ylabel('% of equity')
    axs[1].set_xlabel('Time')
    axs[1].set_ylabel('Price')
    plt.show()
    plt.clf()
    return (pd.DataFrame(stat_res))


def multystock_stat(res_lst, algo, share_lst, risk_free=0.000):
    print("Stats for date -",res_lst[0].index[0], '-', res_lst[0].index[-1])
    print("Algo Info: ")
    print(algo.algo_params, sep='')
    print()

    stat_res = dict()
    for i in range(len(res_lst)):
        res_log = res_lst[i]
        algo_res = dict()
        sharp_ratio, sortino_ratio, geom_return, \
        total_return, duration, p_l, buy_and_hold = advance_stats(res_log, risk_free)
        actual_equity = algo.first_cash
        equity_lst = [actual_equity]
        for j in res_log["Total_Return"]:
            equity_lst.append(actual_equity * (1 + j / 100))
            actual_equity = equity_lst[-1]
        max_draw_lst = [None] * len(equity_lst)
        for j in range(len(equity_lst)):
            max_draw_lst[j] = 100*(min(equity_lst[j:]) - equity_lst[j]) / equity_lst[j]
        #peak_valley = 100*(min(equity_lst) - max(equity_lst)) / max(equity_lst)
        peak_valley = min(max_draw_lst)

        algo_res["Duration"] = duration
        algo_res["Initial cash"] = algo.first_cash
        algo_res["Algo Turnover"] = str(int(res_log["Algo_turnover"].sum()))
        algo_res["P&L Net"] = round(p_l - round(res_log["Algo_turnover"].sum()) * 0.00008)
        algo_res["P&L Gross"] = round(p_l)
        algo_res["Total algo return gross"] = str(round(total_return, 2)) + "%"
        algo_res["Buy & Hold Return"] = str(round(buy_and_hold, 2)) + "%"
        algo_res["Geometric mean Day Return"] = str(round(geom_return, 2)) + "%"
        algo_res["Sharp ratio"] = round(sharp_ratio, 2)
        algo_res["Sortino ratio"] = round(sortino_ratio, 2)
        algo_res["Calmar ratio"] = -round(geom_return / peak_valley, 2)
        algo_res["Max Drawdown at day"] = str(min(res_log["Max_day_drawdown"])) + "%"
        algo_res["Peak to Valley Drawdown"] = str(round(min(total_return, peak_valley), 2)) + '%'
        algo_res["Equity final"] = round(equity_lst[-1])
        algo_res["Equity peak"] = round(max(equity_lst))
        stat_res[share_lst[i]] = algo_res
    #return (pd.DataFrame(stat_res))
    fig, axs = plt.subplots(nrows=2, ncols=1, figsize=(20,10))
    date = res_lst[0].index[0]
    end_date = res_lst[0].index[-1]
    axs[0].set_title('Comparing Share Results in % at ' + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:]\
                     + "-" + str(end_date)[:4] + "/" + str(end_date)[4:6] + "/" + str(end_date)[6:], size=16)
    for i in range(len(res_lst)):
        actual_equity = algo.first_cash
        equity_lst = [actual_equity]
        for j in res_lst[i]["Total_Return"]:
            equity_lst.append(actual_equity * (1 + j / 100))
            actual_equity = equity_lst[-1]
        times = pd.to_datetime(pd.concat([pd.Series(int(res_lst[i].index[0]) - 1), pd.Series(res_lst[i].index)]), format="%Y%m%d")
        axs[0].plot(times, np.array(equity_lst) / algo.first_cash * 100, label=share_lst[i])
    axs[1].set_title(share_lst[0] + " Price at " + str(date)[:4] + "/" + str(date)[4:6] + "/" + str(date)[6:] \
                     + "-" + str(end_date)[:4] + "/" + str(end_date)[4:6] + "/" + str(end_date)[6:], size=16)
    axs[1].plot(pd.to_datetime(res_lst[0].index, format="%Y%m%d"), res_lst[0]["Open_Price"])
    axs[0].set_xlabel('')
    axs[0].legend()
    axs[0].set_ylabel('% of equity')
    axs[1].set_xlabel('Time')
    axs[1].set_ylabel('Price')
    plt.show()
    plt.clf()
    print(pd.DataFrame(stat_res).T)
