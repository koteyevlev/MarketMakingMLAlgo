import pandas as pd
import numpy as np
import sys
import matplotlib.pyplot as plt
from sortedcontainers import SortedDict
import warnings
import math
from copy import deepcopy
from tqdm import tqdm
import matplotlib as mpl
import time
import datetime
from collections import Counter
from config_default import *
from algo_stats import *
from helpers import *

warnings.filterwarnings('ignore')
pd.options.display.max_rows = 10000

warnings.filterwarnings('ignore')
sys.setrecursionlimit(150000)

"""
Matching Engine
"""


class Matching_Engine:
    def __init__(self):
        self.bid = SortedDict()  # descending
        self.ask = SortedDict()
        self.bid_active_order = dict()
        self.ask_active_order = dict()
        self.bid_FIFO = dict()
        self.ask_FIFO = dict()
        self.day = None
        self.share_name = "LKOH"
        self.trade_log = []

    def check_order(self, data):
        if self.day != data["DATE"]:
            self.clean_dom()
            self.share_name = data["SECCODE"]
            self.day = data["DATE"]

        if data["ACTION"] == 1:
            return self.check_add(data, new_trades=[])
        elif data["ACTION"] == 2:
            pass
        else:
            self.delete_order(data)

    ## First part - adding order

    def check_add(self, data, rec_flag=False, new_trades=[]):
        if (len(self.ask) > 0 and data['BUYSELL'] == "B" and
            (data["PRICE"] >= self.ask.peekitem(0)[0] or data["PRICE"] < 0.000001)) or \
                (len(self.bid) > 0 and data['BUYSELL'] == "S" and data["PRICE"] <= self.bid.peekitem(-1)[0]):
            if not rec_flag:
                self.add_order(data)
            return self.trade(data, new_trades=new_trades)
        else:
            if not rec_flag:
                self.add_order(data)

    def add_order(self, data):
        if data['BUYSELL'] == "B":
            self.bid_active_order[data["ORDERNO"]] = (data["PRICE"], data["VOLUME"])
            if data["PRICE"] not in self.bid:
                self.bid[data["PRICE"]] = data["VOLUME"]
                self.bid_FIFO[data["PRICE"]] = [data["ORDERNO"]]
            else:
                self.bid[data["PRICE"]] += data["VOLUME"]
                self.bid_FIFO[data["PRICE"]].append(data["ORDERNO"])
        else:
            self.ask_active_order[data["ORDERNO"]] = (data["PRICE"], data["VOLUME"])
            if data["PRICE"] not in self.ask:
                self.ask[data["PRICE"]] = data["VOLUME"]
                self.ask_FIFO[data["PRICE"]] = [data["ORDERNO"]]
            else:
                self.ask[data["PRICE"]] += data["VOLUME"]
                self.ask_FIFO[data["PRICE"]].append(data["ORDERNO"])

    ## Second part - delete order

    def delete_order(self, data):
        if data['BUYSELL'] == "B":
            self.bid_FIFO[data["PRICE"]].pop(self.bid_FIFO[data["PRICE"]].index(data["ORDERNO"]))
            self.bid[data["PRICE"]] -= self.bid_active_order[data["ORDERNO"]][1]
            if len(self.bid_FIFO[data["PRICE"]]) < 1:
                del self.bid_FIFO[data["PRICE"]]
            del self.bid_active_order[data["ORDERNO"]]
            if self.bid[data["PRICE"]] < 0.000000001:
                del self.bid[data["PRICE"]]
        else:
            self.ask[data["PRICE"]] -= self.ask_active_order[data["ORDERNO"]][1]
            self.ask_FIFO[data["PRICE"]].pop(self.ask_FIFO[data["PRICE"]].index(data["ORDERNO"]))
            if len(self.ask_FIFO[data["PRICE"]]) < 1:
                del self.ask_FIFO[data["PRICE"]]
            del self.ask_active_order[data["ORDERNO"]]
            if self.ask[data["PRICE"]] < 0.000000001:
                del self.ask[data["PRICE"]]

    ## Third part - match order
    def trade(self, data, new_trades=[]):
        if data['BUYSELL'] == "B":
            return self.exec_buy_order(data, new_trades=new_trades)
        else:
            return self.exec_sell_order(data, new_trades=new_trades)

    def exec_sell_order(self, data, new_trades=[]):
        go_trade = True
        while go_trade:
            go_trade = False
            sell_order = self.ask_active_order[data["ORDERNO"]]
            tradeprice = self.bid.peekitem(-1)[0]
            order_no = self.bid_FIFO[tradeprice][0]
            if str(order_no)[0] == 'm':
                out_no = "mm_past"
            else:
                out_no = order_no
            buy_order = self.bid_active_order[order_no]
            if buy_order[1] > sell_order[1]:
                self.bid_active_order[order_no] = (self.bid_active_order[order_no][0],
                                                   buy_order[1] - sell_order[1])
                trade_vol = sell_order[1]
                self.bid[buy_order[0]] -= trade_vol
                self.delete_order(data)
            elif buy_order[1] == sell_order[1]:
                self.delete_order(data)
                tmp = dict()
                tmp["BUYSELL"] = "B"

                tmp["PRICE"] = buy_order[0]
                tmp["ORDERNO"] = order_no

                self.delete_order(tmp)
                trade_vol = sell_order[1]
            else:
                # iseberg or error
                tmp = dict()
                tmp["BUYSELL"] = "B"
                tmp["PRICE"] = buy_order[0]
                tmp["ORDERNO"] = order_no
                self.delete_order(tmp)
                trade_vol = buy_order[1]
                self.ask[sell_order[0]] -= trade_vol
                self.ask_active_order[data["ORDERNO"]] = (self.ask_active_order[data["ORDERNO"]][0],
                                                          sell_order[1] - buy_order[1])
                # TODO не учтено полное пробитие стакана!!
                if len(self.bid) == 0:
                    # reject стакан пробит
                    go_trade = False
                if self.bid.peekitem(-1)[0] >= sell_order[0] or data["PRICE"] < 0.000000001:
                    go_trade = True

            self.trade_log.append(
                [tradeprice, trade_vol, data["ORDERNO"], out_no, tradeprice * trade_vol, data["TIME"], data["NO"], "S"])
            new_trades.append(self.trade_log[-1])
            if buy_order[1] < 0 or sell_order[1] < 0:
                print("Maybe error", buy_order, sell_order)
                raise Exception(buy_order, sell_order)
            if go_trade:
                data["VOLUME"] -= trade_vol
                self.ask_active_order[data["ORDERNO"]] = (self.ask_active_order[data["ORDERNO"]][0], data["VOLUME"])
                # self.ask[data["PRICE"]] -= data["VOLUME"]
                # return self.check_add(data, rec_flag=True, new_trades=new_trades)
        return new_trades

    def exec_buy_order(self, data, new_trades=[]):
        go_trade = True
        while go_trade:
            go_trade = False
            buy_order = self.bid_active_order[data["ORDERNO"]]
            tradeprice = self.ask.peekitem(0)[0]
            order_no = self.ask_FIFO[tradeprice][0]
            if str(order_no)[0] == 'm':
                out_no = "mm_past"
            else:
                out_no = order_no
            sell_order = self.ask_active_order[order_no]
            if sell_order[1] > buy_order[1]:
                self.ask_active_order[order_no] = (self.ask_active_order[order_no][0],
                                                   sell_order[1] - buy_order[1])
                trade_vol = buy_order[1]
                self.ask[sell_order[0]] -= trade_vol
                self.delete_order(data)
            elif buy_order[1] == sell_order[1]:
                self.delete_order(data)
                tmp = dict()
                tmp["BUYSELL"] = "S"
                tmp["PRICE"] = sell_order[0]
                tmp["ORDERNO"] = self.ask_FIFO[tradeprice][0]
                self.delete_order(tmp)
                trade_vol = sell_order[1]
            else:
                # iseberg or error
                tmp = dict()
                tmp["BUYSELL"] = "S"
                tmp["PRICE"] = sell_order[0]
                tmp["ORDERNO"] = order_no
                self.delete_order(tmp)
                trade_vol = sell_order[1]
                self.bid[buy_order[0]] -= trade_vol
                self.bid_active_order[data["ORDERNO"]] = (self.bid_active_order[data["ORDERNO"]][0],
                                                          buy_order[1] - sell_order[1])
                if len(self.ask) == 0:
                    # reject стакан пробит
                    go_trade = False
                if self.ask.peekitem(0)[0] <= buy_order[0] or data["PRICE"] < 0.000000001:
                    go_trade = True

            # TODO Мне кажется здесь потенциальная ошибка, не предусмотрено что аркет мейкер заявка может в кого то удариться
            self.trade_log.append(
                [tradeprice, trade_vol, data["ORDERNO"], out_no, tradeprice * trade_vol, data["TIME"], data["NO"], "B"])
            new_trades.append(self.trade_log[-1])
            if buy_order[1] < 0 or sell_order[1] < 0:
                print("Maybe error", buy_order, sell_order)
                raise Exception(buy_order, sell_order)
            if go_trade:
                data["VOLUME"] -= trade_vol
                self.bid_active_order[data["ORDERNO"]] = (self.bid_active_order[data["ORDERNO"]][0], data["VOLUME"])
                # self.bid[data["PRICE"]] -= data["VOLUME"]
                return self.check_add(data, rec_flag=True, new_trades=new_trades)
        return new_trades

    ## Others

    def clean_dom(self):
        self.__init__()


