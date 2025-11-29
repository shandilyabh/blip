"""
test file for tick-data aggregation
"""

import asyncio
import json
import ssl
import os
import websockets # type: ignore
import signal
import functools
import aiohttp # type: ignore
from datetime import datetime
from bson import ObjectId  # type: ignore
from google.protobuf.json_format import MessageToDict  # type: ignore
from dotenv import load_dotenv  # type: ignore
from concurrent.futures import ThreadPoolExecutor

from utils import MarketDataFeedV3_pb2 as pb
from aggregator import TickAggregator 

load_dotenv()

MONGO_URI = os.getenv("MONGO_CONN_STRING")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")


def decode_protobuf(buffer):
    feed_response = pb.FeedResponse()  # type: ignore
    feed_response.ParseFromString(buffer)
    return feed_response


def _decode_and_parse_sync(buffer):
    """
    Decodes protobuf, converts to dict, and extracts tick data.
    """
    decoded = decode_protobuf(buffer)
    data_dict = MessageToDict(decoded)
    ticks = []

    for feed_key, feed_val in data_dict.get("feeds", {}).items():
        ff = feed_val.get("fullFeed", {}).get("indexFF", {})
        ltpc = ff.get("ltpc", {})
        
        price = float(ltpc.get("ltp", 0))
        size = float(ltpc.get("ltq", 0))
        ts_ms = int(ltpc.get("ltt", 0))
        
        if price > 0 and ts_ms > 0: # Basic data validation
            symbol = feed_key.split("|")[-1]
            tick = (symbol, price, size, ts_ms)
            print(f"[{datetime.now()}] [.] Parsed tick: {tick}")
            ticks.append(tick)
            
    return ticks


async def get_market_data_feed_authorize_v3():
    """
    Fetches websocket auth token asynchronously using aiohttp
    """
    headers = {"Accept": "application/json", "Authorization": f"Bearer {ACCESS_TOKEN}"}
    url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
    
    print(f"[{datetime.now()}] Getting websocket auth...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()  # Raises error for 4xx/5xx
                return await resp.json()
        except aiohttp.ClientError as e:
            print(f"[{datetime.now()}] --[X]-- HTTP Error getting auth: {e}")
            raise


async def fetch_market_data(aggregator: TickAggregator, loop: asyncio.AbstractEventLoop, executor: ThreadPoolExecutor):
    """
    [BACKGROUND TASK]
    Connects to websocket and feeds ticks to the aggregator's queue.
    """
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        response = await get_market_data_feed_authorize_v3()
        ws_url = response.get("data", {}).get("authorized_redirect_uri")
        if not ws_url:
            print(f"[{datetime.now()}] --[X]-- Could not get websocket URL: {response}")
            return

        async with websockets.connect(
            ws_url, ssl=ssl_context, ping_interval=20, ping_timeout=10
        ) as websocket:
            print(f"[{datetime.now()}] [.] Websocket connected.")
            await asyncio.sleep(1)
            data = {
                "guid": str(ObjectId()),
                "method": "sub",
                "data": {"mode": "full", "instrumentKeys": ["NSE_INDEX|Nifty 50"]},
            }
            await websocket.send(json.dumps(data).encode("utf-8"))
            print(f"[{datetime.now()}] [.] Subscribed to Nifty 50.")

            while True:
                msg = await websocket.recv()
                
                parsed_ticks = await loop.run_in_executor(
                    executor, _decode_and_parse_sync, msg
                )

                for tick in parsed_ticks:
                    await aggregator.process_tick(*tick)

    except asyncio.CancelledError:
        print(f"[{datetime.now()}] [.] Websocket task shutting down.")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[{datetime.now()}] --[X]-- Websocket connection closed: {e}")
    except Exception as e:
        print(f"[{datetime.now()}] --[X]-- Error in websocket loop: {e}")
        import traceback
        traceback.print_exc() # Print full error


async def shutdown(sig, loop, aggregator, executor, tasks):
    """Graceful shutdown handler."""
    print(f"\n[{datetime.now()}] [!] Received exit signal {sig.name}...")

    # Cancel all main tasks
    print(f"[{datetime.now()}] [!] Cancelling {len(tasks)} background tasks...")
    for t in tasks:
        t.cancel()
    
    # Wait for tasks to finish cancelling
    await asyncio.gather(*tasks, return_exceptions=True)

    # Now, flush all remaining data from the aggregator
    await aggregator.flush_all_and_close()
    
    # shut down the executor
    print(f"[{datetime.now()}] [!] Shutting down thread pool executor...")
    executor.shutdown(wait=True)
    
    print(f"[{datetime.now()}] [!] Event loop stopping.")
    loop.stop()


async def main():
    # Initialize the aggregator and the thread pool executor
    aggregator = TickAggregator(MONGO_URI)
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='LiveFeedExecutor')
    
    await aggregator.connect_db()

    loop = asyncio.get_event_loop()
    tasks = []

    # Update the shutdown handler to also close the executor
    def shutdown_handler(sig):
        asyncio.create_task(shutdown(sig, loop, aggregator, executor, tasks))

    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, shutdown_handler, s)

    # Create and register all background tasks
    flusher_task = asyncio.create_task(aggregator.flush_completed())
    processor_task = asyncio.create_task(aggregator._run_processor())
    ws_task = asyncio.create_task(fetch_market_data(aggregator, loop, executor))
    
    tasks.extend([flusher_task, processor_task, ws_task])

    print(f"[{datetime.now()}] All tasks started. Running... (Press Ctrl+C to stop)")
    
    # This will run forever until a signal is received
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print(f"[{datetime.now()}] [!] Program force-exited.")
