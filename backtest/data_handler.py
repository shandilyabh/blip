"""
data handler module for loading and
processing data
"""

from typing import Optional

import pandas as pd # type: ignore
from openbb import obb # type: ignore
import yfinance as yf # type: ignore


class DataHandler:
    """
    Data handler class for loading and processing data
    """
    def __init__(
            self,
            symbol: str,
            start_date: Optional[str]=None,
            end_date: Optional[str]=None,
            provider: str = 'fmp'
    ):
        """
        sets the instance variables: for downloading and writing data
        """
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.provider = provider

    def load_data(self) -> pd.DataFrame | dict[str, pd.DataFrame]:
        """
        downloading the data from openbb
        """
        data = obb.equity.price.historical(
            symbol=self.symbol,
            start_date = self.start_date,
            end_date = self.end_date,
            provider = self.provider
        ).to_df()

        if "," in self.symbol:
            data = data.reset_index().set_index("symbol")
            return {symbol: data.loc[symbol] for symbol in self.symbol.split(",")}
        
        return data
    
    def fetch_data(self) -> pd.DataFrame:
        '''
        load_data only, but supports indian equities
        '''
        df = yf.Ticker(self.symbol).history(
            start=self.start_date,
            end=self.end_date,
            auto_adjust=False
        ).dropna()

        return self.yf_to_openbb(df, self.symbol)
    
    def load_data_from_csv(self, file_path) -> pd.DataFrame:
        """loading data from CSV file."""
        return pd.read_csv(file_path, parse_dates=True, index_col="date")
    
    def yf_to_openbb(self, df: pd.DataFrame, symbol: str):
        out = df.copy()

        # normalise names
        out = out.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        # index normalisation
        out.index = out.index.tz_localize(None).normalize() # type: ignore
        out.index.name = "date"

        out["vwap"] = (out["open"] + out["high"] + out["low"] + out["close"]) / 4

        out["change"] = out["close"].diff()
        out["change_percent"] = out["close"].pct_change()

        out["symbol"] = symbol

        out = out[["open","high","low","close","volume","vwap","change","change_percent","symbol"]]
        out = out.dropna(subset=["change", "change_percent"])

        return out
    
# if __name__ == "__main__":
#     data = DataHandler("AAPL").fetch_data()
#     print(data.head()) # type: ignore