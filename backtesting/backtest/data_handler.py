"""
data handler module for loading and
processing data
"""

from typing import Optional

import pandas as pd # type: ignore
from openbb import obb # type: ignore


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
    
    def load_data_from_csv(self, file_path) -> pd.DataFrame:
        """loading data from CSV file."""
        return pd.read_csv(file_path, parse_dates=True, index_col="date")
    
# if __name__ == "__main__":
    # data = DataHandler("AAPL").load_data()
    # print(data.head())