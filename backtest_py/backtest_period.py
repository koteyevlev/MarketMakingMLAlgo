from algo_classes import *
from helpers import create_empty_dict
import platform
from path_generator import path_generator_by_date
warnings.filterwarnings('ignore')
pd.options.display.max_rows = 10000



def backtest_day(all_params, share, show_stat):
    date, fol, dom, start_time, algo = all_params[0], all_params[1], all_params[2], all_params[3], all_params[4]

    if platform.system() == "Darwin":
        isebergs = pd.read_csv("/Users/a185583357/Desktop/MOEX/OrderLog" + date + "/isebergs_" + share + date + ".csv",
                               index_col=0).to_dict()["vol"]
    else:
        isebergs = pd.read_csv(path_generator_by_date(date) + "OrderLog" + date + "\isebergs_" + share + date  + ".csv",
                    index_col=0).to_dict()["vol"]
    fol = fol[fol["ACTION"] != 2]
    fol["DATE"] = date
    records = fol.to_dict("records")
    algo.first_price = max(records[1000]["PRICE"], records[1001]["PRICE"], records[1002]["PRICE"])
    errors = 0
    algo_errors = 0
    algo_orders = None

    # print("Num of icebergs - ", len(isebergs), "\nStart of market simulation")
    for i in tqdm(range(len(records))):
        record = records[i].copy()
        if algo_orders and int(record["TIME"]) > algo_orders[-1]["TIME"] + latency:
            out_algo = []
            for order in algo_orders:
                order["DATE"] = date
                try:
                    out = dom.check_order(order)
                    if out:
                        out_algo.extend(out)
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except Exception as e:
                    if order["ACTION"] == 1:
                        #dom.check_order(order)
                        print("MAYBE Some problem, cant add order. Exc - ", e, sys.exc_info())
                        print(e, sys.exc_info())
                    algo_errors += 1
            algo_orders = None
            if len(out_algo) > 0:
                algo.change_cash_share(out_algo)

        if record["ACTION"] == 1 and record["ORDERNO"] in isebergs:
            record["VOLUME"] = isebergs[record["ORDERNO"]]
        try:
            out = dom.check_order(record)
            algo.change_cash_share(out)
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            errors += 1
        if not algo_orders:
            algo_orders = algo.trading(dom, time=record["TIME"],
                                       first_sma=max(records[1000]["PRICE"], records[1001]["PRICE"]))
    print("Num of historic reject - ", errors, ", algo reject - ", algo_errors)
    print("Share -", share, datetime.datetime.now())
    print("--- %s overall seconds ---" % (time.time() - start_time))

    trade_log = pd.DataFrame((dom.trade_log),
                             columns=["PRICE", 'VOLUME', 'NEW-ORDER-ID', 'PAST-ORDER-ID', "TURNOVER", "TIME", 'NO',
                                      'BUYSELL'])

    algo_raw = pd.concat([trade_log[trade_log["NEW-ORDER-ID"].apply(isinstance, args=(str,))],
                          trade_log[trade_log["PAST-ORDER-ID"].apply(isinstance, args=(str,))]])
    if show_stat:
        #try:
            algo_stats(algo_raw, dom.trade_log[-1][0], dom.trade_log[0][0], algo, date, trade_log, dom, share=share,
                       bid_ask=True, show_deals=True)
        #except Exception as e:
         #   print("\n\n\nSome problems with algo stats\n Exception - ", e, "\n\n\n")
    else:
        print(date)
    return day_stats(algo_raw, dom.trade_log[-1][0], dom.trade_log[0][0], algo, date, dom, share=share)


def get_day_data(date):
    if platform.system() == "Darwin":
        super_fol = pd.read_csv("/Users/a185583357/Desktop/MOEX/OrderLog" + date + "/OrderLog" + date + ".txt",
                                sep=",")
    else:
        try:
            super_fol = pd.read_csv(path_generator_by_date(date) + "/OrderLog" + date + "/OrderLog" + date + ".txt",
                                    sep=",")
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            super_fol = pd.read_csv(path_generator_by_date(date) + "/OrderLog" + date + ".txt",
                                    sep=",")
    print("Get Order log at date" + str(date))
    return super_fol