"""
Basic MM
"""


class Basic_MM:
    def __init__(self, spread=0.005, barriers=None, sma_len=300, basic_volume=30, price_step=.1, cash=1000000):
        self.name = "Basic MM"
        self.cash = cash
        self.first_cash = cash
        self.equity = []
        self.time = []
        self.num_of_shares = 0
        self.spread = spread
        self.price_step = price_step
        # self.barriers = barriers
        self.sma_len = sma_len
        self.basic_volume = basic_volume
        self.baseline_price = None
        self.ask_price_1 = 0
        self.ask_volume_1 = 0
        self.bid_price_1 = 0
        self.bid_volume_1 = 0
        self.bid_order_num = 0
        self.ask_order_num = 0
        self.bid_lst = []
        self.ask_lst = []
        self.volume_lst = []
        self.bid_last_price = None
        self.ask_last_price = None
        self.last_trade_num = None
        self.trigger_time = None
        self.latency_moex = 3
        self.algo_params = "\n\nAlgo name - " + self.name + "\nSpread - " + str(spread * 100) + "%,\n" + \
                           "SMA tick length - " + str(sma_len) + ",\n" + "Order volume - " + str(basic_volume) + \
                           ",\nSpeed of orders - " + str(self.latency_moex) + "ms."
        self.share_name = "LKOH"

    def trading(self, dom, time=100000000, first_sma=0, is_plot=False, is_PL=False):
        if not self.baseline_price:
            if first_sma == 0:
                print("no first price")
                first_sma = dom.bid.peekitem(-1)
            self.share_name = dom.share_name
            self.create_pre_trade_value(first_sma)
            return self.generate_orders()
        else:
            if len(dom.trade_log) < 3:
                if not self.share_name:
                    self.share_name = dom.share_name
                    self.algo_params = "Share name - " + dom.share_name + self.algo_params
                self.equity.append(self.cash + self.num_of_shares * self.baseline_price)
            else:
                self.equity.append(self.cash + self.num_of_shares * dom.trade_log[-1][0])
            self.time.append(time // 100000)
            self.volume_lst.append(self.num_of_shares * self.baseline_price)
            if len(dom.trade_log) > 0:
                if self.last_trade_num == dom.trade_log[-1][-2]:
                    pass
                elif self.trigger_time == None:
                    self.trigger_time = int(dom.trade_log[-1][-3]) + self.latency_moex
                elif int(self.trigger_time) + 100 > time:
                    # print("dsf")
                    pass
                else:
                    # print(time)
                    self.trigger_time = None
                    self.last_trade_num = dom.trade_log[-1][-2]
                    self.calc_bid_ask(dom.trade_log)
                    self.bid_lst.append(self.bid_price_1)
                    self.ask_lst.append(self.ask_price_1)
                    return self.generate_orders(time)
            self.bid_lst.append(self.bid_price_1)
            self.ask_lst.append(self.ask_price_1)
        return []

    def create_pre_trade_value(self, first_sma):
        self.baseline_price = first_sma
        self.ask_price_1 = myround(first_sma * (1 + self.spread / 2), base=self.price_step[self.share_name])
        self.bid_price_1 = myround(first_sma * (1 - self.spread / 2), base=self.price_step[self.share_name])
        self.ask_volume_1 = self.basic_volume
        self.bid_volume_1 = self.basic_volume

    def calc_bid_ask(self, trade_log):
        if len(trade_log) < 3:
            pass
        else:
            # TODO trde log накапливается и эта операция становиться сложной
            self.baseline_price = np.array(trade_log[-self.sma_len:])[:, 0].astype(float).mean()
            self.ask_price_1 = myround(self.baseline_price * (1 + self.spread / 2),
                                       base=self.price_step[self.share_name])
            self.bid_price_1 = myround(self.baseline_price * (1 - self.spread / 2),
                                       base=self.price_step[self.share_name])
            self.ask_volume_1 = self.basic_volume
            self.bid_volume_1 = self.basic_volume

    def generate_orders(self, time=100000000):
        bid_cancel, ask_cancel, bid_place, ask_place = dict(), dict(), dict(), dict()
        bid_cancel["BUYSELL"] = "B"
        bid_place["BUYSELL"] = "B"
        ask_cancel["BUYSELL"] = "S"
        ask_place["BUYSELL"] = "S"
        bid_cancel["ACTION"] = 0
        bid_place["ACTION"] = 1
        ask_cancel["ACTION"] = 0
        ask_place["ACTION"] = 1

        if self.bid_last_price:
            bid_cancel["PRICE"] = self.bid_last_price
            bid_cancel["ORDERNO"] = "myorder" + str(self.bid_order_num)
            ask_cancel["PRICE"] = self.ask_last_price
            ask_cancel["ORDERNO"] = "myorder" + str(self.ask_order_num)
            self.bid_order_num += 1
            self.ask_order_num += 1

        bid_place["PRICE"] = self.bid_price_1
        ask_place["PRICE"] = self.ask_price_1
        bid_place["TIME"] = time
        ask_place["TIME"] = time
        bid_place["VOLUME"] = self.bid_volume_1
        ask_place["VOLUME"] = self.ask_volume_1
        bid_place["ORDERNO"] = "myorder" + str(self.bid_order_num)
        ask_place["ORDERNO"] = "myorder" + str(self.ask_order_num)
        bid_place["NO"] = "mm"
        ask_place["NO"] = "mm"
        self.bid_last_price = self.bid_price_1
        self.ask_last_price = self.ask_price_1

        if int(self.cash) < int(self.bid_price_1 * self.bid_volume_1):
            # print("No cash")
            return [ask_cancel, ask_place]
        elif int(self.cash) > int(self.ask_price_1 * self.ask_volume_1) + 2 * int(self.first_cash):
            # print("Too much shorts")
            return [bid_cancel, bid_place]
        elif self.bid_order_num != 0:
            return [bid_cancel, ask_cancel, bid_place, ask_place]
        else:
            return [bid_place, ask_place]

    def change_cash_share(self, new_trades):
        if not new_trades or len(new_trades) == 0 or new_trades[0] == None:
            return self.cash, self.num_of_shares
        trade_log = np.array(new_trades)

        active_exec = trade_log[np.where(trade_log[:, 6] == "mm")]
        passive_exec = trade_log[np.where(trade_log[:, 3] == "mm_past")]

        if active_exec.shape[0] + passive_exec.shape[0] == 0:
            return self.cash, self.num_of_shares
        if active_exec.shape[0] > 0:
            self.num_of_shares += np.sum(
                active_exec[np.where(active_exec[:, 7] == "B")][:, 1].astype(np.float)) - np.sum(
                active_exec[np.where(active_exec[:, 7] == "S")][:, 1].astype(np.float))
            self.cash += np.sum(active_exec[np.where(active_exec[:, 7] == "S")][:, 4].astype(np.float)) - np.sum(
                active_exec[np.where(active_exec[:, 7] == "B")][:, 4].astype(np.float))
        if passive_exec.shape[0] > 0:
            self.cash += np.sum(passive_exec[np.where(passive_exec[:, 7] == "B")][:, 4].astype(np.float)) - np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "S")][:, 4].astype(np.float))
            self.num_of_shares += np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "S")][:, 1].astype(np.float)) - np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "B")][:, 1].astype(np.float))

        return self.cash, self.num_of_shares


