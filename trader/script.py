"""
main script for running the trader
"""

import asyncio
from market_adapter import MarketAdapter
from risk_engine import RiskEngine
from strategy import SMA_CROSS
from threading import Lock
from pymongo import MongoClient # type: ignore
import json
import os
import pyfiglet # type: ignore
from dotenv import load_dotenv # type: ignore
from pathlib import Path
from uniplot import plot, plot_gen # type: ignore
import warnings
warnings.filterwarnings("ignore")

lock = Lock()

# Globals for Portfolio State Management
INITIAL_CAPITAL = 1000000.0
peak_portfolio_value = INITIAL_CAPITAL
total_realized_pnl = 0.0

positions = {}
latest_prices = {}
pnl_series = []
portfolio_queue = asyncio.Queue()
pnl_plot = plot_gen()

# Mongo Set-up
# env_path = Path(__file__).resolve().parent.parent / '.env'
# load_dotenv(env_path)

# client = MongoClient(os.getenv("MONGO_CONN_STRING"))
# db = client["trade_logs"]
# collection = db["sma_2_7"]


def render_portfolio(state):
    """
    Lightweight terminal renderer for portfolio metrics.
    Purely prints, no clearing, no formatting side-effects.
    """
    os.system("clear")

    # For the Plot
    current_pnl = state["current_portfolio_value"] - INITIAL_CAPITAL
    pnl_series.append(current_pnl)
    color = ["green" if pnl_series[-1] >= 0 else "red"]

    # color schemes for portfolio
    real = state["total_realized_pnl"]
    if real > 0:
        pnl_color = "\033[92m"
    elif real < 0:
        pnl_color = "\033[91m"
    else:
        pnl_color = "\033[97m"

    ops = state["open_positions_count"]
    pos_color = "\033[94m" if ops > 0 else "\033[97m"

    f = pyfiglet.figlet_format("ABX", font="slant")
    print(f)

    print("\n--- LATEST BARS ---")
    with lock:
        for instrument, bar in latest_prices.items():
            print(f"{instrument}: {bar}")
    print("---------------------\n")

    print("\n--- PORTFOLIO METRICS ---")
    print(f"Portfolio Value     : {state['current_portfolio_value']:.2f}")
    print(f"Peak Value          : {state['peak_portfolio_value']:.2f}")
    print(f"Drawdown %          : {state['portfolio_drawdown_pct']*100:.2f}")
    print(f"Realized PnL        : {pnl_color}{real:.2f}\033[0m")
    print(f"Unrealized PnL      : {state['total_unrealized_pnl']:.2f}")
    print(f"Total Positions MV  : {state['total_positions_value']:.2f}")
    print(f"Open Positions Count: {pos_color}{ops}\033[0m")
    print(f"Leverage            : {state['leverage']:.2f}")
    print(f"Open Positions      : {pos_color}{state['open_positions']}\033[0m")
    print("-------------------\n")
    

    print("\n--- PNL GRAPH ---")
    plot(pnl_series, title="Portfolio Value - PnL over Time", color=color)
    print("-----------------\n")


async def close_and_log_position(instrument, pos, exit_bar, reason=""):
    """
    Handles the logic for closing a position, calculating P&L,
    and logging the trade.
    """
    global total_realized_pnl
    
    print(f"[{instrument}] {reason} EXIT triggered -> {pos}\n")
    # await trader_global.exit_position(pos)

    entry_price = pos["entry"]
    size = pos["size"]
    side = pos["side"]
    exit_price = exit_bar.get("close", pos["entry"])

    if reason == "TARGET":
        exit_price = pos["target"]
    elif reason == "STOP":
        exit_price = pos["stop"]

    if side == "BUY":
        pnl = (exit_price - entry_price) * size
    else: # SELL
        pnl = (entry_price - exit_price) * size

    total_realized_pnl += pnl

    exit_record = {
        "instrument": instrument,
        "side": side,
        "entry": entry_price,
        "exit_price": exit_price,
        "pnl": round(pnl, 2),
        "realized_pnl": round(total_realized_pnl, 2),
        "reason": reason,
        "target": pos["target"],
        "stop": pos["stop"],
        "size": size,
        "ts_entry": pos['ts'],
        "ts_exit": exit_bar["ts"],
        "trade_duration" : (int(exit_bar['ts']) - int(pos['ts'])) / 1000,
        "type": "EXIT"
    }

    # collection.insert_one(exit_record) # insert into mongo

    with lock:
        positions.pop(instrument, None)
        
        try:
            with open("trades.json", "r") as file:
                trades = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            trades = []
        trades.append(exit_record)

        with open("trades.json", "w") as file:
            json.dump(trades, file, indent=4)