def backtest_year(date, dom, algo, share="LKOH", enddate="20160301", show_stat=False):
    out = SortedDict()
    arg_list = []
    stat_list = []
    total_skip = 0
    while date != enddate:
        start_time = time.time()
        date_fst = datetime.datetime.strptime(date, "%Y%m%d")
        date = (date_fst + datetime.timedelta(days=1)).strftime("%Y%m%d")
        if algo.name in bad_days and share in bad_days[algo.name] and int(date) in bad_days[algo.name][share]:
            print("this date ", date,  " is bad for this stock. Date will be skipped")
            continue
        # print(date)
        try:
            super_fol = get_day_data(date)
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            continue
        lkoh = super_fol[super_fol["SECCODE"] == share]
        del super_fol
        try:
            stats = backtest_day([date, lkoh, dom, start_time, deepcopy(algo)], share, show_stat)
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            print("DAY" + str(date) + "Was broked. Try 2.")
            try:
                stats = backtest_day([date, lkoh, dom, start_time, deepcopy(algo)], share, show_stat)
            except KeyboardInterrupt:
                break
            except Exception as e:
                total_skip += 1
                print(e)
                print("DAY" + str(date) + "Was totally broked. Day will be skipped. Total skipped day - " + str(total_skip))
                continue
        stat_list.append(stats)
    if total_skip > 0:
        print(str(total_skip) + "Days was skipped!!!!")
    return stat_list


def hard_backtest_day(records, date, start_time, algo, share_lst, show_stats):
    matching_engines = dict()
    doms = dict()
    for share in share_lst:
        doms[share] = Matching_Engine()
        if platform.system() == "Darwin":
            isebergs = \
            pd.read_csv("/Users/a185583357/Desktop/MOEX/OrderLog" + date + "/isebergs_" + share + date + ".csv",
                        index_col=0).to_dict()["vol"]
        else:
            isebergs = pd.read_csv(path_generator_by_date(date) + "/OrderLog" + date + "/isebergs_" + share + date + ".csv",
                                   index_col=0).to_dict()["vol"]
        matching_engines[share] = [doms[share], isebergs, 0, algo, None, 0]

    algo_orders = None
    for i in tqdm(range(len(records))):
        record = records[i].copy()
        dom, isebergs, algo = matching_engines[record["SECCODE"]][0], \
                                           matching_engines[record["SECCODE"]][1], matching_engines[record["SECCODE"]][3]
        if algo_orders and int(record["TIME"]) > algo_orders[-1]["TIME"] + latency:
            out_algo = create_empty_dict(share_lst, [])
            for order in algo_orders:
                order["DATE"] = date
                try:
                    share = order["ORDERNO"].split(',')[1]
                except:
                    print(order)
                    raise Exception
                dom_algo = matching_engines[share][0]
                try:
                    out = dom_algo.check_order(order)
                    if out:
                        out_algo[share].extend(out.copy())
                except KeyboardInterrupt:
                    break
                except:
                    if order["ACTION"] == 1:
                        print("Cant add order!!!, Very strange", record)
                    matching_engines[record["SECCODE"]][5] += 1
            algo_orders = None
            for share in share_lst:
                if len(out_algo[share]) > 0:
                    algo.change_cash_share(out_algo[share], share)

        if record["ACTION"] == 1 and record["ORDERNO"] in isebergs:
            record["VOLUME"] = isebergs[record["ORDERNO"]]
        try:
            out = dom.check_order(record)
            algo.change_cash_share(out, record["SECCODE"])
        except KeyboardInterrupt:
            break
        except:
            matching_engines[record["SECCODE"]][2] += 1
        if not algo_orders:
            algo_orders = algo.trading(doms, time=record["TIME"])

    declined_me = "me declined - "
    algo_declined = '\nalgo declined -'
    for share in share_lst:
        declined_me += share + " - " + str(matching_engines[share][2]) + ' '
        algo_declined += share + " - " + str(matching_engines[share][5]) + ' '
    print(declined_me, algo_declined)
    print("--- %s overall seconds ---" % (time.time() - start_time))
    print(date, datetime.datetime.now())

    output = dict()
    for share in share_lst:
        dom = doms[share]
        trade_log = pd.DataFrame((dom.trade_log),
                                 columns=["PRICE", 'VOLUME', 'NEW-ORDER-ID', 'PAST-ORDER-ID', "TURNOVER", "TIME", 'NO',
                                          'BUYSELL'])
        algo_raw = pd.concat([trade_log[trade_log["NEW-ORDER-ID"].apply(isinstance, args=(str,))],
                              trade_log[trade_log["PAST-ORDER-ID"].apply(isinstance, args=(str,))]])
        try:
            if show_stats:
                algo_stats(algo_raw, dom.trade_log[-1][0], dom.trade_log[0][0], algo, date, trade_log, dom, share=share,
                           bid_ask=True, show_deals=True)
        except KeyboardInterrupt:
            raise Exception
        except:
            algo_stats(algo_raw, dom.trade_log[-1][0], dom.trade_log[0][0], algo, date, trade_log, dom, share=share,
                       bid_ask=True, show_deals=True)
            print("\n\n\n\nProblem with data at algo stats\n\n\n\n")
        output[share] = day_stats(algo_raw, dom.trade_log[-1][0], dom.trade_log[0][0], algo, date, dom, share=share)
    return output


