"""
high frequency data from upstox api
"""

import asyncio
import json
from urllib.parse import quote 
from bson import ObjectId # type: ignore
import ssl
import websockets # type: ignore
import requests # type: ignore
from google.protobuf.json_format import MessageToDict # type: ignore
from dotenv import load_dotenv # type: ignore
import os
from pathlib import Path
import utils.MarketDataFeedV3_pb2 as pb
# import MarketDataFeedV3_pb2 as pb

env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)

# INSTRUMENT = "NSE_INDEX|Nifty 50"
INSTRUMENT = "NSE_EQ|INE839G01010"

def get_market_data_feed_authorize_v3(access_token):
    """Get authorization for market data feed."""
    # access_token = os.getenv("ACCESS_TOKEN")
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    url = 'https://api.upstox.com/v3/feed/market-data-feed/authorize'
    api_response = requests.get(url=url, headers=headers)
    return api_response.json()


def decode_protobuf(buffer):
    """Decode protobuf message."""
    feed_response = pb.FeedResponse() # type: ignore
    feed_response.ParseFromString(buffer)
    return feed_response


async def fetch_market_data():
    """Fetch market data using WebSocket and print it."""

    # Create default SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Get market data feed authorization
    response = get_market_data_feed_authorize_v3(access_token=None)
    # print(response)
    
    # Connect to the WebSocket with SSL context
    async with websockets.connect(response["data"]["authorized_redirect_uri"], ssl=ssl_context) as websocket:
        print('Connection established')

        await asyncio.sleep(1)  # Wait for 1 second

        # Data to be sent over the WebSocket
        data = {
            "guid": str(ObjectId),
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": [INSTRUMENT]
            }
        }

        # Convert data to binary and send over WebSocket
        binary_data = json.dumps(data).encode('utf-8')
        await websocket.send(binary_data)

        current_ts = 0
        # Continuously receive and decode data from WebSocket
        while True:
            message = await websocket.recv()
            decoded_data = decode_protobuf(message)

            # Convert the decoded data to a dictionary
            data_dict = MessageToDict(decoded_data)
            # print(data_dict)

            if data_dict.get("type") == "live_feed":
                try:
                    minute = data_dict.get("feeds", {}).get(INSTRUMENT).get("fullFeed").get("indexFF").get("marketOHLC").get("ohlc", [])[1]

                    if int(minute.get("ts")) > current_ts:
                        current_ts = int(minute.get("ts"))         
                        current_minute_data = {}
                        if minute.get("interval") == "I1":
                            current_minute_data["ts"] = current_ts
                            current_minute_data["open"] = minute.get("open", 0)
                            current_minute_data["high"] = minute.get("high", 0)
                            current_minute_data["low"] = minute.get("low", 0)
                            current_minute_data["close"] = minute.get("close", 0)

                        print('\n[RECORDED]' + json.dumps(current_minute_data))
                        current_ts = int(minute.get("ts"))
                except Exception as e:
                    print(f"[ERROR] - The recieved message from websocket didn't match the JSON schema being accessed: {e}")
            
def fetch_intraday_historical_data(instrument, access_token) -> list[list[float]]:
    """
    fetches intraday bars of the instrument
    upto the point the script is ran
    """
    instrument = quote(instrument)

    url = f'https://api.upstox.com/v3/historical-candle/intraday/{instrument}/minutes/1'
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json().get('data').get('candles')
        data.reverse()
        if len(data) > 0:
            return data
            # print(response.json())
    else:
        print(f"Error: {response.status_code} - {response.text}")
    
    return [[]]

# data = fetch_intraday_historical_data("NSE_EQ|INE839G01010", os.getenv("ACCESS_TOKEN"))
# data.reverse()
# print(data)

# asyncio.run(fetch_market_data())