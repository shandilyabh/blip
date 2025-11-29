"""
Main backtesting logic
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
)

class Backtester:
    """ backtester class for trading strategies """

    def __init__(
            self,
            initial_capital: float = 10000.0,
            commission_pct: float = 0.001,
            commission_fixed: float = 1.0
    ):
        """ constructor """
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.commission_fixed = commission_fixed
        self.assets_data: dict = {}
        self.portfolio_history: dict = {}
        self.daily_portfolio_values: list[float] = []


    def execute_trade(self, asset: str, signal: int, price: float) -> None:
        """
        execute a trade based on signal and price
        """
        if signal > 0 and self.assets_data[asset]["cash"] > 0: # buy
            trade_value = self.assets_data[asset]["cash"]
            commission = self.calculate_commission(trade_value)
            shares_to_buy = (trade_value - commission) / price
            self.assets_data[asset]["positions"] += shares_to_buy
            self.assets_data[asset]["cash"] -= trade_value

        elif signal < 0 and self.assets_data[asset]["positions"] > 0: # sell
            trade_value = self.assets_data[asset]["positions"] * price
            commission = self.calculate_commission(trade_value)
            self.assets_data[asset]["cash"] += trade_value - commission
            self.assets_data[asset]["positions"] = 0


    def calculate_commission(self, trade_value: float) -> float:
        """ calculating commission """
        return max(trade_value * self.commission_pct, self.commission_fixed)
    

    def update_portfolio(self, asset: str, price: float) -> None:
        """ update the portfolio with latest price. """
        self.assets_data[asset]["position_value"] = (
            self.assets_data[asset]["positions"] * price
        )

        self.assets_data[asset]["total_value"] = (
            self.assets_data[asset]["cash"] + self.assets_data[asset]["position_value"]
        )

        self.portfolio_history[asset].append(self.assets_data[asset]["total_value"])

    
    def backtest(self, data: pd.DataFrame | dict[str, pd.DataFrame]):
        """ backtest the trading strategy using the provided data """
        if isinstance(data, pd.DataFrame): # single asset
            data = {
                "SINGLE_ASSET": data
            } # streamlining into dict to maintain format consistency

        for asset in data:
            self.assets_data[asset] = {
                "cash" : self.initial_capital / len(data),
                "positions" : 0,
                "position_value": 0,
                "total_value": 0
            }

            self.portfolio_history[asset] = []

            for date, row in data[asset].iterrows():
                self.execute_trade(asset, row["signal"], row["close"])
                self.update_portfolio(asset, row["close"])

                if len(self.daily_portfolio_values) < len(data[asset]):
                    self.daily_portfolio_values.append(
                        self.assets_data[asset]["total_value"]
                    )
                else:
                    self.daily_portfolio_values[
                        len(self.portfolio_history[asset]) - 1
                    ] += self.assets_data[asset]["total_value"]
    
    def calculate_performance(self, plot: bool = True):
        """
        calculating metrics
        """
        
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
        sharpe_ratio = calculate_sharpe_ratio(annualised_return, annualised_volatility)

        sortino_ratio = calculate_sortino_ratio(daily_returns, annualised_return)
        max_drawdown = calculate_maximum_drawdown(portfolio_values)

        print(f"Final Portfolio Value: {portfolio_values.iloc[-1]:.2f}")
        print(f"Total Return: {total_return * 100:.2f}%")
        print(f"Annualized Return: {annualised_return * 100:.2f}%")
        print(f"Annualized Volatility: {annualised_volatility * 100:.2f}%")
        print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
        print(f"Sortino Ratio: {sortino_ratio:.2f}")
        print(f"Maximum Drawdown: {max_drawdown * 100:.2f}%")

        if plot:
            self.plot_performance(portfolio_values, daily_returns)

        return {
            "initial_capital": self.initial_capital,
            "final_portfolio_value": round(portfolio_values.iloc[-1], 2),
            "total_return": round(total_return * 100, 2),
            "annualised_return": round(annualised_return * 100, 2),
            "annualised_volatility": round(annualised_volatility * 100, 2),
            "sharpe": round(sharpe_ratio, 2),
            "sortino": round(sortino_ratio, 2),
            "max_drawdown": round(max_drawdown * 100, 2)
        }


    def plot_performance(self, portfolio_values: pd.Series, daily_returns: pd.Series):
        """
        plot performance of the trading strategy
        """
        plt.figure(figsize=(10, 6))

        plt.subplot(2, 1, 1)
        plt.plot(portfolio_values, label="Portfolio Value")
        plt.title("Portfolio Value Over Time")
        plt.legend()

        plt.subplot(2, 1, 2)
        plt.plot(daily_returns, label="Daily Returns", color="orange")
        plt.title("Daily Returns Over Time")
        plt.legend()

        plt.tight_layout()
        plt.show()