def calc_empty_day(stats, share_lst, empty_day):
    out = 1
    for share in share_lst:
        if stats[share]["Num_of_trades"] == 0:
            out += 1
    #print(stats, out * empty_day * 1000, out)
    if out == 1:
        return 0
    if out >= len(share_lst):
        return out + empty_day
    else:
        return empty_day // 2

def hard_backtest_year(date, hyperparams, corr_matrix, share_lst, enddate="20160301", cash=2000000, show_graph=False,
                       sigmoid_type="tanh"):
    stat_list = []
    empty_day = 1
    while date != enddate:
        try:
            start_time = time.time()
            date_fst = datetime.datetime.strptime(date, "%Y%m%d")
            date = (date_fst + datetime.timedelta(days=1)).strftime("%Y%m%d")
            if int(date) in bad_days["Hard Correlation MM"]:
                print("this date ", date, " is bad for this stock. Date will be skipped")
                continue
            try:
                fol = get_day_data(date)
            except KeyboardInterrupt:
                break
            except:
                continue
            fol['DATE'] = date
            list_of_data = []
            for share in share_lst:
                try:
                    list_of_data.append(fol[fol["SECCODE"] == share])
                except KeyboardInterrupt:
                    raise Exception
                except:
                    time.sleep(20)
                    list_of_data.append(fol[fol["SECCODE"] == share])
                hyperparams[share]["first_price"] = max(list_of_data[-1].iloc[1000]["PRICE"],
                                                        list_of_data[-1].iloc[1001]["PRICE"])
            try:
                portfolio = pd.concat(list_of_data)
                del fol, list_of_data
            except KeyboardInterrupt:
                raise Exception
            except:
                time.sleep(20)
                portfolio = pd.concat(list_of_data)
                del fol, list_of_data
            portfolio = portfolio.sort_values(by='NO')
            try:
                records = portfolio.to_dict("records")
            except KeyboardInterrupt:
                raise Exception
            except:
                time.sleep(20)
                records = portfolio.to_dict("records")
            del portfolio
            try:
                stats = hard_backtest_day(records, date, start_time,
                                          Hard_Correlation_MM(hyperparams, corr_matrix, sigmoid_type=sigmoid_type, cash=cash),
                                          share_lst, show_graph)
                empty_day = calc_empty_day(stats, share_lst, empty_day)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except Exception as e:
                empty_day += 10
                print("Attention! Day", date, "was broked!", e)
            if empty_day > 1:
                print("\n\nFind potential empty day algo\n\n", empty_day)
                if empty_day > 50:
                    print("\nNon perspective algo\n", hyperparams)
                    return "Non Perspective_algo"
            for share in share_lst:
                hyperparams[share]["first_price"] = stats[share]["Close_price"]
               # print("\n\nclose- ", share, hyperparams[share]["first_price"])
            stat_list.append(stats)
        except MemoryError:
            date = (date_fst - datetime.timedelta(days=1)).strftime("%Y%m%d")
        except KeyboardInterrupt:
            raise Exception
    return stat_list



