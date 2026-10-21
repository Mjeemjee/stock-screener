"""Fixed long-horizon paper study, independent of existing strategy experiments."""
import argparse
from datetime import datetime, timezone
from functools import lru_cache
import json
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from screener.factor_research import digest, sealed, read_sealed
from screener.risk import load_histories
from screener.tracking import ARCHIVE_DIR, ROOT, freeze_snapshot, read_archives, write_json, evaluate_holding

POLICY = {"version": "liq-momentum-forward-v2", "horizon": 21, "lookback": 251,
          "top_fraction": .2, "min_cross_section": 30, "min_coverage": .8,
          "cost_bps": 15, "stress_cost_bps": 30, "checkpoints": [6, 12, 24],
          "family_alpha": .05, "comparison_count": 6, "worst_period_floor_pct": -15}
VARIANTS = {"combined": "流动性与长期动量", "momentum": "仅长期动量", "liquidity": "仅流动性"}
UNIVERSE = Path(__file__).with_name("long_horizon_universe.json")
HISTORY = Path(__file__).with_name("long_horizon_history.json")


@lru_cache(maxsize=2)
def calendar(market):
    if market not in ("US", "HK"):
        raise ValueError("Unknown market")
    return xcals.get_calendar("XNYS" if market == "US" else "XHKG", start="1990-01-01", end="2035-12-31")


def day(value):
    return int(pd.Timestamp(value).strftime("%Y%m%d"))


def sessions(market, start, end):
    return [day(d) for d in calendar(market).sessions_in_range(str(start), str(end))]


def last_completed(market, now):
    schedule = calendar(market).schedule
    return day(schedule.index[schedule["close"] <= now][-1])


def next_entry(market, created):
    cal = calendar(market)
    local = created.astimezone(cal.tz).date().isoformat()
    session = cal.date_to_session(local, direction="next")
    if cal.session_open(session).to_pydatetime() <= created:
        session = cal.next_session(session)
    return day(session)


def score_panel(close, volume):
    """Dense exchange-session grid: no per-stock sliding across missing days."""
    amount = (close * volume).where((close > 0) & (volume >= 0))
    liquidity = -np.log(amount.rolling(20, min_periods=15).mean().where(lambda x: x > 0))
    momentum = close.shift(20) / close.shift(250) - 1
    valid = liquidity.notna() & momentum.notna() & (volume > 0) & (close > 0)
    liquidity, momentum = liquidity.where(valid), momentum.where(valid)
    lr, mr = liquidity.rank(axis=1, pct=True), momentum.rank(axis=1, pct=True)
    return {"combined": (lr + mr) / 2, "momentum": mr, "liquidity": lr}


def signal(prices, members, market, session):
    cal = calendar(market)
    days = [day(d) for d in cal.sessions_window(pd.Timestamp(str(session)), -POLICY["lookback"])]
    close, volume = {}, {}
    for member in members:
        code = member["code"]
        bars = {int(b[0]): b for b in prices.get(code, []) if len(b) >= 6 and int(b[0]) <= session}
        close[code] = [bars[d][4] if d in bars else np.nan for d in days]
        volume[code] = [bars[d][5] if d in bars else np.nan for d in days]
    c, v = pd.DataFrame(close, index=days), pd.DataFrame(volume, index=days)
    c = c.where(np.isfinite(c) & (c > 0)); v = v.where(np.isfinite(v) & (v >= 0))
    scores = {k: frame.iloc[-1].dropna() for k, frame in score_panel(c, v).items()}
    valid = len(scores["combined"])
    ready = valid >= POLICY["min_cross_section"] and valid / len(members) >= POLICY["min_coverage"]
    k = max(1, int(valid * POLICY["top_fraction"]))
    selected = {key: sorted(values.index, key=lambda code: (-values[code], code))[:k] for key, values in scores.items()}
    inputs = {code: [bars for bars in prices.get(code, []) if len(bars) >= 6 and int(bars[0]) in days]
              for code in sorted(c.columns)}
    return selected, {"session": session, "valid": valid, "total": len(members),
                      "status": "ready" if ready else "insufficient_data"}, inputs


