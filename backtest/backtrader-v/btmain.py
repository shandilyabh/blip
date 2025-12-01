"""
the main backtesting script
"""

import backtrader as bt # type: ignore

from strategies import *

import datetime

cerebro = bt.Cerebro()

# in-sample data
data = bt.feeds.GenericCSVData(
    dataname = 'data/AAPL_data.csv',
    dtformat = '%Y-%m-%d %H:%M:%S%z',
    datetime=0,
    open=1,
    high=2,
    low=3,
    close=4,
    volume=5,
    openinterest=-1,
    timeframe=bt.TimeFrame.Days, # essentially means 'per day data'
    fromdate=datetime.datetime(2018, 1, 1),
    todate=datetime.datetime(2019, 12, 25)
)

# whatever remains is the out-of-sample data: used for testing post optimisation--the whole process is called walk-forward analysis

cerebro.adddata(data)

cerebro.addstrategy(MAcrossover, pfast=7, pslow=92)

# this sets the default position size
cerebro.addsizer(bt.sizers.FixedSize, stake=3)

if __name__ == "__main__":
    # cerebro.broker.getvalue() gets the portfolio value at any point in tiem

    start_portfolio_value = cerebro.broker.getvalue()

    cerebro.run()

    end_portfolio_value = cerebro.broker.getvalue()

    pnl = end_portfolio_value - start_portfolio_value

    print(f"Starting Portfolio Value: {start_portfolio_value}")
    print(f"Ending Portfolio Value: {end_portfolio_value}")
    print(f"PnL: {pnl}")

    cerebro.plot()