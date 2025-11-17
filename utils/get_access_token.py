"""
script to obtain and append the upstox access token
for the day required to use the MarketDataFeed Websocket
used for live-streaming market data
"""

import requests # type: ignore
import os
from dotenv import load_dotenv, set_key # type: ignore
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)

# has to be obtained daily, manually
auth_code = os.getenv("CODE")

client_id = os.getenv("UPSTOX_API")
client_secret = os.getenv("UPSTOX_SECRET")
redirect_uri = "http://127.0.0.1"

# the request
url = "https://api.upstox.com/v2/login/authorization/token"
headers = {
    "accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}
data = {
    "code": auth_code,
    "client_id": client_id,
    "client_secret": client_secret,
    "redirect_uri": redirect_uri,
    "grant_type": "authorization_code"
}

# POST
response = requests.post(url, headers=headers, data=data)

if response.status_code == 200:
    json_response = response.json()
    access_token = json_response["access_token"]

    set_key(str(env_path), 'ACCESS_TOKEN', access_token)
    
    print("Successfully obtained and updated the access_token")
else:
    print(f"Failed to get access token: {response.json()}")
