"""
the idea is to run optimisations on the initial
strategy via backtesting aggressively on in-sample data
"""

import backtrader as bt # type: ignore

from strategies import *

'''
cerebro truncates output if optreturn is set to True
so we set it to False to get the full output
'''

cerebro = bt.Cerebro(optreturn=False)

data = bt.feeds.GenericCSVData(
    dataname="data/META_data.csv",
    timeframe=bt.TimeFrame.Days,
    dtformat="%Y-%m-%d %H:%M:%S%z",
    datetime=0,
    open=1,
    high=2,
    low=3,
    close=4,
    volume=5,
    openinterest=-1
)

cerebro.adddata(data)


cerebro.addanalyzer(bt.analyzers.SharpeRatio_A,
                    _name='sharpe_ratio',
                    timeframe=bt.TimeFrame.Days,
                    annualize=True,
                    riskfreerate=0.0)
cerebro.optstrategy(MAcrossover, pfast=range(5, 20), pslow=range(50, 100))

# position sizing
cerebro.addsizer(bt.sizers.SizerFix, stake=3)

if __name__ == "__main__":
    optimized_runs = cerebro.run()

    final_results_list = []
    for run in optimized_runs:
        for strategy in run:
            pnl = round(strategy.broker.get_value() - 10000, 2)

            sharpe = strategy.analyzers.sharpe_ratio.get_analysis()

            if sharpe.get('sharperatio') is not None:
                final_results_list.append([strategy.params.pfast, strategy.params.pslow, pnl, sharpe['sharperatio']])
            else:
                final_results_list.append([strategy.params.pfast, strategy.params.pslow, pnl, sharpe])


    sort_by_sharpe = sorted(final_results_list, key=lambda x: x[3], reverse=True)

    for line in sort_by_sharpe[:5]:
        print(line)
