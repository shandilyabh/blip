# Trader

This document provides a detailed explanation of the architecture of the `trader` directory, which contains a complete, asynchronous, event-driven trading bot.

## Folder Structure

```
/Users/abhishekshandilya/development/duckducktrade/trader/
├───market_adapter.py
├───risk_engine.py
├───script.py
├───strategy.py
├───__pycache__/
├───trade_logs/
└───utils/
    ├───fetch_data_upstox.py
    ├───MarketDataFeedV3_pb2.py
    ├───MarketDataFeedV3.proto
    └───__pycache__/
```

## Architectural Overview

The trading bot is built on an asynchronous, event-driven architecture using Python's `asyncio` library. This allows for concurrent execution of tasks, such as fetching market data for multiple instruments, processing trading signals, and managing a portfolio. The architecture is modular, with a clear separation of concerns between data acquisition, strategy logic, and risk management.

1.  **Orchestration (`script.py`):** The main script initializes and runs the system. It sets up a `MarketAdapter` for data, a `RiskEngine` for trade sizing, and multiple `SMA_CROSS` strategy instances (one for each financial instrument).
2.  **Data Handling (`market_adapter.py`):** The `MarketAdapter` is responsible for sourcing market data. It uses `asyncio.Queue` to distribute 1-minute OHLC bars to the correct strategy instance.
3.  **Strategy Logic (`strategy.py`):** The `SMA_CROSS` class receives bars from the adapter, calculates moving averages, and generates a buy (`1`), sell (`-1`), or hold (`0`) signal.
4.  **Risk Management (`risk_engine.py`):** The `RiskEngine` receives the signal and the current market price. It calculates the appropriate position size based on a predefined risk-per-trade and sets a volatility-based stop-loss using the Average True Range (ATR). It also enforces portfolio-level rules like maximum leverage and drawdown.
5.  **Portfolio Monitoring (`script.py`):** A dedicated task (`portfolio_monitor`) runs concurrently, tracking open positions, checking for stop-loss or target-profit triggers, and rendering a summary of the portfolio's state to the console.
6.  **Utilities (`utils/`):** The `utils` directory contains helpers to connect to the Upstox API (`fetch_data_upstox.py`) and to decode the binary data stream from the WebSocket, which uses Protocol Buffers (`MarketDataFeedV3.proto` and the generated `_pb2.py` file).

## Components

### `script.py`

This is the main entry point of the application. It initializes all the components and orchestrates the concurrent tasks for data fetching, processing, and portfolio management. It clearly shows how the different modules are wired together.

### `market_adapter.py`

This file is responsible for providing market data. It contains the logic for connecting to the live Upstox WebSocket (`fetch`) and the logic for simulating market data for testing (`dummy_fetch`).

### `strategy.py`

This file contains the trading logic (SMA Crossover). It defines how to prime the strategy with historical data, both from a live API (`patch`) and from a simulated dataset (`dummy_patch`). It's responsible for generating the core buy/sell signals.

### `risk_engine.py`

This component is the risk management brain. It takes a raw signal from the strategy and converts it into a concrete trade with proper position sizing, stop-loss, and target levels, based on portfolio-wide risk rules.

### `utils/`

This directory contains utility scripts:

*   `fetch_data_upstox.py`: This is a utility module that abstracts all interactions with the Upstox API, including authentication, fetching historical data via REST, and decoding the binary Protobuf messages from the live WebSocket feed.
*   `MarketDataFeedV3.proto`: This file is the schema definition for the binary data format used by the Upstox WebSocket. It is the source of truth for the structure of live market data.
*   `MarketDataFeedV3_pb2.py`: This is the Python code generated from the `.proto` file, used for parsing the binary data.

## Simulation vs. Live Trading (`dummy_fetch` and `dummy_patch`)

The system is designed to be easily switched between a simulation mode and a live trading mode. This is achieved through the use of `dummy_fetch` and `dummy_patch` methods.

*   **`dummy_fetch` (in `market_adapter.py`):** This method simulates a live market feed. Instead of connecting to a WebSocket, it generates a synthetic stream of price bars with predictable trends (up, down, sideways). This ensures the strategy's logic is triggered for testing purposes.

*   **`dummy_patch` (in `strategy.py`):** A strategy needs historical data to calculate its initial indicator values (e.g., the first moving average). This method provides that initial data by generating a synthetic block of past prices. It is the counterpart to `dummy_fetch`.

In its current configuration, the system is set up to run as a self-contained simulation. To run it live, the calls in `script.py` would need to be changed from `adapter.dummy_fetch()` to `adapter.fetch()` and from `strategy.dummy_patch()` to `strategy.patch()`.
