"""
test script for backtester on basic SMA crossover
"""

from concurrent import futures
from backtest.data_handler import DataHandler
from backtest.backtester import Backtester
from backtest.strategy import Strategy

import csv
import os
import threading

csv_lock = threading.Lock()

def append_dict_to_csv(data: dict, csv_path: str):
    """
    appends results for a ticker as a row to a CSV.
    Creates the CSV with headers if it doesn't exist.
    Returns None.
    """
    file_exists = os.path.isfile(csv_path)

    fieldnames = list(data.keys())

    with csv_lock:
        with open(csv_path, mode="a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow(data)


def backtest_symbol(symbol: str):
    """
    function backtests a strategy on a single ticker
    """
    symbol = symbol
    start_date = "2023-01-01"
    end_date = "2023-12-31"

    data = DataHandler(
            symbol=symbol, start_date=start_date, end_date=end_date
        ).load_data()

    strategy = Strategy(
        indicators={
            "sma_20": lambda row: row["close"].rolling(window=20).mean(),
            "sma_60": lambda row: row["close"].rolling(window=60).mean(),
        },
        signal_logic=lambda row: 1 if row["sma_20"] > row["sma_60"] else -1,
    )
    data = strategy.generate_signals(data)

    backtester = Backtester()
    backtester.backtest(data)
    results = backtester.calculate_performance(plot=False)
    append_dict_to_csv(results, "strategies_results.csv") # type: ignore

list_of_symbols = ["AAPL", "MSFT", "NFLX"]

with futures.ThreadPoolExecutor(3) as executor:
    executor.map(backtest_symbol, list_of_symbols)