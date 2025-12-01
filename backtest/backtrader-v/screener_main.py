""" the main script to run the screener with backtrader """

import backtrader as bt # type: ignore

from strategies import *

cerebro = bt.Cerebro()

instruments = ['AAPL', 'TSLA', 'GE', 'GRPN']

for symbol in instruments:
    data = bt.feeds.GenericCSVData(
        dataname=f"data/{symbol}_data.csv",
        dtformat="%Y-%m-%d %H:%M:%S%z",
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1  # no open interest
    )
    cerebro.adddata(data)

cerebro.addanalyzer(Screener_SMA, period=20, devfactor=2, _name='screener_sma')

if __name__ == "__main__":
    cerebro.run(runonce=False, stdstats=False, writer=True)

    '''
    runonce: precomputes all indicators only once (in one pass), disabling it allows indicators to be recalculated on each bar--useful for strategies that change indicators dynamically/per-bar like Moving average Crossovers. [data remains syncronised]

    stdstats: the default built-in statistics (like broker value, trades etc) from being automatically calculated and displayed. disabling it allows custom statistics or analyzers to be used without the default stats cluttering the output.

    writer: enables Bakctrader's writer to automatically output logs and results to file(s) or console.
    '''
