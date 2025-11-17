"""
implements the upstox live data feed websocket connection
standardises the data
saves it to a mongodb collection
"""

from pymongo import MongoClient # type: ignore
from dotenv import load_dotenv # type: ignore
import os

load_dotenv()

client = MongoClient(os.getenv("MONGO_CONN_STRING"))
db = client["duckducktrade"]
collection = db["market-adapter-data"]

print(collection.count_documents({}))