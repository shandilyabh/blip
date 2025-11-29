"""
Test script for mean reversion strategy
"""

from data_handler import DataHandler
from redundant_backtester import Backtester
from strategy import Strategy

symbol = "NFLX"
start_date = "2022-01-01"
end_date = "2022-12-31"

data = DataHandler(symbol, start_date=start_date, end_date=end_date).load_data()

strategy = Strategy(
    indicators={
        "sma_50" : lambda row: row["close"].rolling(window=50).mean(),
        "std_3": lambda row: row["close"].rolling(window=50).std(),
        "std_3_upper" : lambda row: row["sma_50"] + row["std_3"],
        "std_3_lower" : lambda row: row["sma_50"] - row["std_3"]
    },
    signal_logic=lambda row: (
        1
        if row["close"] < row["std_3_lower"]
        else -1 if row["close"] > row["std_3_upper"] else 0
    )
)

data = strategy.generate_signals(data)

backtester = Backtester()
backtester.backtest(data)
backtester.calculate_performance(plot=True)