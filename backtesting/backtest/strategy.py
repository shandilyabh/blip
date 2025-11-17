'''
Base Strategy class
'''

import pandas as pd # type: ignore
# from data_handler import DataHandler

class Strategy:
    """
    base class for trading strategies
    """
    
    def __init__(self, indicators: dict, signal_logic):
        self.indicators = indicators
        self.signal_logic = signal_logic

    def generate_signals(self, data: pd.DataFrame | dict[str, pd.DataFrame]) -> pd.DataFrame | dict[str, pd.DataFrame]:
        """
        generate trading signals based on strategy's indicators and signal logic
        """
        if isinstance(data, dict):
            for _, asset_data in data.items():
                self._apply_strategy(asset_data)
        else:
            self._apply_strategy(data)

        return data
    
    def _apply_strategy(self, df: pd.DataFrame) -> None:
        """
        apply the strategy to a single dataframe
        """
        for name, indicator in self.indicators.items():
            df[name] = indicator(df)

        df["signal"] = df.apply(lambda row: self.signal_logic(row), axis=1)
        df["positions"] = df["signal"].diff().fillna(0)

indicators_sma = {
    "sma_20": lambda row: row["close"].rolling(window=20).mean(),
    "sma_60": lambda row: row["close"].rolling(window=60).mean()
}
sma = Strategy(
    indicators=indicators_sma,
    signal_logic=lambda row: 1 if row["sma_20"] > row["sma_60"] else -1
)

# data = DataHandler("AAPL").load_data()
# data = sma.generate_signals(data)

# print(data.head())