async def portfolio_monitor():
    """
    Runs continuously.
    - Processes bars from the queue to check for stop/target hits.
    - Renders the portfolio state to the console.
    """

    while True:
        try:
            instrument, bar = await asyncio.wait_for(portfolio_queue.get(), timeout=5.0)

            # update latest prices and render the portfolio
            with lock:
                latest_prices[instrument] = bar
            
            portfolio_state = build_portfolio_state()
            render_portfolio(portfolio_state)

            # check for stop/target hits
            pos = positions.get(instrument)
            if pos:
                exit_reason = ""
                if pos["side"] == "BUY":
                    if bar["low"] <= pos["stop"]: exit_reason = "STOP"
                    elif bar["high"] >= pos["target"]: exit_reason = "TARGET"
                else: # SELL
                    if bar["high"] >= pos["stop"]: exit_reason = "STOP"
                    elif bar["low"] <= pos["target"]: exit_reason = "TARGET"

                if exit_reason:
                    await close_and_log_position(instrument, pos, bar, reason=exit_reason)

        except asyncio.TimeoutError:
            # on timeout, just re-render the last known state
            portfolio_state = build_portfolio_state()
            render_portfolio(portfolio_state)
            pass


def build_portfolio_state():
    """
    Builds a comprehensive snapshot of the current portfolio state.
    """
    global peak_portfolio_value
    
    with lock:
        open_positions_list = []
        total_market_value = 0
        total_unrealized_pnl = 0
        
        for instr, pos in positions.items():
            current_price = latest_prices.get(instr, {}).get("close", pos["entry"])
            market_value = pos["size"] * current_price
            
            if pos["side"] == "BUY":
                unrealized_pnl = (current_price - pos["entry"]) * pos["size"]
            else: # SELL
                unrealized_pnl = (pos["entry"] - current_price) * pos["size"]

            total_market_value += market_value
            total_unrealized_pnl += unrealized_pnl
            open_positions_list.append({ "instrument": instr, "side": pos["side"], "size": pos["size"] })

        current_portfolio_value = INITIAL_CAPITAL + total_realized_pnl + total_unrealized_pnl
        peak_portfolio_value = max(peak_portfolio_value, current_portfolio_value)
        
        drawdown_pct = (peak_portfolio_value - current_portfolio_value) / peak_portfolio_value if peak_portfolio_value > 0 else 0
        leverage = total_market_value / current_portfolio_value if current_portfolio_value > 0 else 0

        return {
            "current_portfolio_value": current_portfolio_value,
            "peak_portfolio_value": peak_portfolio_value,
            "portfolio_drawdown_pct": drawdown_pct,
            "total_positions_value": total_market_value,
            "total_realized_pnl": total_realized_pnl,
            "total_unrealized_pnl": total_unrealized_pnl,
            "open_positions_count": len(positions),
            "leverage": leverage,
            "open_positions": open_positions_list
        }


async def process_instrument(instrument: str, strat: SMA_CROSS, risk: RiskEngine, bar_queue: asyncio.Queue):
    """
    Processes the data stream for a single instrument to generate signals and manage positions.
    """
    _type = "equity" if "NSE_EQ" in instrument else "index"
    
    while True:
        try:
            bar = await bar_queue.get()
            
            await portfolio_queue.put((instrument, bar))

            signal = await strat.generate_signal(bar)

            if instrument in positions:
                continue
            
            # latest portfolio state for risk calculation
            portfolio_state = build_portfolio_state()
            
            params = await risk.determine_position(
                signal, bar, instrument_type=_type, portfolio_state=portfolio_state
            )
            if params is None:
                continue

            print(instrument, "PARAMS:", params, "\n")

            with lock:
                params['instrument'] = instrument
                positions[instrument] = params
                
                try:
                    with open("trades.json", "r") as file:
                        trades = json.load(file)
                except (FileNotFoundError, json.JSONDecodeError):
                    trades = []
                trades.append(params)

                with open("trades.json", "w") as file:
                    json.dump(trades, file, indent=4)
        except asyncio.CancelledError:
            print(f"Pipeline for {instrument} cancelled.")
            break
        except Exception as e:
            print(f"[{instrument}] Error in process_instrument: {e}")


async def main():
    # --- Configuration ---
    instrument_configs = [
        # ("NSE_EQ|INE002A01018", 5, 12), # RELIANCE
        # ("NSE_EQ|INE467B01029", 2, 7),  # TCS
        # ("NSE_EQ|INE0HOQ01053", 5, 12),  # GROWW
        ("NSE_EQ|INE171A01029", 5, 12), # Federal Bank
        ("NSE_EQ|INE200M01039", 5, 12), # VBL
        ("NSE_EQ|INE155A01022", 5, 12),  # TMPV
    ]
    instrument_keys = [config[0] for config in instrument_configs]

    adapter = MarketAdapter(instrument_keys)
    risk_engine = RiskEngine(capital=INITIAL_CAPITAL)
    
    tasks = []

    # Create a single data fetching task
    fetch_task = asyncio.create_task(adapter.dummy_fetch())
    fetch_task.add_done_callback(lambda t: print(f"Master fetch task done. Exception: {t.exception()}"))
    tasks.append(fetch_task)

    # Create a processing task for each instrument
    for instrument, short_sma, long_sma in instrument_configs:
        strategy = SMA_CROSS(short_sma, long_sma, instrument)
        strategy.dummy_patch()
        
        bar_queue = adapter.queues[instrument]
        
        instrument_task = asyncio.create_task(
            process_instrument(instrument, strategy, risk_engine, bar_queue)
        )
        tasks.append(instrument_task)

    tasks.append(asyncio.create_task(portfolio_monitor()))

    await asyncio.gather(*tasks)
    

if __name__ == "__main__":
    with open("trades.json", "w") as f:
        json.dump([], f)
    asyncio.run(main())
