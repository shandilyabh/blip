"""
retrieves market data from websocket and
converts it to supply to the strategy for
signal generation
"""

import os
from bson import ObjectId # type: ignore
import json
from pathlib import Path
from dotenv import load_dotenv # type: ignore
from pymongo import MongoClient # type: ignore
from utils.fetch_data_upstox import (
    get_market_data_feed_authorize_v3,
    decode_protobuf,
)
import ssl
import websockets # type: ignore
import asyncio
from google.protobuf.json_format import MessageToDict # type: ignore


env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

''' mongo set-up '''
# client = MongoClient(os.getenv("MONGO_CONN_STRING"))
# db = client["duckducktrade"]
# collection = db["market-adapter-data"]

class MarketAdapter:
    """
    The main market adapter class
    
    supposed to:
    - send message to the upstox websocket
    - decode data coming from websocket
    - insert the data (once per minute) into DB
    """
    def __init__(self, instruments: list[str]):
        """
        class constructor

        instance variable: instruments : [list of instrument representation for upstox]
        """
        self.instruments = instruments
        self.queues = {instrument: asyncio.Queue() for instrument in instruments}
        self.current_ts = {instrument: 0 for instrument in instruments}
        print("Market Adapter Initiated")


    def insert_to_db(self, data_dict: dict) -> None:
        """
        insert 1-Min OHLC into MongoDB Collection
        """
        # collection.insert_one(data_dict)

    async def fetch(self):
        """
        fetching market data, with reconnect logic
        """
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        while True:
            try:
                response = get_market_data_feed_authorize_v3(ACCESS_TOKEN)

                async with websockets.connect(
                    response["data"]["authorized_redirect_uri"],
                    ssl=ssl_context
                ) as websocket:

                    print(f'Connection established for {len(self.instruments)} instruments')
                    await asyncio.sleep(1)

                    data = {
                        "guid": str(ObjectId()),
                        "method": "sub",
                        "data": {
                            "mode": "full",
                            "instrumentKeys": self.instruments
                        }
                    }

                    await websocket.send(json.dumps(data).encode('utf-8'))

                    while True:
                        try:
                            message = await websocket.recv()
                            decoded_data = decode_protobuf(message)
                            data_dict = MessageToDict(decoded_data)

                            if data_dict.get("type") != "live_feed":
                                continue

                            for instrument in self.instruments:
                                feed = data_dict.get("feeds", {}).get(instrument)
                                if not feed:
                                    continue

                                instrument_type = "equity" if "NSE_EQ" in instrument else "index"
                                ohlc_path = feed.get("fullFeed", {}).get("marketFF" if instrument_type == "equity" else "indexFF", {}).get("marketOHLC", {}).get("ohlc")
                                
                                if not ohlc_path or len(ohlc_path) < 2:
                                    continue
                                
                                minute = ohlc_path[1]

                                if int(minute.get("ts")) > self.current_ts[instrument]:
                                    current_minute_data = {
                                        "ts": minute.get("ts"),
                                        "open": minute.get("open", 0),
                                        "high": minute.get("high", 0),
                                        "low": minute.get("low", 0),
                                        "close": minute.get("close", 0),
                                    }
                                    if instrument_type == "equity":
                                        current_minute_data["volume"] = int(minute.get("vol", 0))
                                    
                                    await self.queues[instrument].put(current_minute_data)
                                    self.current_ts[instrument] = int(minute.get("ts"))

                        except Exception as inner:
                            print(f"[INNER-FETCH] Unhandled error: {inner}")
                            await asyncio.sleep(1)
                            break

            except Exception as outer:
                print(f"[OUTER-FETCH] Loop crash: {outer}")
                await asyncio.sleep(2)
                continue



    ''' dummy function here '''
    async def dummy_fetch(self):
        """
        Simulates OHLC bars for multiple instruments and ensures SMA crossovers occur.
        This is designed to test the multi-instrument processing pipeline.
        """
        import random
        import asyncio
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        print("\n--- Starting DUMMY fetch for all instruments ---")

        IST = ZoneInfo("Asia/Kolkata")
        
        # --- Initialize state for each instrument ---
        instrument_states = {}
        for instrument in self.instruments:
            # Assign a different starting price to each instrument for variety
            base_price = 1000 + (hash(instrument) % 1500)
            instrument_states[instrument] = {
                "px": base_price,
                "last_close": base_price,
                "phase_counter": 0,
                "range": 50 # Shorter phases to see crossovers faster
            }

        # Simulate for a total of 200 minutes
        for i in range(200):
            bar_time = datetime.now(IST) - timedelta(minutes=200-i)
            ts = str(int(bar_time.timestamp() * 1000))

            # In each simulated minute, generate and send a bar for EACH instrument
            for instrument in self.instruments:
                state = instrument_states[instrument]
                
                # Determine the price movement phase for this instrument
                phase_range = state["range"]
                phase = (state["phase_counter"] // phase_range) % 4
                
                if phase == 0: # Phase 1: mild drift
                    state["px"] += random.uniform(-5, 5)
                elif phase == 1: # Phase 2: strong upward push
                    state["px"] += random.uniform(10, 20)
                elif phase == 2: # Phase 3: downward slide
                    state["px"] -= random.uniform(10, 20)
                else: # Phase 4: normalisation
                    state["px"] += random.uniform(-5, 5)
                
                state["phase_counter"] += 1
                
                # Create the OHLC bar
                close_price = state["px"]
                open_price = state["last_close"]
                high_price = max(open_price, close_price) + random.uniform(0, 6)
                low_price = min(open_price, close_price) - random.uniform(0, 6)

                ohlc = {
                    "ts": ts,
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(low_price, 2),
                    "close": round(close_price, 2),
                    "volume": random.randint(10000, 50000)
                }
                
                state["last_close"] = close_price

                # --- Put the bar into the correct instrument's queue ---
                await self.queues[instrument].put(ohlc)
            
            # Wait 1 second to simulate the next minute's bars arriving
            await asyncio.sleep(2)

        print("--- Dummy fetch complete ---")

# ma = MarketAdapter("NSE_EQ|INE839G01010")
# asyncio.run(ma.fetch())