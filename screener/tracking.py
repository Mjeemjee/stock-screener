"""Immutable candidate archives and next-open, fixed-weight paper evaluation."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from screener.risk import HISTORY_DIR, ZONES, exchange_calendar, load_histories

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = ROOT / "data/screening_archive"
TRACKING_OUT = ROOT / "portfolio-board/public/data/tracking.json"
HORIZONS = (5, 20, 60)
TOP_N = 10
COST_BPS = 15


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    return result.astimezone(timezone.utc)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for delay in (.05, .1, .2):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if os.name != "nt":
                raise
            time.sleep(delay)
    # Windows readers may deny replacement while permitting a derived-file refresh.
    # Immutable snapshots use exclusive creation separately and never take this path.
    path.write_text(temporary.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        temporary.unlink()
    except PermissionError:
        pass


def strategy_version():
    digest = hashlib.sha256()
    files = sorted((ROOT / "screener").rglob("*.py")) + [ROOT / "screener/market_rules.json", ROOT / "screener/lab_policy.json"]
    for file in files:
        if "tests" in file.parts:
            continue
        digest.update(str(file.relative_to(ROOT)).replace("\\", "/").encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def freeze_snapshot(payload, archive_dir=ARCHIVE_DIR, *, prospective=True, frozen_at=None):
    """Freeze all hits before truncation; retries cannot replace the first freeze time."""
    snapshot = deepcopy(payload)
    full = all(s["meta"].get("hit_count", len(s["hits"])) == len(s["hits"])
               for s in snapshot["strategies"])
    if prospective and not full:
        raise ValueError("Cannot prospectively archive truncated candidates")
    if prospective:
        for strategy in snapshot["strategies"]:
            codes = [hit["code"] for hit in strategy["hits"]]
            if len(set(codes)) != len(codes):
                raise ValueError("Duplicate candidates cannot be prospectively archived")
            for market in ("US", "HK"):
                ranks = [hit.get("original_market_rank") for hit in strategy["hits"] if hit["code"].startswith(market + ".")]
                if set(ranks) != set(range(1, len(ranks) + 1)):
                    raise ValueError("Original market ranks must be complete before freezing")
    version = strategy_version()
    source = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    digest = hashlib.sha256(source).hexdigest()
    record_id = hashlib.sha256(source + version.encode() + str(prospective).encode()).hexdigest()[:24]
    directory = Path(archive_dir) / "snapshots"
    path = directory / f"{record_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    now = frozen_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Freeze time must include a timezone")
    try:
        generated = instant(snapshot["generated_at"])
        timestamp_valid = generated <= now
    except (ValueError, TypeError):
        timestamp_valid = False
    if prospective and not timestamp_valid:
        raise ValueError("A prospective snapshot needs a valid generation time no later than freeze time")
    for strategy in snapshot["strategies"]:
        ranks = {}
        for rank, hit in enumerate(strategy["hits"], 1):
            market = hit["code"].split(".")[0]
            ranks[market] = ranks.get(market, 0) + 1
            hit["selection_rank"] = rank
            hit["selection_market_rank"] = ranks[market]
    record = {
        "schema_version": 1, "id": record_id, "strategy_version": version,
        "input_sha256": digest,
        "payload_sha256": hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
        "hash_scope": "frozen_payload", "frozen_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "provenance": "prospective" if prospective else "historical_import",
        "complete_candidates": full, "generation_time_verified": timestamp_valid,
        "payload": snapshot,
    }
    directory.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves an existing archive even during concurrent retries.
    try:
        with path.open("x", encoding="utf-8") as output:
            json.dump(record, output, ensure_ascii=False, indent=2, allow_nan=False)
    except FileExistsError:
        return json.loads(path.read_text(encoding="utf-8"))
    return record


def read_archives(directory=ARCHIVE_DIR):
    records = [json.loads(path.read_text(encoding="utf-8"))
               for path in sorted((Path(directory) / "snapshots").glob("*.json"))]
    for record in records:
        payload = deepcopy(record["payload"])
        for strategy in payload["strategies"]:
            market_ranks = {}
            for rank, hit in enumerate(strategy["hits"], 1):
                market = hit["code"].split(".")[0]
                market_ranks[market] = market_ranks.get(market, 0) + 1
                if hit.get("selection_rank") != rank or hit.get("selection_market_rank") != market_ranks[market]:
                    raise ValueError(f"Archive ranking integrity mismatch: {record['id']}")
        if record.get("hash_scope") != "frozen_payload":
            # Initial archives hashed the input before selection annotations were added.
            for strategy in payload["strategies"]:
                for hit in strategy["hits"]:
                    hit.pop("selection_rank", None)
                    hit.pop("selection_market_rank", None)
        actual = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        if actual != record["payload_sha256"]:
            raise ValueError(f"Archive integrity mismatch: {record['id']}")
    return sorted(records, key=lambda record: (record["frozen_at"], record["id"]))


def price_rows(bars):
    rows = {}
    previous = 0
    for row in bars:
        day = int(row[0])
        if day <= previous:
            raise ValueError("Daily bars must have unique ascending dates")
        previous = day
        rows[day] = row
    return rows


def finite_positive(value):
    return isinstance(value, (int, float)) and 0 < value < float("inf")


def evaluate_holding(bars, entry_day, exit_day, *, cost_bps=COST_BPS):
    rows = price_rows(bars)
    entry = rows.get(entry_day)
    if entry is None or not finite_positive(entry[1]):
        return {"status": "missing_entry", "return_pct": None}
    if len(entry) < 6 or not isinstance(entry[5], (int, float)) or not 0 <= entry[5] < float("inf"):
        return {"status": "missing_entry", "return_pct": None}
    if entry[5] == 0:
        return {"status": "no_trade", "return_pct": 0.0}
    if exit_day is None:
        return {"status": "pending", "return_pct": None, "entry_price": entry[1]}
    exit_row = rows.get(exit_day)
    if exit_row is None or not finite_positive(exit_row[1]) or len(exit_row) < 6 or not finite_positive(exit_row[5]):
        return {"status": "missing_exit", "return_pct": None, "entry_price": entry[1]}
    fee = cost_bps / 10000
    net = (exit_row[1] / entry[1]) * (1 - fee) / (1 + fee) - 1
    return {"status": "matured", "return_pct": round(net * 100, 6),
            "entry_price": entry[1], "exit_price": exit_row[1]}


def evaluate_record(record, stocks, indexes, *, as_of=None, horizons=HORIZONS):
    now = as_of or datetime.now(timezone.utc)
    cutoff = instant(record["frozen_at"])
    rows = []
    for strategy in record["payload"]["strategies"]:
        for market in ("US", "HK"):
            candidates = [hit for hit in strategy["hits"] if hit["code"].startswith(market + ".")]
            if not candidates:
                continue
            index_bars = indexes.get("SPX" if market == "US" else "HSI", [])
            from zoneinfo import ZoneInfo
            calendar = exchange_calendar(market)
            local_date = cutoff.astimezone(ZoneInfo(ZONES[market])).date().isoformat()
            entry_session = calendar.date_to_session(local_date, direction="next")
            if calendar.session_open(entry_session).to_pydatetime() <= cutoff:
                entry_session = calendar.next_session(entry_session)
            entry_day = (int(entry_session.strftime("%Y%m%d"))
                         if calendar.session_open(entry_session).to_pydatetime() <= now else None)
            original_known = all(isinstance(hit.get("original_market_rank"), int) for hit in candidates)
            modes = {"selected": candidates[:TOP_N]}
            if original_known:
                modes["original"] = sorted(candidates, key=lambda hit: hit["original_market_rank"])[:TOP_N]
            benchmark = price_rows(index_bars)
            for horizon in horizons:
                exit_session = calendar.session_offset(entry_session, horizon)
                exit_day = (int(exit_session.strftime("%Y%m%d"))
                            if entry_day and calendar.session_open(exit_session).to_pydatetime() <= now else None)
                row = {"snapshot_id": record["id"], "strategy_id": strategy["meta"]["id"],
                       "strategy_name": strategy["meta"]["name"], "market": market,
                       "strategy_version": record["strategy_version"], "horizon": horizon,
                       "scheduled_entry_date": int(entry_session.strftime("%Y%m%d")),
                       "scheduled_exit_date": int(exit_session.strftime("%Y%m%d")),
                       "entry_date": entry_day, "exit_date": exit_day,
                       "prospective": record["provenance"] == "prospective",
                       "original_rank_known": original_known, "baskets": {}, "benchmark_pct": None}
                for mode, chosen in modes.items():
                    detail = [{"code": hit["code"], **(evaluate_holding(stocks.get(hit["code"], []), entry_day, exit_day)
                              if entry_day else {"status": "pending", "return_pct": None})} for hit in chosen]
                    complete = bool(exit_day) and all(item["return_pct"] is not None for item in detail)
                    row["baskets"][mode] = {
                        "count": len(chosen), "complete": complete, "holdings": detail,
                        "known_count": sum(item["return_pct"] is not None for item in detail),
                        "return_pct": round(sum(item["return_pct"] for item in detail) / len(chosen), 6) if complete else None,
                    }
                if entry_day and exit_day:
                    b0, b1 = benchmark.get(entry_day), benchmark.get(exit_day)
                    if b0 and b1 and finite_positive(b0[1]) and finite_positive(b1[1]):
                        row["benchmark_pct"] = round((b1[1] / b0[1] - 1) * 100, 6)
                rows.append(row)
    return rows


def summarize(rows, records):
    # Weekend and manual scans targeting the same opening are one cohort per version.
    record_map = {record["id"]: record for record in records}
    groups, seen = {}, set()
    for row in sorted(rows, key=lambda item: record_map[item["snapshot_id"]]["frozen_at"]):
        if record_map[row["snapshot_id"]]["provenance"] != "prospective":
            continue
        key = (row["strategy_id"], row["market"], row["horizon"], row["strategy_version"])
        cohort = (*key, row.get("scheduled_entry_date", row.get("entry_date")))
        if cohort in seen:
            continue
        seen.add(cohort)
        group = groups.setdefault(key, {"strategy_id": key[0], "market": key[1], "horizon": key[2],
                                       "strategy_version": key[3], "cohorts": 0, "paired": []})
        group["cohorts"] += 1
        selected, original = row["baskets"].get("selected"), row["baskets"].get("original")
        if selected and original and selected["complete"] and original["complete"] and row["benchmark_pct"] is not None:
            group["paired"].append((selected["return_pct"], original["return_pct"], row["benchmark_pct"]))
    output = []
    for group in groups.values():
        paired = group.pop("paired")
        group["matured_pairs"] = len(paired)
        group["mean_selected_pct"] = sum(p[0] for p in paired) / len(paired) if paired else None
        group["mean_original_pct"] = sum(p[1] for p in paired) / len(paired) if paired else None
        group["mean_benchmark_pct"] = sum(p[2] for p in paired) / len(paired) if paired else None
        group["mean_delta_pp"] = sum(p[0] - p[1] for p in paired) / len(paired) if paired else None
        output.append(group)
    return output


def update_tracking(archive_dir=ARCHIVE_DIR, history_dir=HISTORY_DIR, output_path=TRACKING_OUT,
                    *, as_of=None, fetch_missing=False, max_fetch=80):
    now = as_of or datetime.now(timezone.utc)
    records = read_archives(archive_dir)
    from screener.research_lab import prepare, needed_prices, update_lab
    prepare(records, archive_dir, now)
    stocks, indexes = load_histories(history_dir)
    cached = Path(archive_dir) / "prices"
    for file in sorted(cached.glob("*.json")):
        node = json.loads(file.read_text(encoding="utf-8"))
        current = stocks.get(node["code"], [])
        if node["bars"] and (not current or int(node["bars"][-1][0]) > int(current[-1][0])):
            stocks[node["code"]] = node["bars"]
    rows = [row for record in records for row in evaluate_record(record, stocks, indexes, as_of=now)]
    needed = sorted({h["code"] for row in rows if row["prospective"] for basket in row["baskets"].values() for h in basket["holdings"]
                     if h["status"] in ("missing_entry", "missing_exit")})
    needed = sorted(set(needed) | needed_prices(archive_dir, stocks, indexes, now))
    fetched, failed = 0, []
    if fetch_missing:
        from screener.history_fetch import hk_bars, us_bars
        attempts_path = Path(archive_dir) / "fetch_attempts.json"
        attempts = json.loads(attempts_path.read_text(encoding="utf-8")) if attempts_path.exists() else {}
        queue = sorted(needed, key=lambda code: (attempts.get(code, ""), code))
        for code in queue[:max_fetch]:
            attempts[code] = now.isoformat(timespec="seconds")
            try:
                bars = (hk_bars if code.startswith("HK.") else us_bars)(code)
                if not bars:
                    raise ValueError("No price history")
                price_rows(bars)
                stocks[code] = bars
                write_json(cached / (hashlib.sha256(code.encode()).hexdigest()[:20] + ".json"), {"code": code, "bars": bars})
                fetched += 1
            except Exception:
                failed.append(code)
            time.sleep(.15)
        write_json(attempts_path, attempts)
        rows = [row for record in records for row in evaluate_record(record, stocks, indexes, as_of=now)]
    result = {
        "schema_version": 1, "generated_at": now.isoformat(timespec="seconds"),
        "protocol": {"version": 2, "calendar": "exchange-calendars XNYS / XHKG",
                     "top_n": TOP_N, "horizons": HORIZONS, "cost_bps_per_side": COST_BPS,
                     "entry": "first market opening after frozen_at", "exit": "H sessions after entry, at open",
                     "aggregation": "paired mean period returns; overlapping cohorts are not compounded"},
        "archives": [{"id": r["id"], "generated_at": r["payload"]["generated_at"],
                      "frozen_at": r["frozen_at"], "provenance": r["provenance"],
                      "strategy_version": r["strategy_version"], "complete_candidates": r["complete_candidates"],
                      "candidate_count": sum(len(s["hits"]) for s in r["payload"]["strategies"])} for r in records],
        "summary": summarize(rows, records), "evaluations": rows,
        "history_refresh": {"needed": len(needed), "fetched": fetched, "failed": failed,
                            "budget_excluded": max(0, len(needed) - max_fetch) if fetch_missing else len(needed)},
    }
    from screener.risk import completed_bars, risk_metrics
    securities, appearances = {}, {}
    for record in records:
        for strategy in record["payload"]["strategies"]:
            for hit in strategy["hits"]:
                code = hit["code"]
                securities[code] = {**hit, "last_seen": record["payload"]["generated_at"]}
                appearances.setdefault(code, []).append({
                    "snapshot_id": record["id"], "generated_at": record["payload"]["generated_at"],
                    "strategy_name": strategy["meta"]["name"], "provenance": record["provenance"],
                    "original_market_rank": hit.get("original_market_rank"),
                    "selection_market_rank": hit.get("selection_market_rank"),
                    "factor_score": hit.get("factor_score"),
                })
    for code, security in securities.items():
        market = code.split(".")[0]
        bars = stocks.get(code, [])
        for field in ("risk_as_of", "volatility_20d_pct", "drawdown_120d_pct", "median_turnover_20d", "risk_window_sessions"):
            security.pop(field, None)
        security.update(risk_metrics(bars, market, now))
        security["history"] = [[bar[0], bar[4]] for bar in completed_bars(bars, market, now)[-120:]]
    result["securities"] = securities
    result["appearances"] = {code: entries[-100:] for code, entries in appearances.items()}
    write_json(output_path, result)
    decision_time = now if as_of is not None else datetime.now(timezone.utc)
    update_lab(records, result, stocks, indexes, archive_dir, decision_time,
               output_path=Path(output_path).parent / "lab.json")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-snapshot", type=Path, help="Import a past snapshot, excluded from prospective statistics")
    parser.add_argument("--archive-dir", type=Path, default=ARCHIVE_DIR)
    parser.add_argument("--history-dir", type=Path, default=HISTORY_DIR)
    parser.add_argument("--output", type=Path, default=TRACKING_OUT)
    parser.add_argument("--fetch-missing", action="store_true")
    parser.add_argument("--sync-latest", action="store_true", help="Rebuild the local screener display from the latest frozen full snapshot")
    args = parser.parse_args()
    if args.import_snapshot:
        freeze_snapshot(json.loads(args.import_snapshot.read_text(encoding="utf-8")), args.archive_dir, prospective=False)
    if args.sync_latest:
        from screener.common import finalize_results, save_payload
        records = read_archives(args.archive_dir)
        prospective = [record for record in records if record["provenance"] == "prospective"]
        if not prospective:
            raise ValueError("No prospective snapshot is available to sync")
        record = prospective[-1]
        payload = deepcopy(record["payload"])
        payload["archive_id"] = record["id"]
        payload["strategy_version"] = record["strategy_version"]
        finalize_results(payload["strategies"])
        save_payload(payload, str(ROOT / "portfolio-board/public/data/screener_results.json"))
    result = update_tracking(args.archive_dir, args.history_dir, args.output, fetch_missing=args.fetch_missing)
    print(f"Tracking: {len(result['archives'])} archives, {len(result['evaluations'])} observations")


if __name__ == "__main__":
    main()