def basket(codes, prices, entry, exit_day, now, market, cost=15):
    cal = calendar(market)
    entered = cal.session_open(str(entry)).to_pydatetime() <= now
    due = cal.session_open(str(exit_day)).to_pydatetime() <= now
    holdings = [{"code": c, **(evaluate_holding(prices.get(c, []), entry, exit_day if due else None, cost_bps=cost)
                              if entered else {"status": "pending", "return_pct": None})} for c in codes]
    for holding in holdings:
        if holding['status'] != 'matured':
            continue
        bars = prices.get(holding['code'], [])
        for previous, current in zip(bars, bars[1:]):
            if entry <= int(current[0]) <= exit_day and previous[4] > 0 and abs(current[4] / previous[4] - 1) > .6:
                holding.update(status='corporate_action_unknown', return_pct=None)
                break
    complete = due and bool(codes) and all(h["return_pct"] is not None for h in holdings)
    return {"count": len(codes), "complete": complete, "holdings": holdings,
            "return_pct": float(np.mean([h["return_pct"] for h in holdings])) if complete else None}


def metrics(rows):
    due_all = [r for r in rows if r["due"]]
    due = due_all[:24]
    paired = [r for r in due if all(r["baskets"][k]["complete"] for k in VARIANTS) and r["benchmark_pct"] is not None]
    values = [r["baskets"]["combined"]["return_pct"] for r in paired]
    deltas = [r["baskets"]["combined"]["return_pct"] - r["baskets"]["momentum"]["return_pct"] for r in paired]
    lower = None
    lower_checks = {}
    if len(deltas) >= 6:
        rng = np.random.default_rng(20261021)
        starts = rng.integers(len(deltas), size=(5000, int(np.ceil(len(deltas) / 3))))
        idx = ((starts[:, :, None] + np.arange(3)) % len(deltas)).reshape(5000, -1)[:, :len(deltas)]
        lower = float(np.quantile(np.asarray(deltas)[idx].mean(axis=1), .025))
        for key, comparisons in {
            'momentum': deltas,
            'liquidity': [v - r['baskets']['liquidity']['return_pct'] for v, r in zip(values, paired)],
            'benchmark': [v - r['benchmark_pct'] for v, r in zip(values, paired)],
        }.items():
            lower_checks[key] = float(np.quantile(np.asarray(comparisons)[idx].mean(axis=1),
                                                  POLICY['family_alpha'] / POLICY['comparison_count']))
    mean = lambda x: float(np.mean(x)) if x else None
    stress = mean([r['stress']['return_pct'] - r['benchmark_pct'] for r in paired if r['stress']['complete']])
    gate = (bool(lower_checks) and all(v > 0 for v in lower_checks.values()) and len(paired) / len(due) >= .9
            and stress is not None and stress > 0 and min(values) >= POLICY['worst_period_floor_pct'])
    return {"due": len(due), "total_due": len(due_all), "paired": len(paired), "coverage": len(paired) / len(due) if due else 0,
            "mean_net_pct": mean(values), "mean_delta_pp": mean(deltas), "lower_delta_pp": lower,
            "mean_excess_pp": mean([v - r["benchmark_pct"] for v, r in zip(values, paired)]),
            "stress_excess_pp": stress,
            "worst_period_pct": min(values) if values else None,
            "adjusted_lower_pp": lower_checks,
            "stage": ("可人工复核" if gate else "未达门槛") if len(due) == 24 else
                     "等待样本" if len(paired) < 6 else "初步观察" if len(paired) < 12 else "持续验证"}


