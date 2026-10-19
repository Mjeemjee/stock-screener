"""Time-separated diagnostics; retrospective folds never become live evidence."""
from datetime import datetime, timezone

import numpy as np

from screener.research_signals import (FEATURES, correlation, expression_values, feature,
                                     raw_features, select, standardize)
from screener.risk import completed_bars, exchange_calendar
from screener.tracking import evaluate_holding


def last_completed(market, now):
    schedule = exchange_calendar(market).schedule
    days = schedule.index[schedule["close"] <= now]
    if len(days) == 0:
        raise ValueError("No completed market session")
    return int(days[-1].strftime("%Y%m%d"))


def panel_at(members, prices, market, day, lookback=61):
    calendar = exchange_calendar(market)
    session = calendar.date_to_session(str(day), direction="none")
    expected = [int(d.strftime("%Y%m%d")) for d in calendar.sessions_window(session, -lookback)]
    rows, missing, inputs = {}, {}, {}
    for member in members:
        code = member["code"]
        bars = [b for b in prices.get(code, []) if int(b[0]) <= day][-lookback:]
        try:
            if [int(b[0]) for b in bars] != expected:
                raise ValueError("缺少连续61个交易日或行情未更新")
            rows[code] = raw_features(bars)
            inputs[code] = bars
        except (ValueError, TypeError, IndexError):
            missing[code] = "缺少连续有效行情或成交量为零"
    return rows, missing, inputs


def usable_prices(prices, market, now):
    return {code: completed_bars(bars, market, now) for code, bars in prices.items()
            if code.startswith(market + ".")}


def basket(codes, prices, entry, exit_day, cost=15):
    holdings = [{"code": code, **evaluate_holding(prices.get(code, []), entry, exit_day, cost_bps=cost)}
                for code in codes]
    complete = all(h["return_pct"] is not None for h in holdings)
    return {"count": len(codes), "holdings": holdings, "complete": complete,
            "return_pct": float(np.mean([h["return_pct"] for h in holdings])) if holdings and complete
                          else 0.0 if complete else None}


def diagnostics(spec, panel, pool, controls):
    normalized = standardize(panel)
    scores = expression_values(spec["expression"], normalized)
    returns = {h["code"]: h["return_pct"] for h in pool["holdings"] if h["return_pct"] is not None}
    correlations = [correlation(scores, expression_values(expr, normalized)) for expr in controls]
    values = [abs(v) for v in correlations if v is not None]
    ordered = sorted(set(scores) & set(returns), key=lambda code: (scores[code], code))
    bucket = max(1, len(ordered) // 5)
    spread = average([returns[c] for c in ordered[-bucket:]]) - average([returns[c] for c in ordered[:bucket]]) if len(ordered) >= 20 else None
    return {"rank_ic": correlation(scores, returns), "pearson_ic": correlation(scores, returns, rank=False),
            "q5_q1_pp": spread,
            "novelty_max": max(values, default=None),
            "control_correlations": correlations}


def average(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def novelty(rows):
    arrays = [r.get("control_correlations", []) for r in rows if r.get("due")]
    n = max((len(a) for a in arrays), default=0)
    means = [average([abs(a[i]) for a in arrays if i < len(a) and a[i] is not None]) for i in range(n)]
    return max((v for v in means if v is not None), default=None)


def historical_diagnostic(spec, members, prices, market, now, rules):
    calendar = exchange_calendar(market)
    day = last_completed(market, now)
    end = calendar.date_to_session(str(day))
    needed = rules["history_train"] + rules["embargo"] + rules["history_test"] * rules["history_folds"]
    sessions = calendar.sessions_window(end, -(needed + rules["horizon"] + 1))
    signal_days = sessions[:needed]
    controls = [feature(k) for k, value in FEATURES.items() if value["family"] == "control"]
    rows = []
    for session in signal_days:
        signal_day = int(session.strftime("%Y%m%d"))
        panel, _, _ = panel_at(members, prices, market, signal_day)
        entry = int(calendar.next_session(session).strftime("%Y%m%d"))
        exit_day = int(calendar.session_offset(session, 1 + rules["horizon"]).strftime("%Y%m%d"))
        row = {"day": signal_day, "rank_ic": None, "pearson_ic": None, "q5_q1_pp": None, "delta": None, "coverage": 0.0}
        if len(panel) >= rules["min_cross_section"] and len(panel) / len(members) >= rules["min_data_coverage"]:
            pool = basket(sorted(panel), prices, entry, exit_day, rules["cost_bps"])
            chosen = basket([h["code"] for h in select(spec, panel, rules["top_n"])], prices, entry, exit_day, rules["cost_bps"])
            row["coverage"] = len(panel) / len(members)
            if pool["complete"] and chosen["complete"]:
                row.update(diagnostics(spec, panel, pool, controls))
                row["delta"] = chosen["return_pct"] - pool["return_pct"]
        rows.append(row)
    folds = []
    for i in range(rules["history_folds"]):
        start = i * rules["history_test"]
        anchor = start + rules["history_train"]
        train = rows[start:anchor - rules["horizon"]]
        test = rows[anchor + rules["embargo"]:anchor + rules["embargo"] + rules["history_test"]]
        if not train or not test:
            continue
        ic = [r["rank_ic"] for r in test if r["rank_ic"] is not None]
        train_ic = average([r["rank_ic"] for r in train])
        test_ic = average(ic)
        lower, upper = None, None
        if len(ic) >= 20:
            starts = np.random.default_rng(314159).integers(len(ic), size=(2000, 4))
            positions = (starts[:, :, None] + np.arange(5)) % len(ic)
            means = np.array(ic)[positions.reshape(2000, -1)].mean(axis=1)
            lower, upper = (float(v) for v in np.quantile(means, [0.025, 0.975]))
        folds.append({"train_start": train[0]["day"], "train_end": train[-1]["day"],
                      "test_start": test[0]["day"], "test_end": test[-1]["day"],
                      "purged": rules["horizon"], "embargo": rules["embargo"],
                      "test_periods": len(test), "complete": sum(r["delta"] is not None for r in test),
                      "train_rank_ic": train_ic, "rank_ic": test_ic,
                      "icir": float(np.mean(ic) / np.std(ic, ddof=1)) if len(ic) > 1 and np.std(ic) > 1e-10 else None,
                      "ic_lower": lower, "ic_upper": upper,
                      "degradation": 1 - test_ic / train_ic if train_ic is not None and train_ic > 1e-6 and test_ic is not None else None,
                      "q5_q1_pp": average([r["q5_q1_pp"] for r in test]),
                      "pearson_ic": average([r["pearson_ic"] for r in test]),
                      "mean_delta_pp": average([r["delta"] for r in test]),
                      "coverage": average([r["coverage"] for r in test])})
    return {"kind": "retrospective_diagnostic", "as_of": now.isoformat(), "folds": folds,
            "status": "available" if folds and all(f["complete"] >= 16 for f in folds) else "insufficient_data",
            "note": "当前固定股票池的历史回溯，存在幸存者及复权修订偏差；不计入前瞻成绩。公式未在测试折调参。"}
