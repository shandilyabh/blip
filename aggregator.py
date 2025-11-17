"""
Tick aggregator for 1-minute OHLCV generation + MongoDB time-series flush
Uses motor (async) and an asyncio.Queue for non-blocking operation.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import pytz  # type: ignore
import motor.motor_asyncio # type: ignore
from pymongo.errors import ConnectionFailure # type: ignore


class TickAggregator:
    def __init__(self, mongo_uri, db_name="market-data", coll_name="bars_1m"):
        try:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                mongo_uri, serverSelectionTimeoutMS=5000
            )
            self.mongo = self.client[db_name][coll_name]
            print(f"[{datetime.now()}] MongoDB client initialised.")
        except Exception as e:
            print(f"[{datetime.now()}] --[x]-- MongoDB client init failed:", e)
            raise

        self.buckets = {}
        self.lock = asyncio.Lock()
        self.queue = asyncio.Queue()
        self.late_ms = 5000
        self.flush_interval = 1.0

        
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='AggregatorExecutor')

        self.tz = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(self.tz)
        
        is_top_of_minute = now_ist.second == 0 and now_ist.microsecond == 0
        
        current_minute_truncated = now_ist.replace(second=0, microsecond=0)

        if is_top_of_minute:
            # Started exactly on the minute, start processing now.
            self.start_time = current_minute_truncated
        else:
            # Started mid-minute, wait for the *next* minute to begin.
            self.start_time = current_minute_truncated + timedelta(minutes=1)

        
        self.start_time_utc_ms = int(self.start_time.astimezone(timezone.utc).timestamp() * 1000)
        
        print(f"[{datetime.now()}] [.] Current IST: {now_ist.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[{datetime.now()}] [.] Will start processing ticks from: {self.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    async def connect_db(self):
        try:
            await self.client.admin.command("ping")
            print(
                f"[{datetime.now()}] -- Connected to MongoDB ({self.mongo.database.name}.{self.mongo.name})"
            )
        except ConnectionFailure as e:
            print(f"[{datetime.now()}] --[x]-- MongoDB connection failed:", e)
            raise

    def _bucket_key(self, symbol, ts_ms):
        return (symbol, ts_ms - (ts_ms % 60000))

    async def process_tick(self, symbol, price, size, ts_ms):
        try:
            await self.queue.put((symbol, price, size, ts_ms))
        except Exception as e:
            print(f"[{datetime.now()}] --[X]-- Error putting tick on queue:", e)

    
    def _update_buckets_sync(self, tick, start_time_utc_ms):
        symbol, price, size, ts_ms = tick
        
        
        now_ms = int(time.time() * 1000)
        bucket_start_ms = ts_ms - (ts_ms % 60000)
        bucket_end_ms = bucket_start_ms + 60000

        if now_ms - bucket_end_ms >= self.late_ms:
            return False # tick was discarded

        if ts_ms < start_time_utc_ms:
            return False

        key = (symbol, bucket_start_ms)
        b = self.buckets.get(key)
        if not b:
            self.buckets[key] = {
                "open": price, "high": price, "low": price, "close": price,
                "volume": size, "count": 1, "start_ms": key[1],
            }
        else:
            b["high"] = max(b["high"], price)
            b["low"] = min(b["low"], price)
            b["close"] = price
            b["volume"] += size
            b["count"] += 1
        
        return True 

    async def _run_processor(self):
        """
        Reads ticks from the queue and updates the in-memory buckets.
        """
        print(f"[{datetime.now()}] [.] Tick processor coroutine started.")
        loop = asyncio.get_running_loop() 

        while True:
            try:
                tick = await self.queue.get()

                async with self.lock:
                    await loop.run_in_executor(
                        self.executor, 
                        self._update_buckets_sync, 
                        tick, 
                        self.start_time_utc_ms
                    )

                self.queue.task_done()

            except asyncio.CancelledError:
                print(f"[{datetime.now()}] [.] Tick processor shutting down.")
                return
            except Exception as e:
                print(f"[{datetime.now()}] --[X]-- Error in tick processor:", e)


    def _find_flushable_buckets_sync(self, cutoff_ms):
        """ bucket discovery logic. """
        to_flush = []
        for (symbol, start_ms), b in self.buckets.items():
            if start_ms + 60000 <= cutoff_ms:
                to_flush.append((symbol, b))
        
        # return the list of buckets to be flushed. The deletion will happen back on the main thread inside the lock.
        return to_flush

    async def flush_completed(self):
        print(f"[{datetime.now()}] [.] Flush coroutine started.")
        loop = asyncio.get_running_loop()
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                
                now_ms = int(time.time() * 1000)
                cutoff = now_ms - self.late_ms
                

                # find which buckets to flush in a background thread. a read-only operation and is safe to do outside the lock.
                to_flush = await loop.run_in_executor(
                    self.executor, self._find_flushable_buckets_sync, cutoff
                )
                
                if to_flush:
                    async with self.lock:
                        for symbol, b in to_flush:
                            if (symbol, b['start_ms']) in self.buckets:
                                del self.buckets[(symbol, b['start_ms'])]
                    
                    await self._insert_to_db(to_flush)

            except asyncio.CancelledError:
                print(f"[{datetime.now()}] [.] Flusher shutting down.")
                return
            except Exception as e:
                print(f"[{datetime.now()}] --[X]-- Error in flush loop:", e)
                await asyncio.sleep(2)


    def _prepare_docs_sync(self, bars_to_flush):
        """
        formatting the doc to be inserted into Mongo
        """
        docs = []
        for symbol, b in bars_to_flush:
            dt_utc = datetime.fromtimestamp(b["start_ms"] / 1000, tz=timezone.utc)
            dt_ist = dt_utc.astimezone(self.tz)
            doc = {
                "meta": {"symbol": symbol},
                "ts": dt_utc,
                "ts_ist": dt_ist.strftime('%Y-%m-%d %H:%M:%S'),
                "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"],
                "volume": b["volume"], "count": b["count"],
            }
            docs.append(doc)
        return docs

    async def _insert_to_db(self, bars_to_flush):
        
        loop = asyncio.get_running_loop()

        docs = await loop.run_in_executor(
            self.executor, self._prepare_docs_sync, bars_to_flush
        )

        if not docs:
            return

        print(f"\n[{datetime.now()}] [...] Preparing to insert {len(docs)} bar(s):")
        for d in docs[:5]:
             print(f"→ {d['meta']['symbol']} @ {d['ts_ist']} IST: O:{d['open']} H:{d['high']} L:{d['low']} C:{d['close']}")
        if len(docs) > 5:
            print(f"  ...and {len(docs) - 5} more.")

        try:
            print(f"[{datetime.now()}] [DB] Writing {len(docs)} bars to MongoDB...")
            result = await self.mongo.insert_many(docs)
            print(
                f"[{datetime.now()}] ---- Inserted {len(result.inserted_ids)} bars into MongoDB.\n"
            )
        except Exception as e:
            print(f"[{datetime.now()}] --[X]-- Mongo insert_many error:", e)

    async def flush_all_and_close(self):
        print(f"\n[{datetime.now()}] [!] Shutdown initiated. Flushing all remaining buckets...")
        

        final_flush = []
        async with self.lock:
            if self.buckets:
                final_flush = [(key[0], b) for key, b in self.buckets.items()]
                self.buckets.clear()
        
        if final_flush:
            print(f"[{datetime.now()}] [!] Found {len(final_flush)} remaining bars to flush.")
            await self._insert_to_db(final_flush)
        else:
            print(f"[{datetime.now()}] [!] No remaining bars in memory.")

        self.client.close()
        print(f"[{datetime.now()}] [!] MongoDB connection closed.")
        

        # ensure that all pending tasks are completed before we exit.
        print(f"[{datetime.now()}] [!] Shutting down background thread pool...")
        self.executor.shutdown(wait=True)
        print(f"[{datetime.now()}] [!] Executor shut down.")