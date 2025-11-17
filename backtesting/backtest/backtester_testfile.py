"""
Main backtesting logic + optional trade logging
"""

import pandas as pd # type: ignore
import matplotlib.pyplot as plt # type: ignore
from performance import (
    calculate_total_return,
    calculate_annualised_return,
    calculate_annualised_volatility,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_maximum_drawdown,
    calculate_calmar_ratio,
)

class Backtester:
    """ backtester class for trading strategies """

    def __init__(
            self,
            symbol: str,
            initial_capital: float = 10000.0,
            commission_pct: float = 0.001,
            commission_fixed: float = 1.0,
            stop_loss_pct: float | None = None
    ):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.commission_fixed = commission_fixed
        self.stop_loss_pct = stop_loss_pct
        self.assets_data: dict = {}
        self.portfolio_history: dict = {}
        self.daily_portfolio_values: list[float] = []
        self.trade_log: list[dict] = []


    def log_trade(
        self,
        asset: str,
        entry_time,
        exit_time,
        entry_price: float,
        exit_price: float,
        size: float,
        exit_reason: str
    ):
        pnl = (exit_price - entry_price) * size
        pnl_pct = (exit_price / entry_price - 1) if entry_price else 0

        self.trade_log.append({
            "asset": asset,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": exit_reason
        })


    def close_all_positions(self, data: dict[str, pd.DataFrame]):
        """
        Optional: call at the end of backtest() if you want
        all open positions flattened + logged.
        """
        for asset, st in self.assets_data.items():
            size = st["positions"]
            if size <= 0:
                continue

            final_price = data[asset].iloc[-1]["close"]
            entry_price = st.get("entry_price", final_price)
            entry_time = st.get("entry", None)
            exit_time = data[asset].index[-1]

            self.log_trade(
                asset,
                entry_time,
                exit_time,
                entry_price=entry_price,
                exit_price=final_price,
                size=size,
                exit_reason="end_of_backtest"
            )

            st["positions"] = 0


    def export_trade_log(self, filepath: str):
        if not self.trade_log:
            return

        df = pd.DataFrame(self.trade_log)
        df.to_csv(filepath, index=False)


    def execute_trade(self, asset: str, signal: int, price: float, date) -> None:
        date = date

        if signal > 0 and self.assets_data[asset]["cash"] > 0:
            trade_value = self.assets_data[asset]["cash"]
            commission = self.calculate_commission(trade_value)
            shares_to_buy = (trade_value - commission) / price

            self.assets_data[asset]["entry_price"] = price
            self.assets_data[asset]["entry"] = date

            self.assets_data[asset]["positions"] += shares_to_buy
            self.assets_data[asset]["cash"] -= trade_value

        elif signal < 0 and self.assets_data[asset]["positions"] > 0:
            entry_price = self.assets_data[asset].get("entry_price")
            entry_time = self.assets_data[asset].get("entry")
            if entry_price is not None:
                self.log_trade(
                    asset,
                    entry_time,
                    date,
                    entry_price=entry_price,
                    exit_price=price,
                    size=self.assets_data[asset]["positions"],
                    exit_reason="signal_exit"
                )

            trade_value = self.assets_data[asset]["positions"] * price
            commission = self.calculate_commission(trade_value)

            self.assets_data[asset]["cash"] += trade_value - commission
            self.assets_data[asset]["positions"] = 0

        if self.stop_loss_pct is not None and self.assets_data[asset]["positions"] > 0:
            entry_price = self.assets_data[asset].get("entry_price")
            if entry_price:
                if price <= entry_price * (1 - self.stop_loss_pct):
                    size = self.assets_data[asset]["positions"]
                    self.log_trade(
                        asset,
                        self.assets_data[asset].get("entry"),
                        date,
                        entry_price=entry_price,
                        exit_price=price,
                        size=size,
                        exit_reason="stop_loss_hit"
                    )
                    trade_value = size * price
                    commission = self.calculate_commission(trade_value)
                    self.assets_data[asset]["cash"] += trade_value - commission
                    self.assets_data[asset]["positions"] = 0
                    return


    def calculate_commission(self, trade_value: float) -> float:
        return max(trade_value * self.commission_pct, self.commission_fixed)
    

    def update_portfolio(self, asset: str, price: float) -> None:
        self.assets_data[asset]["position_value"] = (
            self.assets_data[asset]["positions"] * price
        )
        self.assets_data[asset]["total_value"] = (
            self.assets_data[asset]["cash"] + self.assets_data[asset]["position_value"]
        )
        self.portfolio_history[asset].append(self.assets_data[asset]["total_value"])

    
    def backtest(self, data: pd.DataFrame | dict[str, pd.DataFrame]):
        if isinstance(data, pd.DataFrame):
            data = { "SINGLE_ASSET": data }

        for asset in data:
            self.assets_data[asset] = {
                "cash" : self.initial_capital / len(data),
                "positions" : 0,
                "position_value": 0,
                "total_value": 0,
                "entry_price": None,
                "entry": None
            }
            self.portfolio_history[asset] = []

            for date, row in data[asset].iterrows():
                self.execute_trade(asset, row["signal"], row["close"], date=date)
                self.update_portfolio(asset, row["close"])

                if len(self.daily_portfolio_values) < len(data[asset]):
                    self.daily_portfolio_values.append(
                        self.assets_data[asset]["total_value"]
                    )
                else:
                    self.daily_portfolio_values[
                        len(self.portfolio_history[asset]) - 1
                    ] += self.assets_data[asset]["total_value"]

        # (optional) allow user to flatten & log
        # self.close_all_positions(data)


    def calculate_performance(self, plot: bool = True):
        if not self.daily_portfolio_values:
            print("[.] No portfolio history to calculate performance")
            return
        
        portfolio_values = pd.Series(self.daily_portfolio_values)
        daily_returns = portfolio_values.pct_change().dropna()

        total_return = calculate_total_return(
            portfolio_values.iloc[-1], self.initial_capital
        )
        annualised_return = calculate_annualised_return(
            total_return, len(portfolio_values)
        )
        annualised_volatility = calculate_annualised_volatility(daily_returns)
        sharpe_ratio = calculate_sharpe_ratio(
            annualised_return, annualised_volatility
        )
        sortino_ratio = calculate_sortino_ratio(
            daily_returns, annualised_return
        )
        max_drawdown = calculate_maximum_drawdown(portfolio_values)
        calmar_ratio = calculate_calmar_ratio(annualised_return, max_drawdown)

        total_trades = len(self.trade_log)
        winning_trades = [t for t in self.trade_log if t["pnl"] > 0]
        losing_trades = [t for t in self.trade_log if t["pnl"] <= 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        loss_rate = len(losing_trades) / total_trades if total_trades > 0 else 0

        avg_win = sum(t["pnl"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t["pnl"] for t in losing_trades) / len(losing_trades) if losing_trades else 0

        expectancy = (win_rate * avg_win / self.initial_capital) - (loss_rate * abs(avg_loss / self.initial_capital))

        if plot:
            self.plot_performance(portfolio_values, daily_returns)

        return {
            "symbol": self.symbol,
            "initial_capital": self.initial_capital,
            "final_portfolio_value": round(portfolio_values.iloc[-1], 2),
            "total_return": round(total_return * 100, 2),
            "annualised_return": round(annualised_return * 100, 2),
            "annualised_volatility": round(annualised_volatility * 100, 2),
            "sharpe": round(sharpe_ratio, 2),
            "sortino": round(sortino_ratio, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "calmar": round(calmar_ratio, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate * 100, 2),
            "loss_rate": round(loss_rate * 100, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "expectancy": round(expectancy, 3),
        }


    def plot_performance(self, portfolio_values: pd.Series, daily_returns: pd.Series):
        plt.figure(figsize=(10, 6))

        plt.subplot(2, 1, 1)
        plt.plot(portfolio_values, label="Portfolio Value")
        plt.legend()

        plt.subplot(2, 1, 2)
        plt.plot(daily_returns, label="Daily Returns", color="orange")
        plt.legend()

        plt.tight_layout()
        plt.show()
