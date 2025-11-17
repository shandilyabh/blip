"""
helper script for fetching historical data from yfinance
"""
import yfinance as yf # type: ignore
from pathlib import Path
from tqdm import tqdm # type: ignore
import yaml # type: ignore


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

def download_csv(tick: str, period="1y", interval="1d") -> None:
    """
    Download historical data for a ticker and save as CSV in /data
    """
    ticker = yf.Ticker(tick)
    df = ticker.history(start="2016-01-01", end="2020-01-01", auto_adjust=False)
    file_path = DATA_DIR / f"{tick}.csv"
    df.to_csv(file_path)

if __name__ == "__main__":
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    instruments = config.get("symbols", [])
    for tick in tqdm(instruments, desc="Downloading Data", colour='blue'):
        try:
            download_csv(tick)
        except Exception as e:
            print(f"Error downloading {tick}: {e}")
