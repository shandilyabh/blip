"""
The main usage script for testing modified backtester
"""

import csv
import os
import threading
from concurrent import futures
from data_handler import DataHandler
from backtester_testfile import Backtester
from strategy import Strategy

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
    backtests a strategy for a single symbol
    """
    symbol = symbol
    start_date = "2022-01-01"
    end_date = "2024-12-31"

    data = DataHandler(symbol=symbol, start_date=start_date, end_date=end_date).load_data()

    strategy = Strategy(
        indicators={
            "sma_20": lambda row: row["close"].rolling(window=20).mean(),
            "sma_60": lambda row: row["close"].rolling(window=60).mean(),
        },
        signal_logic=lambda row: 1 if row["sma_20"] > row["sma_60"] else -1,
    )
    data = strategy.generate_signals(data)

    backtester = Backtester(symbol=symbol, stop_loss_pct=0.05)
    backtester.backtest(data)

    # flatten & log trades
    backtester.close_all_positions({"SINGLE_ASSET": data}) # type: ignore

    results = backtester.calculate_performance(plot=False)
    append_dict_to_csv(results, "results/strategies_results_test.csv") # type: ignore

    # export trade log
    backtester.export_trade_log(f"results/trades/{symbol}_trades.csv")

list_of_symbols = ["AAPL", "MSFT", "NFLX"]

with futures.ThreadPoolExecutor(3) as executor:
    executor.map(backtest_symbol, list_of_symbols)