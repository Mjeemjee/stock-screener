"""Reject private or unexpected data before publishing a static website."""
import argparse
import json
import math
from pathlib import Path
import re


PUBLIC_DATA = {
    "screener_results.json", "tracking.json", "lab.json", "research.json", "long_research.json", "history/hk.json",
    "history/us.json", "history/index.json", "history/etf.json",
}

CANDLE_FILE = re.compile(r"candles/(?:HK\.[0-9]{5}|US\.[A-Z0-9][A-Z0-9.\-]{0,29})\.json\Z")


def public_data_names(data):
    return PUBLIC_DATA | {file.relative_to(data).as_posix() for file in (data / "candles").glob("*.json")
                          if CANDLE_FILE.fullmatch(file.relative_to(data).as_posix())}


def verify_candles(file):
    from datetime import datetime
    value = json.loads(file.read_text(encoding="utf-8-sig"))
    keys = {"schema_version", "code", "generated_at", "as_of", "price_basis", "volume_unit", "source", "status", "bars", "rejected_rows"}
    if not isinstance(value, dict) or set(value) != keys or value["schema_version"] != 1 or value["code"] != file.stem:
        raise ValueError(f"Invalid public candle payload: {file.name}")
    if (value["price_basis"] != "source_adjusted" or value["volume_unit"] != "source_units" or
            value["source"] not in ("tracking_history", "chart_history") or value["status"] not in ("available", "unavailable") or
            type(value["rejected_rows"]) is not int or value["rejected_rows"] < 0):
        raise ValueError("Unexpected candle metadata")
    if datetime.fromisoformat(value["generated_at"].replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("Candle generation time requires timezone")
    bars = value["bars"]
    if not isinstance(bars, list) or len(bars) > 260:
        raise ValueError("Invalid candle count")
    previous = 0
    for row in bars:
        if not isinstance(row, list) or len(row) != 6 or not all(type(v) in (int, float) and math.isfinite(v) for v in row):
            raise ValueError("Invalid OHLCV row")
        day, o, h, low, close, volume = row
        if type(day) is not int or day <= previous or min(o, h, low, close) <= 0 or h < max(o, close) or low > min(o, close) or volume < 0:
            raise ValueError("Invalid OHLCV geometry or date order")
        datetime.strptime(str(day), "%Y%m%d")
        previous = day
    if value["as_of"] != (bars[-1][0] if bars else None) or (value["status"] == "available") != bool(bars):
        raise ValueError("Candle coverage metadata disagrees with bars")


def verify(directory):
    directory = Path(directory)
    if not (directory / "index.html").is_file():
        raise ValueError("The built website is missing index.html")
    for file in directory.rglob("*"):
        if not file.is_file():
            continue
        name = file.name.lower()
        if name.startswith(".env") or name in {"positions.json", "quotes.json"} or file.suffix.lower() in {".pem", ".key"}:
            raise ValueError(f"Private file must not be published: {file.relative_to(directory)}")
    data = directory / "data"
    actual = {file.relative_to(data).as_posix() for file in data.rglob("*") if file.is_file()}
    unexpected = actual - public_data_names(data)
    if unexpected:
        raise ValueError(f"Unexpected public data files: {sorted(unexpected)}")
    for name in ("screener_results.json", "tracking.json"):
        payload = json.loads((data / name).read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object: {name}")
    tracked = json.loads((data / "tracking.json").read_text(encoding="utf-8-sig")).get("securities", {})
    for name in actual:
        if CANDLE_FILE.fullmatch(name):
            file = data / name
            if file.is_symlink() or file.stem not in tracked:
                raise ValueError("Only tracked security candles may be published")
            verify_candles(file)
    return sorted(actual)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="portfolio-board/dist")
    args = parser.parse_args()
    print("Public build verified:", ", ".join(verify(args.directory)))
