"""Export display-only, per-security OHLCV from the tracking price sources.

Optional free-data fetching writes a separate chart cache; no ranking, evaluation
or frozen archive mutation. Kept outside screener/
so a presentation change does not alter the strategy version hash.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time

from screener.risk import completed_bars, load_histories, session_closes

ROOT = Path(__file__).resolve().parents[1]
CODE = re.compile(r"(?:HK\.[0-9]{5}|US\.[A-Z0-9][A-Z0-9.\-]{0,29})\Z")


def display_bars(raw, market, now):
    """Reject individual bad candles without inventing missing OHLC values."""
    clean, rejected = [], 0
    for row in raw:
        if (not isinstance(row, list) or len(row) < 6 or
                not all(type(v) in (int, float) and math.isfinite(v) for v in row[:6])):
            rejected += 1
            continue
        day, o, high, low, close, volume = row[:6]
        try:
            datetime.strptime(str(day), "%Y%m%d")
            valid = type(day) is int and min(o, high, low, close) > 0 and high >= max(o, close) and low <= min(o, close) and volume >= 0
        except ValueError:
            valid = False
        if valid:
            clean.append(row[:6])
        else:
            rejected += 1
    if any(b[0] <= a[0] for a, b in zip(clean, clean[1:])):
        return [], len(raw)
    return completed_bars(clean, market, now), rejected


def export(data_dir, cache_dir, *, as_of=None, limit=260, fetch_missing=False, max_fetch=4, fetcher=None):
    if not 1 <= limit <= 260 or not 0 <= max_fetch <= 20:
        raise ValueError("Chart export requires 1..260 bars and 0..20 fetches")
    data_dir, cache_dir = Path(data_dir), Path(cache_dir)
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Explicit timezone required")
    tracking = json.loads((data_dir / "tracking.json").read_text(encoding="utf-8-sig"))
    stocks, _ = load_histories(data_dir / "history")
    # Same whole-series preference as tracking.update_tracking. Never splice
    # differently adjusted price series, even when that would fill a gap.
    for file in sorted(cache_dir.glob("*.json")):
        node = json.loads(file.read_text(encoding="utf-8"))
        current = stocks.get(node["code"], [])
        if node["bars"] and (not current or int(node["bars"][-1][0]) > int(current[-1][0])):
            stocks[node["code"]] = node["bars"]
    # Separate display cache: these prices must never feed ranking or evaluation.
    chart_cache = cache_dir.parent / "chart_prices"
    sources = {}
    for code in tracking["securities"]:
        if not CODE.fullmatch(code):
            raise ValueError(f"Invalid public security code: {code}")
        market = code.split(".")[0]
        available, _ = display_bars(stocks.get(code, []), market, now)
        file = chart_cache / f"{code}.json"
        if file.is_file():
            node = json.loads(file.read_text(encoding="utf-8"))
            if node.get("code") == code:
                extra, _ = display_bars(node["bars"], market, now)
                if extra and (not available or extra[-1][0] > available[-1][0]):
                    stocks[code] = node["bars"]
                    sources[code] = "chart_history"
    fetched = 0
    if fetch_missing:
        if fetcher is None:
            from screener.history_fetch import hk_bars, us_bars
            fetcher = lambda code: (hk_bars if code.startswith("HK.") else us_bars)(code)
        latest = {}
        for row in tracking.get("evaluations", []):
            if row["horizon"] == 5:
                key = (row["strategy_id"], row["market"])
                if key not in latest or (row.get("scheduled_entry_date") or 0) >= (latest[key].get("scheduled_entry_date") or 0):
                    latest[key] = row
        priority = {h["code"] for row in latest.values() for h in row["baskets"]["selected"]["holdings"]}
        expected = {market: max((day for day, close in session_closes(market).items() if close <= now), default=0) for market in ("US", "HK")}
        needed = []
        for code in tracking["securities"]:
            market = code.split(".")[0]
            available, _ = display_bars(stocks.get(code, []), market, now)
            if not available or (code in priority and sources.get(code) == "chart_history" and available[-1][0] < expected[market]):
                needed.append(code)
        needed.sort(key=lambda c: (tracking["securities"][c].get("last_seen", ""), c), reverse=True)
        needed.sort(key=lambda c: c not in priority)
        for code in needed[:max_fetch]:
            try:
                raw = fetcher(code) or []
                if display_bars(raw, code.split(".")[0], now)[0]:
                    stocks[code] = raw
                    sources[code] = "chart_history"
                    chart_cache.mkdir(parents=True, exist_ok=True)
                    (chart_cache / f"{code}.json").write_text(json.dumps({"code": code, "bars": raw}, allow_nan=False), encoding="utf-8")
                    fetched += 1
            except Exception as exc:
                print(f"Chart fetch unavailable: {code} ({type(exc).__name__})")
            time.sleep(.1)
    out = data_dir / "candles"
    out.mkdir(parents=True, exist_ok=True)
    counts = {"securities": 0, "available": 0, "unavailable": 0}
    for code in sorted(tracking["securities"]):
        if not CODE.fullmatch(code):
            raise ValueError(f"Invalid public security code: {code}")
        bars, rejected = display_bars(stocks.get(code, []), code.split(".")[0], now)
        bars = bars[-limit:]
        payload = {
            "schema_version": 1, "code": code, "generated_at": now.isoformat(timespec="seconds"),
            "as_of": int(bars[-1][0]) if bars else None,
            "price_basis": "source_adjusted", "volume_unit": "source_units",
            "source": sources.get(code, "tracking_history"), "status": "available" if bars else "unavailable",
            "rejected_rows": rejected,
            "bars": bars,
        }
        target = out / f"{code}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        temporary.replace(target)
        counts["securities"] += 1
        counts[payload["status"]] += 1
    # Only clean files managed by this exporter. Arbitrary files remain for the
    # public verifier to reject, rather than being silently copied or removed.
    for file in out.glob("*.json"):
        if CODE.fullmatch(file.stem) and file.stem not in tracking["securities"]:
            file.unlink()
    return {**counts, "fetched": fetched}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "portfolio-board/public/data")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/screening_archive/prices")
    parser.add_argument("--fetch-missing", action="store_true", help="Free data; separate display cache only")
    parser.add_argument("--max-fetch", type=int, default=4)
    args = parser.parse_args()
    print("Display-only candles:", export(args.data_dir, args.cache_dir, fetch_missing=args.fetch_missing, max_fetch=args.max_fetch))