def evaluate(records, prices, indexes, directory, now):
    output = []
    for record in records:
        payload = record["payload"]
        market, selected = payload["market"], payload["selected"]
        entry = next_entry(market, datetime.fromisoformat(record["frozen_at"]))
        exit_day = day(calendar(market).session_offset(str(entry), POLICY["horizon"]))
        path = Path(directory) / "settled" / (record["id"] + ".json")
        if path.exists():
            output.append(read_sealed(path)); continue
        b = {k: basket(codes, prices, entry, exit_day, now, market, POLICY["cost_bps"]) for k, codes in selected.items()}
        due = calendar(market).session_open(str(exit_day)).to_pydatetime() <= now
        ib = {int(x[0]): x for x in indexes.get("SPX" if market == "US" else "HSI", [])}
        benchmark = ((ib[exit_day][1] / ib[entry][1] - 1) * 100 if due and entry in ib and exit_day in ib and ib[entry][1] > 0 else None)
        row = {"id": record["id"], "market": market, "frozen_at": record["frozen_at"], "entry_date": entry,
               "exit_date": exit_day, "due": due, "baskets": b, "benchmark_pct": benchmark,
               "stress": basket(selected["combined"], prices, entry, exit_day, now, market, POLICY["stress_cost_bps"])}
        if due and all(v["complete"] for v in b.values()) and benchmark is not None:
            sealed(path, row)
        output.append(row)
    return output


def run(archive_dir=ARCHIVE_DIR, history_dir=None, output=None, *, now=None, universe=None):
    now = now or datetime.now(timezone.utc)
    history_dir = Path(history_dir or ROOT / "portfolio-board/public/data/history")
    output = Path(output or ROOT / "portfolio-board/public/data/long_research.json")
    directory = Path(archive_dir) / "long_study"
    members = universe or json.loads(UNIVERSE.read_text(encoding="utf-8"))
    definition = {"policy": POLICY, "members": members,
                  "engine": digest(Path(__file__).read_text(encoding="utf-8"))}
    definition_hash = sealed(directory / "definition.json", definition)
    prices, indexes = load_histories(history_dir)
    for market, stocks in members.items():
        for member in stocks:
            code = member["code"]
            path = directory / "prices" / (code + ".json")
            cached = json.loads(path.read_text(encoding="utf-8"))["bars"] if path.exists() else []
            incoming = prices.get(code, [])
            if incoming and (not cached or incoming[-1][0] >= cached[-1][0]):
                write_json(path, {"bars": incoming})
            else:
                prices[code] = cached
    records = read_archives(directory)
    quality = []
    for market, stocks in members.items():
        completed = last_completed(market, now)
        selected, q, inputs = signal(prices, stocks, market, completed)
        quality.append({"market": market, **q})
        own = [r for r in records if r["payload"]["market"] == market]
        if own:
            last = max(next_entry(market, datetime.fromisoformat(r["frozen_at"])) for r in own)
            if completed < day(calendar(market).session_offset(str(last), POLICY["horizon"] - 1)):
                continue
        if q["status"] != "ready":
            continue
        payload = {"generated_at": now.isoformat(), "strategies": [], "market": market, "selected": selected,
                   "input_session": completed, "inputs": inputs, "definition_hash": definition_hash}
        freeze_snapshot(payload, directory, frozen_at=now)
    records = read_archives(directory)
    if any(r["payload"]["definition_hash"] != definition_hash for r in records):
        raise ValueError("Long-horizon study definition changed")
    rows = evaluate(records, prices, indexes, directory, now)
    markets = [{"market": m, "quality": next(q for q in quality if q["market"] == m),
                "metrics": metrics([r for r in rows if r["market"] == m]),
                "latest": next((r for r in reversed(rows) if r["market"] == m), None)} for m in members]
    report = {"schema_version": 1, "generated_at": now.isoformat(), "definition_hash": definition_hash,
              "policy": POLICY, "markets": markets, "cohorts": rows,
              "historical": json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else None}
    write_json(output, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=ARCHIVE_DIR)
    parser.add_argument("--history-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.archive_dir, args.history_dir, args.output)
    print("Long-horizon frozen cohorts:", len(result["cohorts"]))
