"""Restore only the explicit published market data, never private account data."""
from pathlib import Path
import requests

BASE = "https://mjeemjee.github.io/stock-screener/data/"
OUT = Path(__file__).resolve().parents[1] / "portfolio-board/public/data"
FILES = ("screener_results.json", "tracking.json", "history/hk.json", "history/us.json",
         "history/index.json", "history/etf.json")


def main(output=OUT, get=requests.get):
    for name in FILES:
        response = get(BASE + name, timeout=90, headers={"Cache-Control": "no-cache"})
        if response.status_code == 404 and name == "history/etf.json":
            print("Optional ETF history is not published; retaining the current availability state")
            continue
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid public payload: {name}")
        target = Path(output) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        print("Restored public market data:", name)


if __name__ == "__main__":
    main()
