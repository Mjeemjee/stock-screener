"""Restore only the explicit published market data, never private account data."""
from pathlib import Path
import requests

BASE = "https://mjeemjee.github.io/stock-screener/data/"
OUT = Path(__file__).resolve().parents[1] / "portfolio-board/public/data"
FILES = ("screener_results.json", "tracking.json", "history/hk.json", "history/us.json",
         "history/index.json", "history/etf.json")


def main():
    for name in FILES:
        response = requests.get(BASE + name, timeout=90, headers={"Cache-Control": "no-cache"})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid public payload: {name}")
        target = OUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        print("Restored public market data:", name)


if __name__ == "__main__":
    main()