"""
Bollinger MM
"""


class Bollinger_Bands_MM:
    def __init__(self, spread=0.004, min_spread=0.004, sma_len=30, basic_volume=3, cash=1000000,
                 name="Bollinger Bands MM", price_step=.1, num_of_std=2, std_len=30):
        self.name = name
        self.cash = cash
        self.first_cash = cash
        self.equity = []
        self.time = []
        self.num_of_shares = 0
        self.spread = spread
        self.min_spread = min_spread
        self.spread_lst = []
        self.sma_len = sma_len
        self.std_len = std_len
        self.price_step = price_step
        self.basic_volume = basic_volume
        self.baseline_price = None
        self.baseline_lst = []
        self.volume_lst = []
        self.ask_lst = []
        self.bid_lst = []
        self.num_of_std = num_of_std
        self.ask_price_1 = 0
        self.ask_volume_1 = 0
        self.bid_price_1 = 0
        self.bid_volume_1 = 0
        self.bid_order_num = 0
        self.ask_order_num = 0
        self.bid_last_price = None
        self.ask_last_price = None
        self.last_trade_num = None
        self.trigger_time = None
        self.latency_moex = 3
        self.algo_params = "\n\nAlgo name - " + self.name + "\nMin spread - " + str(self.min_spread) + ",\n" + \
                           "ticks-" + str(sma_len) + ",\n" + "Volume -" + str(basic_volume) + \
                           "\nNum of std -" + str(self.num_of_std) + ",\nSpeed of orders - " + str(
            self.latency_moex) + "ms."
        self.share_name = "LKOH"

    def trading(self, dom, time=100000000, first_sma=0, is_plot=False, is_PL=False):
        if not self.baseline_price:
            self.share_name = dom.share_name
            self.create_pre_trade_value(first_sma)
            return self.generate_orders()
        else:
            if len(dom.trade_log) < 3:
                if not self.share_name:
                    self.share_name = dom.share_name
                    self.algo_params = "Share name - " + dom.share_name + self.algo_params
                self.equity.append(self.cash + self.num_of_shares * self.baseline_price)
            else:
                self.equity.append(self.cash + self.num_of_shares * dom.trade_log[-1][0])
            self.time.append(time // 100000)
            self.volume_lst.append(self.num_of_shares * self.baseline_price)
            if len(dom.trade_log) > 3:
                if self.last_trade_num == dom.trade_log[-1][-2]:
                    pass
                elif self.trigger_time == None:
                    self.trigger_time = int(dom.trade_log[-1][-3]) + self.latency_moex
                elif int(self.trigger_time) + 100 > time:
                    # print("dsf")
                    pass
                else:
                    # print(time)
                    self.trigger_time = None
                    self.last_trade_num = dom.trade_log[-1][-2]
                    self.calc_bid_ask(dom.trade_log)
                    self.bid_lst.append(self.bid_price_1)
                    self.ask_lst.append(self.ask_price_1)
                    return self.generate_orders(time)
            self.bid_lst.append(self.bid_price_1)
            self.ask_lst.append(self.ask_price_1)
        return []

    def create_pre_trade_value(self, first_sma):
        self.baseline_price = first_sma
        self.baseline_lst.append(self.baseline_price)
        self.ask_price_1 = myround(self.baseline_price * (1 + self.spread / 2), base=self.price_step[self.share_name])
        self.bid_price_1 = myround(self.baseline_price * (1 - self.spread / 2), base=self.price_step[self.share_name])
        self.ask_volume_1 = self.basic_volume
        self.bid_volume_1 = self.basic_volume

    def calc_bid_ask(self, trade_log):
        if len(trade_log) < 3:
            pass
        else:
            # TODO trde log накапливается и эта операция становиться сложной
            self.baseline_price = np.array(trade_log[-self.sma_len:])[:, 0].astype(float).mean()
            self.baseline_lst.append(self.baseline_price)
            std_len = min(len(self.baseline_lst), len(trade_log), self.std_len)
            self.spread = max((np.array(trade_log[-std_len:])[:, 0].astype(float) \
                               - np.array(self.baseline_lst[-std_len:])).std() * self.num_of_std,
                              self.baseline_price * self.min_spread)
            self.spread_lst.append(self.spread)
            self.ask_price_1 = myround(self.baseline_price + self.spread / 2, base=self.price_step[self.share_name])
            self.bid_price_1 = myround(self.baseline_price - self.spread / 2, base=self.price_step[self.share_name])
            self.ask_volume_1 = self.basic_volume
            self.bid_volume_1 = self.basic_volume

    def generate_orders(self, time=100000000):
        bid_cancel, ask_cancel, bid_place, ask_place = dict(), dict(), dict(), dict()
        bid_cancel["BUYSELL"] = "B"
        bid_place["BUYSELL"] = "B"
        ask_cancel["BUYSELL"] = "S"
        ask_place["BUYSELL"] = "S"
        bid_cancel["ACTION"] = 0
        bid_place["ACTION"] = 1
        ask_cancel["ACTION"] = 0
        ask_place["ACTION"] = 1

        if self.bid_last_price:
            bid_cancel["PRICE"] = self.bid_last_price
            bid_cancel["ORDERNO"] = "myorder" + str(self.bid_order_num)
            ask_cancel["PRICE"] = self.ask_last_price
            ask_cancel["ORDERNO"] = "myorder" + str(self.ask_order_num)
            self.bid_order_num += 1
            self.ask_order_num += 1

        bid_place["PRICE"] = self.bid_price_1
        ask_place["PRICE"] = self.ask_price_1
        bid_place["TIME"] = time
        ask_place["TIME"] = time
        bid_place["VOLUME"] = self.bid_volume_1
        ask_place["VOLUME"] = self.ask_volume_1
        bid_place["ORDERNO"] = "myorder" + str(self.bid_order_num)
        ask_place["ORDERNO"] = "myorder" + str(self.ask_order_num)
        bid_place["NO"] = "mm"
        ask_place["NO"] = "mm"
        self.bid_last_price = self.bid_price_1
        self.ask_last_price = self.ask_price_1

        if int(self.cash) < int(self.bid_price_1 * self.bid_volume_1):
            # print("No cash")
            return [ask_cancel, ask_place]
        elif int(self.cash) > int(self.ask_price_1 * self.ask_volume_1) + 2 * int(self.first_cash):
            # print("Too much shorts")
            return [bid_cancel, bid_place]
        elif self.bid_order_num != 0:
            return [bid_cancel, ask_cancel, bid_place, ask_place]
        else:
            return [bid_place, ask_place]

    def change_cash_share(self, new_trades):
        if not new_trades or len(new_trades) == 0 or new_trades[0] == None:
            return self.cash, self.num_of_shares

        trade_log = np.array(new_trades)

        active_exec = trade_log[np.where(trade_log[:, 6] == "mm")]
        passive_exec = trade_log[np.where(trade_log[:, 3] == "mm_past")]
        if active_exec.shape[0] + passive_exec.shape[0] == 0:
            return self.cash, self.num_of_shares
        if active_exec.shape[0] > 0:
            self.num_of_shares += np.sum(
                active_exec[np.where(active_exec[:, 7] == "B")][:, 1].astype(np.float)) - np.sum(
                active_exec[np.where(active_exec[:, 7] == "S")][:, 1].astype(np.float))
            self.cash += np.sum(active_exec[np.where(active_exec[:, 7] == "S")][:, 4].astype(np.float)) - np.sum(
                active_exec[np.where(active_exec[:, 7] == "B")][:, 4].astype(np.float))
        if passive_exec.shape[0] > 0:
            self.cash += np.sum(passive_exec[np.where(passive_exec[:, 7] == "B")][:, 4].astype(np.float)) - np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "S")][:, 4].astype(np.float))
            self.num_of_shares += np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "S")][:, 1].astype(np.float)) - np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "B")][:, 1].astype(np.float))

        return self.cash, self.num_of_shares


