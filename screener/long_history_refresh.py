"""Bounded refresh of fixed study members that rotate out of the main history pool."""
from datetime import datetime, timezone
import json

from screener.long_horizon import UNIVERSE, last_completed
from screener.risk import load_histories, HISTORY_DIR
from screener.tracking import ARCHIVE_DIR, write_json


def refresh(archive_dir=ARCHIVE_DIR, history_dir=HISTORY_DIR, *, now=None, budget=8, fetch=None):
    now = now or datetime.now(timezone.utc)
    directory = archive_dir / 'long_study/prices'
    state_path = directory / '_fetch_attempts.json'
    attempts = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    prices, _ = load_histories(history_dir)
    members = json.loads(UNIVERSE.read_text(encoding='utf-8'))
    due = []
    for market, stocks in members.items():
        latest = last_completed(market, now)
        for member in stocks:
            code = member['code']
            path = directory / (code + '.json')
            cached = json.loads(path.read_text(encoding='utf-8'))['bars'] if path.exists() else []
            available = prices.get(code, [])
            bars = max([cached, available], key=lambda b: b[-1][0] if b else 0)
            if not bars or len(bars) < 251 or bars[-1][0] < latest:
                due.append(code)
    if fetch is None:
        from screener.history_fetch import hk_bars, us_bars
        fetch = lambda code: (hk_bars if code.startswith('HK.') else us_bars)(code)
    tried, fetched = 0, 0
    for code in sorted(due, key=lambda c: (attempts.get(c, ''), c))[:budget]:
        attempts[code] = now.isoformat()
        write_json(state_path, attempts)
        tried += 1
        try:
            bars = fetch(code)
            path = directory / (code + '.json')
            cached = json.loads(path.read_text(encoding='utf-8'))['bars'] if path.exists() else []
            if bars and len(bars) >= 251 and (not cached or bars[-1][0] >= cached[-1][0]):
                write_json(path, {'bars': bars}); fetched += 1
        except (OSError, RuntimeError, ValueError):
            pass
    print('Fixed long-horizon pool refresh:', tried, 'attempted,', fetched, 'updated,', len(due), 'needed')


if __name__ == '__main__':
    refresh()
