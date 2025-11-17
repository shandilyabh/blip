"""
Real-time Risk Management Simulator (INDEX performance metrics)
"""

import pandas as pd # type: ignore
import numpy as np
import time
from datetime import datetime, timedelta
import os
import sys


def generate_synthetic_ohlc(start_price=22000.0, minutes=375):
    """
    synthetic data generation (1-min) for 1 day
    of an index (i.e. size==0)
    """
    start_time = datetime.strptime("09:15", "%H:%M")
    times = [start_time + timedelta(minutes=i) for i in range(minutes)]

    # simulate log-normal drift + volatility + noise
    mu = 0.00005     # mean drift per minute (~0.3% daily)
    sigma = 0.0008   # per-minute volatility (~1.2% daily)
    returns = np.random.normal(mu, sigma, minutes)
    prices = start_price * np.exp(np.cumsum(returns))  # geometric Brownian motion

    highs = prices * (1 + np.random.uniform(0, 0.001, minutes))
    lows  = prices * (1 - np.random.uniform(0, 0.001, minutes))

    df = pd.DataFrame({
        "datetime": times,
        "open": prices,
        "high": highs,
        "low": lows,
        "close": prices,
        # "volume": [0] * minutes
    })
    return df


class RealTimeRiskEngine:
    def __init__(self, df, initial_capital=100_000):
        self.df = df
        self.initial_capital = initial_capital
        self.alerts = []

        self.dd_limit = -2.0       # % intraday drawdown
        self.var95_limit = -1.0    # % one-minute VaR
        # self.vol_limit = 1.5       # % hourly realized vol

    def calculate_metrics(self, data):
        closes = data["close"].values
        returns = np.diff(closes) / closes[:-1] * 100

        # ---- performance metrics ----
        pnl_pct = (closes[-1] - closes[0]) / closes[0] * 100
        # realized_vol = np.std(returns[-60:]) * np.sqrt(60) if len(returns) > 60 else np.nan
        max_dd = (np.min(closes) - np.max(closes)) / np.max(closes) * 100
        var95 = np.percentile(returns, 5)
        sharpe = (np.mean(returns) / (np.std(returns) + 1e-9)) * np.sqrt(60)
        cumulative_ret = (1 + returns / 100).prod() - 1

        metrics = {
            "PnL(%)": pnl_pct,
            "CumReturn(%)": cumulative_ret * 100,
            # "RealizedVol(%)": realized_vol,
            "MaxDrawdown(%)": max_dd,
            "VaR95(%)": var95,
            "Sharpe": sharpe,
            "LastReturn(%)": returns[-1] if len(returns) else 0
        }
        return metrics

    def check_thresholds(self, m, datetime):
        if m["MaxDrawdown(%)"] < self.dd_limit:
            self.alerts.append({'cause': 'DrawDown Breach', 'time': datetime, 'value': f'{m["MaxDrawdown(%)"]:.2f}%'}) # this to be replaced with mongo insert logic
            sys.exit(f"[Drawdown breach] {m['MaxDrawdown(%)']:.2f}%\n")
        if m["VaR95(%)"] < self.var95_limit:
            self.alerts.append({'cause': 'Value at Risk Breach', 'time': datetime, 'value': f'{m["VaR95(%)"]:.2f}%'}) # this to be replaced with mongo insert logic
            sys.exit(f"[VaR breach] {m['VaR95(%)']:.2f}%")
            
        # if m["RealizedVol(%)"] > self.vol_limit:
        #     self.alerts.append(f"[Volatility regime change]: {m['RealizedVol(%)']:.2f}%")

    def stream(self, delay=0.1):
        for i in range(10, len(self.df) + 1):
            os.system("clear")
            print(f"{'Time':<5} | {'PnL%':<6} | {'CumRet%':<7} | {'MaxDD%':<7} | {'VaR95%':<7} | {'Sharpe':<6}")
            print("-" * 60)
            m = self.calculate_metrics(self.df.iloc[:i])
            self.check_thresholds(m, self.df.iloc[i-1]['datetime'].strftime('%H:%M'))
            print(f"{self.df.iloc[i-1]['datetime'].strftime('%H:%M')} | "
                  f"{m['PnL(%)']:<6.2f} | {m['CumReturn(%)']:<7.2f} | {m['MaxDrawdown(%)']:<7.2f} | "
                  f"{m['VaR95(%)']:<7.2f} | {m['Sharpe']:<6.2f}")
            
            time.sleep(delay)

if __name__ == "__main__":
    df = generate_synthetic_ohlc()
    engine = RealTimeRiskEngine(df)
    engine.stream(delay=0.08)