"""
Hard Correlation MM
"""


class Hard_Correlation_MM:
    def __init__(self, hyperparams, corr_matrix, spread_type='basic',
                 std_type="Basic", sigmoid_type="tanh", num_of_shares=2, cash=2000000, name="Hard Correlation MM"):
        self.name = name
        self.num_of_shares = num_of_shares
        self.share_names = list(hyperparams.keys())
        if isinstance(cash, int):
            self.cash = self.create_empty_dict(cash)
        else:
            self.cash = cash
        self.first_cash = cash
        self.portfolio_vol = self.create_empty_dict(0)
        self.q_max = self.create_q_max(hyperparams)
        self.sma_len = self.create_empty_dict(None)
        self.std_len = self.create_empty_dict(None)
        self.spread_type = spread_type
        self.sma_type = self.create_empty_dict(None)
        for share in self.share_names:
            self.sma_type[share] = hyperparams[share]["MA_type"]
            self.sma_len[share] = hyperparams[share]["tick"]
            self.std_len[share] = 100
        self.std_type = std_type
        self.sigmoid_type = sigmoid_type
        self.hyperparams = hyperparams
        self.corr_matrix = corr_matrix
        self.equity = self.create_empty_dict([])
        self.time = self.create_empty_dict([])
        self.volume_lst = self.create_empty_dict([])
        self.bid_order_num = self.create_empty_dict(0)
        self.ask_order_num = self.create_empty_dict(0)
        self.calc_params = self.pre_calc_params(hyperparams)
        self.bid_last_price = self.create_empty_dict(None)
        self.ask_last_price = self.create_empty_dict(None)
        self.last_trade_num = self.create_empty_dict(None)
        self.baseline_lst = self.create_empty_dict([])
        self.bid_lst = self.create_empty_dict([])
        self.ask_lst = self.create_empty_dict([])
        self.spread_lst = self.create_empty_dict([])
        self.trigger_time = self.create_empty_dict(None)
        self.latency_moex = 3
        # TODO algo_params
        hp_string = str(pd.DataFrame(hyperparams))

        corr_string = '     ' + ' '.join(map(str, self.share_names)) + '\n'
        for share in range(len(self.share_names)):
            corr_string += self.share_names[share] + '  ' + '  '.join(map(str, corr_matrix[share])) + '\n'

        self.algo_params = "\nAlgo name - " + self.name + "\nHyperparams - \n" + \
                           hp_string + '\n\nCorrelation matrix\n' + corr_string + "\nSpeed of orders - " + str(
            self.latency_moex) + "ms."

    def create_empty_dict(self, content):
        output = dict()
        for share in self.share_names:
            output[share] = deepcopy(content)
        return output

    def create_q_max(self, hyperparams):
        q_max = []
        for share in self.share_names:
            q_max.append(hyperparams[share]["q_max"])
        return q_max

    def pre_calc_params(self, hyperparams):
        params = dict()
        for share in self.share_names:
            params[share] = dict()
            params[share]["spread"] = hyperparams[share]["spread_max"]
            params[share]["baseline_price"] = hyperparams[share]["first_price"]
            # TODO округление
            params[share]["bid_price"] = params[share]["baseline_price"] - params[share]["spread"] / 2
            # TODO динамический объем если надо
            params[share]["ask_price"] = params[share]["baseline_price"] + params[share]["spread"] / 2
            params[share]["volume"] = hyperparams[share]["basic_volume"]
        return params

    def trading(self, doms, time=100000000):
        all_orders = []
        for share in self.share_names:
            dom = doms[share]
            if len(dom.trade_log) < 3:
                # if not self.share_name:
                #    self.share_name = dom.share_name
                #   self.algo_params = "Share name - " + dom.share_name + self.algo_params
                self.equity[share].append(
                    self.cash[share] + self.portfolio_vol[share] * self.calc_params[share]["baseline_price"])
            else:
                self.equity[share].append(self.cash[share] + self.portfolio_vol[share] * dom.trade_log[-1][0])
            self.time[share].append(time // 100000)
            self.volume_lst[share].append(self.portfolio_vol[share] * self.calc_params[share]["baseline_price"])
            if len(dom.trade_log) > 0:
                if self.last_trade_num[share] == dom.trade_log[-1][-2]:
                    pass
                elif self.trigger_time[share] == None:
                    self.trigger_time[share] = int(dom.trade_log[-1][-3]) + self.latency_moex
                elif int(self.trigger_time[share]) + 100 > time:
                    # print("dsf")
                    pass
                else:
                    # print(time)
                    self.trigger_time[share] = None
                    self.last_trade_num[share] = dom.trade_log[-1][-2]
                    self.calc_bid_ask(dom.trade_log, share)
                    all_orders.extend(self.generate_orders(share, time=time))
            self.bid_lst[share].append(self.calc_params[share]["bid_price"])
            self.ask_lst[share].append(self.calc_params[share]["ask_price"])
            self.baseline_lst[share].append(self.calc_params[share]["baseline_price"])
        return all_orders

    def calc_baseline_price(self, trade_log, share):
        if self.sma_type[share] == "SMA":
            # conservative
            return np.array(trade_log[-self.sma_len[share]:])[:, 0].astype(float).mean()
        elif self.sma_type[share] == "WMA":
            # middle
            leng = min(self.sma_len[share], len(trade_log))
            weights = np.arange(1, leng + 1)
            wmas = (np.array(trade_log[-leng:])[:, 0].astype(float) * weights) / weights.sum()
            return wmas.sum()
        elif self.sma_type[share] == "EMA":
            # aggresive
            # можно сделать оптимальнее, если хранить старое ema
            values = pd.DataFrame(np.array(trade_log[-self.sma_len[share]:])[:, 0].astype(float))
            # print(values.ewm(span=self.sma_len).mean())
            return values.ewm(span=self.sma_len[share]).mean().iat[-1, 0]
        else:
            # not implement
            raise Exception()

    def calc_volatility(self, trade_log, share):
        if self.std_type == "Basic":
            return np.array(trade_log[-self.std_len[share]:])[:, 0].astype(float).std()
        else:
            # Bollinger
            std_len = min(len(self.baseline_lst[share]), len(trade_log), self.sma_len[share])
            return (np.array(trade_log[-self.std_len[share]:])[:, 0].astype(float) \
                    - np.array(self.baseline_lst[-self.std_len[share]:])).std()

    def sigmoid(self, q_norm):
        if self.sigmoid_type == 'tanh':
            # normal
            return math.tanh(q_norm)
        elif self.sigmoid_type == "gauss":
            # aggrersive
            return math.erf(q_norm)
        elif self.sigmoid_type == "arctan":
            # conservative
            return (2 / math.pi) * math.atan(q_norm * math.pi / 2)
        else:
            # not implement
            raise Exception()

    def mean_q_corr(self, corr_vector, norm_q_lst):
        out = 0
        for i in range(len(corr_vector)):
            out += corr_vector[i] * self.sigmoid(norm_q_lst[i])
        return out / len(corr_vector)

    def bid_ask_spread(self, spread, share_index, share):
        norm_q_lst = [None] * len(self.share_names)
        for i in range(len(norm_q_lst)):
            norm_q_lst[i] = self.portfolio_vol[self.share_names[i]]
            norm_q_lst[i] = norm_q_lst[i] / self.q_max[i]
        # max_q_stock_change_index = np.argmax(
        #   np.absolute(np.array(norm_q_lst) * np.array(self.corr_matrix[share_index])))
        spread_bid = max(((1 + self.mean_q_corr(self.corr_matrix[share_index],
                                                norm_q_lst)) / 2 * spread), price_step[share] * 2)
        # TODO Здесь костыль с 0.5 очень влиятельный костыль
        if spread_bid < 0 or math.isnan(spread_bid):  # to check
            print('Spread Bid =', spread_bid, spread)
            print(self.mean_q_corr(self.corr_matrix[share_index], norm_q_lst))
            raise Exception

        spread_ask = spread - spread_bid
        # print(spread, spread_bid, spread_ask, (1 - self.corr_matrix[share_index][max_q_stock_change_index] * \
        #           (self.sigmoid(norm_q_lst[max_q_stock_change_index]))) / 2)
        # print((1 - self.corr_matrix[share_index][max_q_stock_change_index] * \
        #           (self.sigmoid(norm_q_lst[max_q_stock_change_index]))) / 2)
        return [spread_bid, spread_ask]

    def calc_bid_ask(self, trade_log, share):
        if len(trade_log) < 5:
            pass
        else:
            hp = self.hyperparams[share]
            self.calc_params[share]["baseline_price"] = self.calc_baseline_price(trade_log, share)

            if self.spread_type == "basic":
                std = self.calc_volatility(trade_log, share)
                spread = (hp["spread_max"] * hp["B"] * std + \
                          hp["spread_min"] * (hp["spread_max"] - hp["spread_min"])) / \
                         (hp["B"] * std + hp["spread_max"] - hp["spread_min"])
                if math.isnan(spread):
                    spread = hp["spread_min"]
            else:
                # Bollinger like spread
                std_len = min(len(self.baseline_lst[share]), len(trade_log), self.sma_len[share])
                spread = max((np.array(trade_log[-std_len:])[:, 0].astype(float) \
                              - np.array(self.baseline_lst[share][-std_len:])).std() * 2,
                             self.hyperparams[share]["min_spread"])

            self.spread_lst[share].append(spread)

            bid_ask_ind = self.bid_ask_spread(spread, self.share_names.index(share), share)

            # TODO!!!!! round разный везде
            self.calc_params[share]["bid_price"] = round(self.calc_params[share]["baseline_price"] - bid_ask_ind[0], 1)
            self.calc_params[share]["ask_price"] = round(self.calc_params[share]["baseline_price"] + bid_ask_ind[1], 1)
            self.calc_params[share]["volume"] = self.calc_params[share]["volume"]
            # print(self.calc_params[share]["bid_price"], self.calc_params[share]["baseline_price"], self.calc_params[share]["ask_price"])
            # print(bid_ask_ind, self.portfolio_vol)

    def generate_orders(self, share, time=100000000):
        bid_cancel, ask_cancel, bid_place, ask_place = dict(), dict(), dict(), dict()
        bid_cancel["BUYSELL"] = "B"
        bid_place["BUYSELL"] = "B"
        ask_cancel["BUYSELL"] = "S"
        ask_place["BUYSELL"] = "S"
        bid_cancel["ACTION"] = 0
        bid_place["ACTION"] = 1
        ask_cancel["ACTION"] = 0
        ask_place["ACTION"] = 1

        if self.bid_last_price[share]:
            bid_cancel["PRICE"] = self.bid_last_price[share]
            bid_cancel["ORDERNO"] = "myorder," + share + ',' + str(self.bid_order_num[share]) + ',' + 'b'

            ask_cancel["PRICE"] = self.ask_last_price[share]
            ask_cancel["ORDERNO"] = "myorder," + share + ',' + str(self.ask_order_num[share]) + ',' + 'a'
            self.bid_order_num[share] += 1
            self.ask_order_num[share] += 1

        bid_place["PRICE"] = self.calc_params[share]["bid_price"]
        ask_place["PRICE"] = self.calc_params[share]["ask_price"]
        bid_place["TIME"] = time
        ask_place["TIME"] = time
        bid_place["VOLUME"] = self.calc_params[share]["volume"]
        ask_place["VOLUME"] = self.calc_params[share]["volume"]
        bid_place["ORDERNO"] = "myorder," + share + ',' + str(self.bid_order_num[share]) + ',' + 'b'
        ask_place["ORDERNO"] = "myorder," + share + ',' + str(self.ask_order_num[share]) + ',' + 'a'
        bid_place["NO"] = "mm"
        ask_place["NO"] = "mm"
        self.bid_last_price[share] = self.calc_params[share]["bid_price"]
        self.ask_last_price[share] = self.calc_params[share]["ask_price"]

        if int(self.cash[share]) < int(self.calc_params[share]["bid_price"] * self.calc_params[share]["volume"]):
            # print("No cash")
            return [bid_cancel, ask_cancel, ask_place]
        elif int(self.cash[share]) > int(
                self.calc_params[share]["ask_price"] * self.calc_params[share]["volume"]) + 2 * int(self.first_cash):
            # print("Too much shorts")
            return [bid_cancel, ask_cancel, bid_place]
        elif self.bid_order_num[share] != 0:
            return [bid_cancel, ask_cancel, bid_place, ask_place]
        else:
            return [bid_place, ask_place]

    def change_cash_share(self, new_trades, share):
        if not new_trades or len(new_trades) == 0 or new_trades[0] == None:
            return self.cash[share], self.portfolio_vol[share]

        trade_log = np.array(new_trades)

        active_exec = trade_log[np.where(trade_log[:, 6] == "mm")]
        passive_exec = trade_log[np.where(trade_log[:, 3] == "mm_past")]
        if active_exec.shape[0] + passive_exec.shape[0] == 0:
            return self.cash[share], self.portfolio_vol[share]
        if active_exec.shape[0] > 0:
            self.portfolio_vol[share] += np.sum(
                active_exec[np.where(active_exec[:, 7] == "B")][:, 1].astype(np.float)) - np.sum(
                active_exec[np.where(active_exec[:, 7] == "S")][:, 1].astype(np.float))
            self.cash[share] += np.sum(active_exec[np.where(active_exec[:, 7] == "S")][:, 4].astype(np.float)) - np.sum(
                active_exec[np.where(active_exec[:, 7] == "B")][:, 4].astype(np.float))
        if passive_exec.shape[0] > 0:
            self.cash[share] += np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "B")][:, 4].astype(np.float)) - np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "S")][:, 4].astype(np.float))
            self.portfolio_vol[share] += np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "S")][:, 1].astype(np.float)) - np.sum(
                passive_exec[np.where(passive_exec[:, 7] == "B")][:, 1].astype(np.float))

        return self.cash[share], self.portfolio_vol[share]
