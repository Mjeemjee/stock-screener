"""Reject private or unexpected data before publishing a static website."""
import argparse
import json
from pathlib import Path


PUBLIC_DATA = {
    "screener_results.json", "tracking.json", "lab.json", "research.json", "long_research.json", "history/hk.json",
    "history/us.json", "history/index.json", "history/etf.json",
}


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
    unexpected = actual - PUBLIC_DATA
    if unexpected:
        raise ValueError(f"Unexpected public data files: {sorted(unexpected)}")
    for name in ("screener_results.json", "tracking.json"):
        payload = json.loads((data / name).read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object: {name}")
    return sorted(actual)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="portfolio-board/dist")
    args = parser.parse_args()
    print("Public build verified:", ", ".join(verify(args.directory)))
