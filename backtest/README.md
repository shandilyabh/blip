# Backtesting

This project contains a collection of Python scripts for backtesting trading strategies. It includes a custom backtesting framework and a set of example strategies. The project also contains a tutorial folder where I learnt how to use the `backtrader` library for backtesting.

## Folder Structure

```
/
├───backtest.py
├───backtester.py
├───data_handler.py
├───mean_reversion.py
├───pairs.py
├───performance.py
├───redundant_backtester.py
├───strategy.py
├───__pycache__/
└───results/
    ├───mean_rev_strategy_results_test.csv
    └───trades/
        ├───MR_RELIANCE.NS_trades.csv
        └───MR_TCS.NS_trades.csv
├───backtrader-v/
    ├───data/
    │   ├───AAPL_data.csv
    │   ├───GE_data.csv
    │   ├───GRPN_data.csv
    │   └───TSLA_data.csv
    ├───btmain.py
    ├───opt_btmain.py
    ├───screener_main.py
    └───strategies.py
```

## Components

### Core Components

- **`backtest.py`**: The main script for running the backtesting process. It uses a `ThreadPoolExecutor` to run backtests for multiple symbols in parallel. It uses `DataHandler` to fetch data, `Strategy` to generate signals, and `Backtester` to simulate trading and calculate performance. The results are then saved to CSV files in the `results` folder.

- **`backtester.py`**: This script contains the core backtesting logic. The `Backtester` class handles trade execution, commission calculation, stop-loss implementation, and performance calculation. It also includes trade logging and performance plotting.

- **`data_handler.py`**: This script is responsible for fetching historical price data. The `DataHandler` class can fetch data from `openbb` and `yfinance`. It also has a method to load data from a CSV file.

- **`strategy.py`**: This script defines a generic `Strategy` class that can be used to create trading strategies. It takes a dictionary of indicators and a signal logic function to generate trading signals.

- **`performance.py`**: This script contains a collection of functions for calculating various performance metrics, such as total return, annualized return, Sharpe ratio, etc.

- **`redundant_backtester.py`**: This is a simpler version of `backtester.py`. It lacks some of the advanced features, such as trade logging and stop-loss functionality.

### Example Strategies

- **`mean_reversion.py`**: This script is an example of a mean reversion strategy. It uses a 50-day simple moving average and standard deviation to generate trading signals.

- **`pairs.py`**: This script is an example of a pairs trading strategy. It uses the 5-day lookback price of two stocks to generate trading signals.

### Results

The `results` folder contains the output of the backtesting process.

- **`mean_rev_strategy_results_test.csv`**: This file contains the performance metrics for the mean reversion strategy.
- **`trades/`**: This directory contains the trade logs for each symbol.

## `backtrader-v`

The `backtrader-v` folder contains a tutorial on how to use the `backtrader` library for backtesting.

- **`btmain.py`**: This script shows how to run a simple backtest using `backtrader`. It uses a moving average crossover strategy.

- **`opt_btmain.py`**: This script shows how to optimize a strategy using `backtrader`. It runs the moving average crossover strategy with a range of different parameters and prints the top 5 results.

- **`screener_main.py`**: This script shows how to use `backtrader` to screen for stocks that meet certain criteria. It uses a custom analyzer to screen for stocks that are trading below their lower Bollinger Band.

- **`strategies.py`**: This script defines the `MAcrossover` strategy and the `Screener_SMA` analyzer used in the other scripts.
- **`data/`**: This directory contains sample data for the `backtrader` tutorial.
