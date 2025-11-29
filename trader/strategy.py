"""
ingests market data (one unit)
generates signal +-1
returns only a flag
"""

import os
from dotenv import load_dotenv # type: ignore
from pathlib import Path
import pandas as pd # type: ignore
from utils.fetch_data_upstox import fetch_intraday_historical_data
from typing import Any


env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")


class SMA_CROSS:
    def __init__(self, short_sma: int, long_sma: int, instrument: str):
        self.instrument: str = instrument
        self.period_s: int = short_sma
        self.period_l: int = long_sma
        self._data: list = [] # close prices only
        self.sma_s: Any
        self.sma_l: Any
        self.prev_sma_s: Any
        self.prev_sma_l: Any


    def apply_strategy(self):
        """
        simple moving averages crossover
        """
        
        if not (isinstance(self.prev_sma_l, float) and isinstance(self.prev_sma_s, float)):
            return 0

        # print(f"[Prev_Small: {self.prev_sma_s} | Prev_Long: {self.prev_sma_l}]\n[Current_Small: {self.sma_s} | Current_Long: {self.sma_l}]\n")

        if (self.prev_sma_l > self.prev_sma_s) and (self.sma_l < self.sma_s):
            return 1 # buy
        elif (self.prev_sma_l < self.prev_sma_s) and (self.sma_l > self.sma_s):
            return -1 # sell
        
        return 0


    def patch(self):
        '''
        integrating a strategy into the system
        '''
        self.load_historical_bars(self.instrument)
        if len(self._data) >= self.period_l:
            self.prev_sma_s = pd.Series(self._data[len(self._data) - self.period_s:]).mean()
            self.prev_sma_l = pd.Series(self._data[len(self._data) - self.period_l:]).mean()

    
    def dummy_patch(self):
        """
        Simulates loading historical data by generating a synthetic price series.
        This allows the strategy to be primed with enough data to calculate
        initial SMAs for testing purposes.
        """
        import random
        
        # We need at least self.period_l bars to calculate the initial long SMA.
        # Let's generate a bit more for a better starting point.
        num_bars = self.period_l + 20
        
        # Generate a simple random walk for the close prices.
        px = 1000 + (hash(self.instrument) % 500) # Start price based on instrument
        dummy_prices = []
        for _ in range(num_bars):
            px += random.uniform(-1, 1)
            dummy_prices.append(px)
            
        self._data = dummy_prices
        
        print(f"[{self.instrument}] DUMMY PATCH: Loaded {len(self._data)} synthetic bars.")

        # This part is identical to the real patch() method.
        # It calculates the initial SMAs based on the synthetic historical data.
        if len(self._data) >= self.period_l:
            self.prev_sma_s = pd.Series(self._data[len(self._data) - self.period_s:]).mean()
            self.prev_sma_l = pd.Series(self._data[len(self._data) - self.period_l:]).mean()


    async def generate_signal(self, bar):
        '''
        everything that happens as each bar is recieved
        from the market adapter
        '''
        try: 
            self._data.append(bar.get("close")) 
        except Exception as e: 
            print("[ERROR] recieved bar doesn't have a close price: ", e) 

        if len(self._data) < self.period_l:
            return 0

        self.sma_s = pd.Series(self._data[len(self._data) - self.period_s:]).mean()
        self.sma_l = pd.Series(self._data[len(self._data) - self.period_l:]).mean()

        signal = self.apply_strategy()

        # update the previous state for the next iteration
        self.prev_sma_s = self.sma_s
        self.prev_sma_l = self.sma_l
        
        return signal


    def load_historical_bars(self, instrument): 
        """
        loads historical data from upstox
        and puts the close prices in the self._data list
        """
        fetched_data = fetch_intraday_historical_data(instrument, ACCESS_TOKEN)
        self._data = [x[4] for x in fetched_data]
