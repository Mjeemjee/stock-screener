"""Reproduce one fixed normalization experiment using local OHLCV snapshots.

This is a retrospective market-pool diagnostic, not evidence for the historical
momentum_breakout candidate pipeline. No fitting or parameter search is done.
Run: python scripts/validate_factor_optimization.py --as-of 2026-10-14
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from screener.factor_rank import (  # noqa: E402
    FACTOR_WEIGHTS, HISTORY_N, calculate_factors, score_candidates,
)

METHODS = ("zscore", "winsorized_zscore")
HORIZON = 20
MIN_CROSS_SECTION = 50
COSTS_BPS = (0, 15, 30)
BOOTSTRAP_SEED = 20261014
BOOTSTRAP_REPEATS = 4000
BLOCK_LENGTH = 2

ITER_NOTE = {
    "op_type": "preprocess",
    "hypothesis": "Extreme factor observations can dominate ordinary z-scores; fixed MAD clipping may stabilize cross-sectional rankings.",
    "change": "Compare 3 * 1.4826 MAD clipping with the original z-score; keep weights, lookbacks, holding period and market pools fixed.",
    "expected": "No assumed gain: promote only if the paired return improvement CI is above 0, coverage >= 90%, and >= 12 holdout periods with prospective point-in-time evidence.",
    "decision": "REJECTED for default promotion; comparison retained as a reproducible research option.",
    "record_note": "Structured record of the hypothesis stated before execution; this dataset had already been inspected and is not a preregistered untouched holdout.",
}


def bootstrap_mean(values, *, seed=BOOTSTRAP_SEED, repeats=BOOTSTRAP_REPEATS,
                   block_length=BLOCK_LENGTH):
    """Circular moving-block bootstrap; preserve adjacent-period dependence."""
    x = np.asarray(values, dtype=float)
    observed = x[np.isfinite(x)]
    if len(observed) < 4:
        return {"mean": float(observed.mean()) if len(observed) else None, "ci95": None, "n": len(observed)}
    rng = np.random.default_rng(seed)
    length = min(block_length, len(x))
    starts = rng.integers(0, len(x), size=(repeats, int(np.ceil(len(x) / length))))
    indexes = (starts[..., None] + np.arange(length)) % len(x)
    samples = x[indexes.reshape(repeats, -1)[:, :len(x)]]
    counts = np.isfinite(samples).sum(axis=1)
    means = np.nansum(samples[counts > 0], axis=1) / counts[counts > 0]
    return {"mean": float(observed.mean()), "ci95": np.quantile(means, [0.025, 0.975]).tolist(),
            "n": len(observed), "scheduled_periods": len(x), "block_length_periods": length}


def correlation(a, b, rank=False):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if rank:
        a = pd.Series(a).rank(method="average").to_numpy()
        b = pd.Series(b).rank(method="average").to_numpy()
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def valid_open(row):
    return row is not None and np.isfinite(row[1]) and row[1] > 0 and row[5] > 0


def holding_result(bars_by_date, entry_date, exit_date):
    """Missing entry leaves its fixed allocation in cash; unknown exits stay unknown."""
    entry = bars_by_date.get(entry_date)
    if not valid_open(entry):
        return {"gross": 0.0, "filled": False, "missing_exit": False}
    end = bars_by_date.get(exit_date)
    if not valid_open(end):
        return {"gross": None, "filled": True, "missing_exit": True}
    return {"gross": float(end[1] / entry[1] - 1), "filled": True, "missing_exit": False}


def net_return(gross, filled, cost_bps):
    """Independent fully liquidated sleeve, fees applied to buy and sell notionals."""
    if not filled:
        return 0.0
    cost = cost_bps / 10000.0
    return (1 + gross) * (1 - cost) / (1 + cost) - 1


def load_market(history_dir, market, as_of):
    path = history_dir / f"{market}.json"
    payload = path.read_bytes()
    source = json.loads(payload)
    stocks, malformed = {}, []
    for stock in source["stocks"]:
        bars = np.asarray(stock["bars"], dtype=float)
        if bars.ndim != 2 or bars.shape[1] < 6:
            malformed.append(stock["code"])
            continue
        bars = bars[bars[:, 0] < as_of]
        if not len(bars) or not (np.diff(bars[:, 0]) > 0).all():
            malformed.append(stock["code"])
            continue
        stocks[stock["code"]] = {
            "bars": bars, "index": {int(d): i for i, d in enumerate(bars[:, 0])},
            "by_date": {int(row[0]): row for row in bars},
        }
    metadata = {"file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "generated_at": source.get("generated_at"), "stocks": len(stocks),
                "malformed_stocks": malformed, "stock_pool": "current snapshot, not point-in-time"}
    return stocks, metadata


def split_periods(periods):
    """Use calendar positions before inspecting outcome validity, with one embargo."""
    train_end = int(len(periods) * 0.60)
    holdout = list(range(train_end + 1, len(periods)))
    fold_numbers = {}
    for fold, members in enumerate(np.array_split(holdout, 3), 1):
        fold_numbers.update({int(i): fold for i in members})
    for i, row in enumerate(periods):
        row["split"] = "development" if i < train_end else "embargo" if i == train_end else "holdout"
        row["fold"] = fold_numbers.get(i)
    return periods


def evaluate_market(stocks, benchmark):
    calendar = sorted({date for stock in stocks.values() for date in stock["index"]})
    periods = []
    for signal_i in range(HISTORY_N - 1, len(calendar) - HORIZON - 1, HORIZON):
        signal_date = calendar[signal_i]
        entry_date, exit_date = calendar[signal_i + 1], calendar[signal_i + HORIZON + 1]
        raw = {}
        for code, stock in stocks.items():
            bar_i = stock["index"].get(signal_date)
            if bar_i is None or stock["bars"][bar_i, 5] <= 0:
                continue
            factors = calculate_factors(stock["bars"][:bar_i + 1])
            if factors:
                raw[code] = factors
        row = {"signal_date": signal_date, "entry_date": entry_date, "exit_date": exit_date,
               "cross_section": len(raw), "valid": False, "methods": {}}
        if len(raw) < MIN_CROSS_SECTION:
            row["excluded_reason"] = "insufficient_cross_section"
            periods.append(row)
            continue
        # Candidate eligibility and rankings are fixed before reading future prices.
        scores = {method: score_candidates(raw, method=method) for method in METHODS}
        holdings = {code: holding_result(stocks[code]["by_date"], entry_date, exit_date) for code in raw}
        missing_exits = sorted(code for code, ret in holdings.items() if ret["missing_exit"])
        row.update({"unfilled_entries": sorted(c for c, r in holdings.items() if not r["filled"]),
                    "missing_exits": missing_exits,
                    "valid": not missing_exits})
        if missing_exits:
            row["excluded_reason"] = "missing_exit_in_fixed_cross_section"
        benchmark_return = holding_result(benchmark, entry_date, exit_date)
        row["benchmark_gross"] = benchmark_return["gross"] if benchmark_return["filled"] else None
        row["equal_weight_net"] = {}
        if row["valid"]:
            for cost in COSTS_BPS:
                row["equal_weight_net"][str(cost)] = float(np.mean([
                    net_return(r["gross"], r["filled"], cost) for r in holdings.values()]))
        for method in METHODS:
            ordered = sorted(raw, key=lambda c: (scores[method][c], c))
            groups = [list(group) for group in np.array_split(ordered, 5)]
            detail = {"bucket_sizes": [len(group) for group in groups],
                      "top_codes": groups[-1], "bottom_codes": groups[0],
                      "rank_ic": None, "pearson_ic": None, "quantile_net": {}}
            complete = [c for c in raw if holdings[c]["filled"] and not holdings[c]["missing_exit"]]
            detail["ic_pairs"] = len(complete)
            if row["valid"] and len(complete) >= MIN_CROSS_SECTION:
                forward = [holdings[c]["gross"] for c in complete]
                prediction = [scores[method][c] for c in complete]
                detail["rank_ic"] = correlation(prediction, forward, rank=True)
                detail["pearson_ic"] = correlation(prediction, forward)
            if row["valid"]:
                for cost in COSTS_BPS:
                    detail["quantile_net"][str(cost)] = [float(np.mean([
                        net_return(holdings[c]["gross"], holdings[c]["filled"], cost) for c in group]))
                        for group in groups]
            row["methods"][method] = detail
        top_sets = [set(row["methods"][method]["top_codes"]) for method in METHODS]
        row["top_basket_jaccard"] = len(top_sets[0] & top_sets[1]) / len(top_sets[0] | top_sets[1])
        periods.append(row)
    return split_periods(periods)


def performance(returns):
    a = np.asarray(returns, dtype=float)
    if not len(a):
        return None
    nav = np.r_[1.0, np.cumprod(1 + a)]
    sd = a.std(ddof=1) if len(a) > 1 else 0
    return {"periods": len(a), "total_return": float(nav[-1] - 1),
            "mean_period_return": float(a.mean()),
            "cagr_observed_periods": float(nav[-1] ** (252 / (HORIZON * len(a))) - 1),
            "sharpe_rf0_period_returns": float(a.mean() / sd * np.sqrt(252 / HORIZON)) if sd else None,
            "max_drawdown_at_period_end": float(np.min(nav / np.maximum.accumulate(nav) - 1))}


def summarize(periods):
    valid = [row for row in periods if row["valid"]]
    out = {"scheduled_periods": len(periods), "evaluated_periods": len(valid),
           "excluded_periods": len(periods) - len(valid), "methods": {},
           "first_signal": periods[0]["signal_date"] if periods else None,
           "last_exit": periods[-1]["exit_date"] if periods else None}
    for method in METHODS:
        detail = {"rank_ic": bootstrap_mean([row["methods"][method]["rank_ic"] if row["valid"] else np.nan
                                             for row in periods]),
                  "pearson_ic": bootstrap_mean([row["methods"][method]["pearson_ic"] if row["valid"] else np.nan
                                                for row in periods]),
                  "cost_sensitivity": {}}
        for cost in COSTS_BPS:
            q_returns = np.array([row["methods"][method]["quantile_net"][str(cost)] for row in valid])
            if not len(q_returns):
                detail["cost_sensitivity"][str(cost)] = None
                continue
            detail["cost_sensitivity"][str(cost)] = {
                "top": performance(q_returns[:, -1]), "bottom": performance(q_returns[:, 0]),
                "q5_minus_q1_mean": bootstrap_mean([
                    row["methods"][method]["quantile_net"][str(cost)][-1]
                    - row["methods"][method]["quantile_net"][str(cost)][0] if row["valid"] else np.nan
                    for row in periods]),
                "quantile_mean_returns": q_returns.mean(axis=0).tolist(),
                "equal_weight_pool": performance([row["equal_weight_net"][str(cost)] for row in valid])}
        out["methods"][method] = detail
    deltas = [row["methods"][METHODS[1]]["quantile_net"]["15"][-1]
              - row["methods"][METHODS[0]]["quantile_net"]["15"][-1] if row["valid"] else np.nan
              for row in periods]
    out["paired_top_delta_15bps"] = bootstrap_mean(deltas)
    out["benchmark"] = performance([row["benchmark_gross"] for row in valid
                                    if row["benchmark_gross"] is not None])
    out["mean_top_basket_jaccard"] = float(np.mean([row["top_basket_jaccard"] for row in valid])) if valid else None
    return out


def assess(periods, holdout):
    """Predeclared evidence gates are deliberately conservative for a small sample."""
    ci = holdout["paired_top_delta_15bps"]["ci95"]
    candidate = holdout["methods"][METHODS[1]]
    ic_ci = candidate["rank_ic"]["ci95"]
    spread = candidate["cost_sensitivity"]["30"]
    spread_ci = spread["q5_minus_q1_mean"]["ci95"] if spread else None
    gates = {"at_least_12_evaluated_holdout_periods": holdout["evaluated_periods"] >= 12,
             "at_least_90pct_holdout_coverage": bool(holdout["scheduled_periods"] and
                 holdout["evaluated_periods"] / holdout["scheduled_periods"] >= 0.9),
             "paired_top_delta_ci_above_zero": bool(ci and ci[0] > 0),
             "candidate_rank_ic_ci_above_zero": bool(ic_ci and ic_ci[0] > 0),
             "candidate_spread_ci_above_zero_at_30bps": bool(spread_ci and spread_ci[0] > 0),
             "point_in_time_universe_available": False,
             "historical_prescreen_membership_available": False,
             "untouched_prospective_holdout": False}
    return {"verdict": "RESEARCH_ONLY", "promote_default": False, "gates": gates,
            "reason": "Retrospective snapshot pool cannot establish live screener improvement; retain baseline default."}


def write_chart(market, periods, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    valid = [row for row in periods if row["split"] == "holdout" and row["valid"]]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    if not valid:
        fig.text(0.5, 0.5, "Insufficient complete holdout periods", ha="center")
    else:
        x = np.arange(len(valid) + 1)
        for method, label in zip(METHODS, ("Legacy", "MAD clipped")):
            q = np.array([row["methods"][method]["quantile_net"]["15"] for row in valid])
            nav = np.r_[1, np.cumprod(1 + q[:, -1])]
            axes[0, 0].plot(x, nav, label=label)
            ic = [row["methods"][method]["rank_ic"] or 0 for row in valid]
            axes[0, 1].plot(np.arange(1, len(valid) + 1), np.cumsum(ic), label=label)
            axes[1, 0].plot(np.arange(1, 6), q.mean(axis=0) * 100, marker="o", label=label)
            axes[1, 1].plot(x, (nav / np.maximum.accumulate(nav) - 1) * 100, label=label)
        equal = np.r_[1, np.cumprod(1 + np.array([row["equal_weight_net"]["15"] for row in valid]))]
        axes[0, 0].plot(x, equal, label="Equal-weight pool", linestyle="--")
        if all(row["benchmark_gross"] is not None for row in valid):
            bench = np.r_[1, np.cumprod(1 + np.array([row["benchmark_gross"] for row in valid]))]
            axes[0, 0].plot(x, bench, label="SPX" if market == "us" else "HSI", linestyle=":")
        titles = ("Holdout Q5 NAV (15 bp each side)", "Cumulative nonoverlapping rank IC",
                  "Mean 20-session return by quintile (%)", "Period-end drawdown (%)")
        for axis, title in zip(axes.flat, titles):
            axis.set_title(title, fontsize=10)
            axis.grid(alpha=0.25)
            axis.legend(fontsize=8)
        for axis in (axes[0, 0], axes[0, 1], axes[1, 1]):
            axis.set_xlabel("Evaluated holdout period (excluded gaps omitted)")
        axes[1, 0].set_xlabel("Q1 low score to Q5 high score")
    fig.suptitle(f"{market.upper()} retrospective diagnostic | snapshot universe; no alpha claim", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def fmt(value, percent=False):
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%" if percent else f"{value:.4f}"


def write_report(result, path):
    lines = ["# Factor Normalization Validation", "",
             "**Decision: retain legacy normalization; MAD clipping remains opt-in research.**", "",
             "This fixed-parameter experiment does not prove improved live screener returns. "
             "The time split is retrospective: this historical snapshot was already used in earlier research.", "",
             "## Reproduce", "", "```powershell",
             f"python scripts/validate_factor_optimization.py --as-of {result['as_of']}",
             "python -m unittest discover -s scripts -p test_validate_factor_optimization.py", "```", "",
             "## Protocol", "",
             "- Separate US and HK calendars and normalization; fixed weights 0.3/0.3/0.4.",
             "- Candidate: clip each factor at median +/- 3 * 1.4826 * MAD, z-score each factor, "
             "weight, then re-z-score the composite. Legacy uses ordinary per-factor z-scores.",
             "- Signal uses only bars available at that close; buy next session OPEN, exit 20 sessions "
             "later at OPEN. Bars on or after the as-of date are excluded, including unfinished daily bars.",
             "- Five equal-weight buckets; at least 50 names. This matches the existing quintile comparison "
             "rather than changing the investment universe and top fraction in the same experiment.",
             "- Nonoverlapping, independently liquidated sleeves. Each filled holding pays both entry and "
             "exit costs at 0/15/30 bp per side, including re-entered names. This is conservative relative "
             "to a continuously held portfolio and avoids name-count turnover accounting.",
             "- First 60% of scheduled periods are development, one full period is embargoed, the remainder "
             "is chronological holdout in three blocks. No fitting, optimization, or holdout parameter search.",
             "- Candidate selection precedes reading future prices. Missing/zero-volume entry leaves that "
             "weight in cash. An unknown exit excludes the entire paired period; exclusions and codes are "
             "reported, never silently reweighted. Exclusion bias remains and limits inference.",
             "- IC and paired-return confidence intervals use 4,000 circular block-bootstrap draws, "
             "two consecutive 20-session periods per block, fixed seed 20261014. Missing periods remain "
             "gaps in the sampling grid. Few periods imply low power.", "",
             "## Holdout Results", "",
             "| Market | Periods kept/scheduled | Legacy Q5 return | MAD Q5 return | Legacy Rank IC | MAD Rank IC | MAD minus legacy / period, CI95 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for market, data in result["markets"].items():
        hold = data["holdout"]
        methods = hold["methods"]
        def top(method):
            sensitivity = methods[method]["cost_sensitivity"]["15"]
            return sensitivity["top"]["total_return"] if sensitivity else None
        delta = hold["paired_top_delta_15bps"]
        ci = delta["ci95"]
        ci_text = f"[{fmt(ci[0], True)}, {fmt(ci[1], True)}]" if ci else "n/a"
        lines.append(f"| {market.upper()} | {hold['evaluated_periods']}/{hold['scheduled_periods']} | "
                     f"{fmt(top(METHODS[0]), True)} | {fmt(top(METHODS[1]), True)} | "
                     f"{fmt(methods[METHODS[0]]['rank_ic']['mean'])} | {fmt(methods[METHODS[1]]['rank_ic']['mean'])} | "
                     f"{fmt(delta['mean'], True)} {ci_text} |")
    lines += ["", "Returns compound only the evaluated holdout periods at 15 bp per side. "
              "If periods are excluded, these are conditional diagnostic returns, not a continuous executable NAV.", ""]
    for market, data in result["markets"].items():
        lines += [f"## {market.upper()} Detail", "", f"Snapshot names: {data['source']['stocks']}. "
                  f"Full schedule: {data['full']['first_signal']} to {data['full']['last_exit']}. "
                  f"Holdout: {data['holdout']['first_signal']} to {data['holdout']['last_exit']}.", "",
                  "| Cost per side | Legacy Q5 return | MAD Q5 return | MAD Q5-Q1 mean / period |",
                  "|---|---:|---:|---:|"]
        for cost in COSTS_BPS:
            old = data["holdout"]["methods"][METHODS[0]]["cost_sensitivity"][str(cost)]
            new = data["holdout"]["methods"][METHODS[1]]["cost_sensitivity"][str(cost)]
            lines.append(f"| {cost} bp | {fmt(old['top']['total_return'], True) if old else 'n/a'} | "
                         f"{fmt(new['top']['total_return'], True) if new else 'n/a'} | "
                         f"{fmt(new['q5_minus_q1_mean']['mean'], True) if new else 'n/a'} |")
        lines += ["", "Chronological holdout blocks (no refitting):", "",
                  "| Block | Kept/scheduled | Legacy IC | MAD IC | MAD minus legacy mean / period |",
                  "|---|---:|---:|---:|---:|"]
        for fold, summary in data["folds"].items():
            lines.append(f"| {fold} | {summary['evaluated_periods']}/{summary['scheduled_periods']} | "
                         f"{fmt(summary['methods'][METHODS[0]]['rank_ic']['mean'])} | "
                         f"{fmt(summary['methods'][METHODS[1]]['rank_ic']['mean'])} | "
                         f"{fmt(summary['paired_top_delta_15bps']['mean'], True)} |")
        lines += ["", "Evidence gates:", ""]
        lines += [f"- {gate}: {'PASS' if passed else 'NOT MET'}" for gate, passed in data["assessment"]["gates"].items()]
        excluded = [p for p in data["periods"] if not p["valid"]]
        lines += ["", f"Excluded periods: {len(excluded)}. " + "; ".join(
            f"{p['signal_date']} ({p['excluded_reason']}; missing exits: {', '.join(p.get('missing_exits', [])) or 'none'})" for p in excluded),
                  "", f"![{market.upper()} diagnostics](factor_optimization_{market}.png)", ""]
    lines += ["## Audit of Earlier Evidence", "",
              "- Earlier IC pooled markets with different calendars, used close-to-close labels despite "
              "signals needing that close, and treated overlapping 20-session returns as independent in t tests.",
              "- Earlier quantile backtest exited at the next signal-day close but entered next-day open, "
              "omitting overnight exposure and charging only name-count turnover despite equal-weight rebalancing.",
              "- Its benchmark divided by the first completed period NAV, thereby removing the first benchmark "
              "return; strategy and benchmark also used different open/close endpoints.",
              "- Its drawdown did not include initial NAV = 1, so a first-period loss was omitted from drawdown.",
              "- Missing future prices were dropped and remaining names reweighted, making apparent returns "
              "depend on future data availability. Earlier significance and absolute returns need revalidation.", "",
              "## Limits and Next Evidence", "",
              "The local universe is selected using the 2026-10-14 snapshot, with missing delisted names and "
              "survivorship/liquidity selection bias. Price adjustment, dividends and corporate-action treatment "
              "are not independently reconciled. Volume is only a coarse trading-availability proxy; auction "
              "fills, impact, capacity and halt status are unavailable. US/HK limit mechanics are not inferred "
              "from A-share rules. Period-end drawdowns understate intraperiod drawdowns.", "",
              "Historical daily momentum_breakout memberships and contemporaneous fundamental snapshots are "
              "absent. This experiment measures normalization on the available market pools, not end-to-end "
              "screening effectiveness. The three chronological blocks are stability diagnostics, not a fitted "
              "walk-forward model. Ongoing paper evaluation should freeze the strategy version, save every "
              "daily candidate set and score before next-session prices arrive, and evaluate matched baselines "
              "after the 20-session holding period. Promote a new default only with adequate prospective "
              "coverage, costs, and uncertainty estimates.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=datetime.now(timezone(timedelta(hours=8))).date().isoformat())
    parser.add_argument("--history-dir", type=Path, default=ROOT / "portfolio-board/public/data/history")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    cutoff = int(datetime.strptime(args.as_of, "%Y-%m-%d").strftime("%Y%m%d"))
    index_path = args.history_dir / "index.json"
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)["indexes"]
    result = {"as_of": args.as_of, "protocol_version": 1, "iteration_note": ITER_NOTE, "weights": FACTOR_WEIGHTS,
              "horizon_sessions": HORIZON, "minimum_cross_section": MIN_CROSS_SECTION,
              "costs_bps_per_side": COSTS_BPS, "bootstrap_seed": BOOTSTRAP_SEED,
              "bootstrap_repeats": BOOTSTRAP_REPEATS, "bootstrap_block_periods": BLOCK_LENGTH,
              "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
              "factor_code_sha256": hashlib.sha256((ROOT / "screener/factor_rank.py").read_bytes()).hexdigest(),
              "validation_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "markets": {}}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for market in ("us", "hk"):
        stocks, metadata = load_market(args.history_dir, market, cutoff)
        benchmark = {int(row[0]): row for row in index["SPX" if market == "us" else "HSI"]["bars"]
                     if int(row[0]) < cutoff}
        periods = evaluate_market(stocks, benchmark)
        if not periods:
            raise ValueError(f"Insufficient history for {market}")
        data = {"source": metadata, "periods": periods, "full": summarize(periods),
                "development": summarize([p for p in periods if p["split"] == "development"]),
                "holdout": summarize([p for p in periods if p["split"] == "holdout"]),
                "folds": {str(fold): summarize([p for p in periods if p["fold"] == fold]) for fold in (1, 2, 3)}}
        data["assessment"] = assess(periods, data["holdout"])
        result["markets"][market] = data
        write_chart(market, periods, args.out_dir / f"factor_optimization_{market}.png")
        print(f"{market.upper()}: {data['holdout']['evaluated_periods']}/{data['holdout']['scheduled_periods']} "
              f"holdout periods; paired delta {data['holdout']['paired_top_delta_15bps']}; RESEARCH_ONLY")
    (args.out_dir / "factor_optimization.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    write_report(result, args.out_dir / "factor_optimization_report.md")
    print(f"Wrote diagnostics to {args.out_dir}")


if __name__ == "__main__":
    main()
