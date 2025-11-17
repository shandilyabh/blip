"""
to upkeep high frequency data from
upstox api
"""

import asyncio
import json
from bson import ObjectId # type: ignore
import ssl
import websockets # type: ignore
import requests # type: ignore
from google.protobuf.json_format import MessageToDict # type: ignore
from dotenv import load_dotenv # type: ignore
import os
from pathlib import Path
import MarketDataFeedV3_pb2 as pb

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)


def get_market_data_feed_authorize_v3():
    """Get authorization for market data feed."""
    access_token = os.getenv("ACCESS_TOKEN")
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
    response = get_market_data_feed_authorize_v3()
    
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
                "instrumentKeys": ["NSE_INDEX|Nifty Bank", "NSE_INDEX|Nifty 50"]
            }
        }

        # Convert data to binary and send over WebSocket
        binary_data = json.dumps(data).encode('utf-8')
        await websocket.send(binary_data)

        # Continuously receive and decode data from WebSocket
        while True:
            message = await websocket.recv()
            decoded_data = decode_protobuf(message)

            # Convert the decoded data to a dictionary
            data_dict = MessageToDict(decoded_data)

            # Print the dictionary representation
            print('\n' + json.dumps(data_dict))


# Execute the function to fetch market data
asyncio.run(fetch_market_data())