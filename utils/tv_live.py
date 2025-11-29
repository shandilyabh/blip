"""
live market data streaming via
TradingView DataFeed
"""

from tvDatafeed import TvDatafeed, Interval # type: ignore
import time
import os
from tqdm import tqdm # type: ignore
import pandas as pd # type: ignore
from pymongo import MongoClient # type: ignore
from dotenv import load_dotenv # type: ignore

load_dotenv()

client = MongoClient(os.getenv("MONGO_CONN_STRING"))
db = client["duckducktrade"]
collection = db["ethusd-tvdatafeed"]

class DataLengthError(Exception):
    pass

def calculate_SMA(data:pd.DataFrame, long_period:int, short_period:int):
    """
    calculate simple moving averages
    long and short
    """
    if len(data) < long_period:
        raise DataLengthError(f"Insufficient data length: {len(data)} < {long_period} [length of provided data is less than the SMA-Long Period]")
    
    sum_short = 0
    sum_long = 0

    # for short:
    for i in range(1, short_period + 1):
        sum_short += data['close'].iloc[(-1) * i]

    for i in range(1, long_period + 1):
        sum_long += data['close'].iloc[(-1) * i]
    
    return [sum_long/long_period, sum_short/short_period]

def main():
    """
    recieves data from trading view
    does operations on it
    saves it in mongo's collection
    """
    tv = TvDatafeed()

    while True:
        etherum_usd_data = tv.get_hist(symbol='ETHUSD',exchange='BINANCE',interval=Interval.in_1_minute,n_bars=50)

        short, long = calculate_SMA(data=etherum_usd_data, long_period=50, short_period=14)

        print(f'\nLong SMA: {long:.2f} | Short SMA: {short:.2f}')

        print(f'Last Cose Price: {etherum_usd_data.iloc[-1].close:.2f}\n')

        try:
            collection.insert_one({
                'timestamp': str(pd.Timestamp(etherum_usd_data.index[-1])),
                'open' : etherum_usd_data['open'].iloc[-1],
                'high' : etherum_usd_data['high'].iloc[-1],
                'low' : etherum_usd_data['low'].iloc[-1],
                'close' : etherum_usd_data['close'].iloc[-1],
                'volume' : etherum_usd_data['volume'].iloc[-1],
                'short_sma': round(short, 3),
                'long_sma' : round(long, 3)
            })
        except Exception as e:
            print(f"Couldn't append data to the collection | Error: {e}")

        # print(type(etherum_usd_data.index[-1]))
        
        for _ in tqdm(range(60), desc="next bar in:"):
            time.sleep(1)

if __name__ == "__main__":
    main()
