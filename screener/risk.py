"""Risk observations from completed daily bars; absent data stays absent."""
from datetime import datetime, timezone
from functools import lru_cache
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import exchange_calendars as calendars

ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = ROOT / "portfolio-board/public/data/history"
ZONES = {"US": "America/New_York", "HK": "Asia/Hong_Kong"}


@lru_cache(maxsize=2)
def exchange_calendar(market):
    return calendars.get_calendar("XNYS" if market == "US" else "XHKG")


def session_open(day, market):
    day = datetime.strptime(str(int(day)), "%Y%m%d").date().isoformat()
    return exchange_calendar(market).session_open(day).to_pydatetime()


@lru_cache(maxsize=2)
def session_closes(market):
    schedule = exchange_calendar(market).schedule
    return {int(day.strftime("%Y%m%d")): close.to_pydatetime()
            for day, close in zip(schedule.index, schedule["close"])}


def completed_bars(bars, market, as_of=None):
    now = as_of or datetime.now(timezone.utc)
    try:
        arr = np.asarray(bars, dtype=float)
    except (ValueError, TypeError):
        return []
    if arr.ndim != 2 or arr.shape[1] < 6 or not np.isfinite(arr[:, :6]).all():
        return []
    if not (np.diff(arr[:, 0]) > 0).all():
        return []
    o, high, low, close, volume = arr[:, 1:6].T
    if ((np.minimum.reduce([o, high, low, close]) <= 0) | (volume < 0) |
        (high < np.maximum(o, close)) | (low > np.minimum(o, close))).any():
        return []
    closes = session_closes(market)
    return [row for row in bars if int(row[0]) in closes and closes[int(row[0])] <= now]


def risk_metrics(bars, market, as_of=None):
    bars = completed_bars(bars, market, as_of)
    if len(bars) < 21:
        return {"risk_status": "insufficient_history"}
    last_day = datetime.strptime(str(int(bars[-1][0])), "%Y%m%d").date()
    local_day = (as_of or datetime.now(timezone.utc)).astimezone(ZoneInfo(ZONES[market])).date()
    if (local_day - last_day).days > 7:
        return {"risk_status": "stale_history", "risk_as_of": str(int(bars[-1][0]))}
    arr = np.asarray(bars, dtype=float)
    closes = arr[:, 4]
    returns = np.diff(np.log(closes[-21:]))
    window = closes[-120:]
    return {
        "risk_status": "available", "risk_as_of": str(int(arr[-1, 0])),
        "volatility_20d_pct": round(float(returns.std(ddof=1) * np.sqrt(252) * 100), 2),
        "drawdown_120d_pct": round(float((window / np.maximum.accumulate(window) - 1).min() * 100), 2),
        "risk_window_sessions": len(window),
        "median_turnover_20d": round(float(np.median(arr[-20:, 4] * arr[-20:, 5])), 2),
    }


def load_histories(history_dir=HISTORY_DIR):
    stocks, indexes = {}, {}
    for market in ("us", "hk"):
        file = Path(history_dir) / f"{market}.json"
        if file.exists():
            for stock in json.loads(file.read_text(encoding="utf-8"))["stocks"]:
                stocks[stock["code"]] = stock["bars"]
    file = Path(history_dir) / "index.json"
    if file.exists():
        indexes = {key: node["bars"] for key, node in json.loads(file.read_text(encoding="utf-8"))["indexes"].items()}
    return stocks, indexes


def enrich_snapshot(df, history_dir=HISTORY_DIR, as_of=None):
    stocks, _ = load_histories(history_dir)
    metrics = [risk_metrics(stocks.get(code, []), code.split(".")[0], as_of) for code in df["code"]]
    import pandas as pd
    fields = pd.DataFrame(metrics, index=df.index)
    result = df.copy()
    for column in fields.columns:
        result[column] = fields[column]
    if "median_turnover_20d" not in result:
        result["median_turnover_20d"] = float("nan")
    return result
