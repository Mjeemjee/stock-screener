"""Bounded prospective parameter branches, paired evidence and owner-only review."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from screener.tracking import (ARCHIVE_DIR, ROOT, evaluate_record, finite_positive,
                               freeze_snapshot, instant, read_archives, strategy_version, write_json)

POLICY_PATH = Path(__file__).with_name("lab_policy.json")
PUBLIC_OUT = ROOT / "portfolio-board/public/data/lab.json"
CONDITIONS = {
    "near_high_pct": ("off_52w_high_pct", "high"),
    "near_low_pct": ("off_52w_low_pct", "max"),
    "min_turnover": ("turnover", "min"),
    "min_market_val": ("circular_market_val", "min"),
    "pe_ttm_max": ("pe_ttm_ratio", "max"),
    "dividend_min": ("dividend_ratio_ttm", "min"),
}
CORE = ("id", "root_id", "parent_id", "generation", "market", "source_version",
        "base_params", "params", "created_at", "hypothesis", "expected")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def load_state(directory):
    path = Path(directory) / "lab/state.json"
    rules = policy()
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "schema_version": 1, "policy_hash": digest(rules), "trials": [], "events": [], "processed_sources": {}}
    if state["policy_hash"] != digest(rules):
        raise ValueError("Lab policy changed: migrate the study explicitly; do not reset its budget")
    if len(state["trials"]) > rules["max_trials"]:
        raise ValueError("Lab trial budget exceeded")
    for trial in state["trials"]:
        if trial["definition_hash"] != digest({key: trial[key] for key in CORE}):
            raise ValueError("Lab definition integrity mismatch")
        validate_params(trial["base_params"], trial["params"])
    return state


def save_state(directory, state):
    write_json(Path(directory) / "lab/state.json", state)


def event(state, trial_id, action, now, **detail):
    state["events"].append({"trial_id": trial_id, "action": action,
                            "at": now.isoformat(timespec="seconds"), **detail})


def validate_params(base, params):
    if base.keys() != params.keys():
        raise ValueError("Branches may not add/remove parameters")
    for key, value in params.items():
        if value == base[key]:
            continue
        if key not in CONDITIONS or not finite_positive(value) or not finite_positive(base[key]):
            raise ValueError("Unsupported branch parameter")
        mode = CONDITIONS[key][1]
        if (mode in ("high", "max") and value > base[key]) or (mode == "min" and value < base[key]):
            raise ValueError("Branches must narrow their mother candidate set")


def alternatives(root_id, params):
    if root_id == "momentum_breakout":
        return [("near_high_pct", round(params["near_high_pct"] * 2 / 3, 4), "更接近年内高点"),
                ("min_turnover", round(params["min_turnover"] * 1.5), "提高成交额门槛")]
    if root_id == "oversold_watch":
        return [("near_low_pct", round(params["near_low_pct"] * 2 / 3, 4), "更接近年内低点"),
                ("min_market_val", round(params["min_market_val"] * 1.5), "提高市值门槛")]
    if root_id == "value_dividend_hk":
        return [("pe_ttm_max", round(params["pe_ttm_max"] * 5 / 6, 4), "收紧估值上限"),
                ("dividend_min", round(params["dividend_min"] + 1, 4), "提高股息率门槛")]
    return []


def selected(hits, market, base, params):
    validate_params(base, params)
    output = []
    for hit in hits:
        if not hit["code"].startswith(market + "."):
            continue
        valid = True
        for key, value in params.items():
            if value == base[key]:
                continue
            field, mode = CONDITIONS[key]
            if key == "min_market_val" and params.get("market_value_field"):
                field = params["market_value_field"]
            number = hit.get(field)
            if not isinstance(number, (int, float)) or not np.isfinite(number):
                valid = False
                break
            if not (number >= -value if mode == "high" else number >= value if mode == "min" else number <= value):
                valid = False
                break
        if valid:
            output.append(deepcopy(hit))
    for rank, hit in enumerate(output, 1):
        hit["parent_original_market_rank"] = hit.get("original_market_rank")
        hit["original_rank"] = hit["original_market_rank"] = rank
    return output


def prepare(records, directory, now):
    """Freeze each active experiment and its mother together, once per source."""
    state = load_state(directory)
    current = [r for r in records if r["provenance"] == "prospective" and instant(r["frozen_at"]) <= now]
    if not current:
        return state
    source = current[-1]
    already_processed = source["id"] in state["processed_sources"]
    roots = {s["meta"]["id"]: s for s in source["payload"]["strategies"]}
    trials = {trial["id"]: trial for trial in state["trials"]}
    strategies, mappings = [], []
    for trial in trials.values():
        if trial["status"] not in ("testing", "review"):
            continue
        if any(child["parent_id"] == trial["id"] for child in trials.values()):
            continue
        if trial["source_version"] != source["strategy_version"] or trial["source_version"] != strategy_version():
            trial["status"] = "paused"
            event(state, trial["id"], "paused", now, reason="母策略源码版本已变化")
            continue
        if already_processed:
            continue
        if instant(trial["created_at"]) >= instant(source["frozen_at"]):
            continue
        root = roots.get(trial["root_id"])
        if not root or root["meta"].get("market_params", {}).get(trial["market"]) != trial["base_params"]:
            trial["status"] = "paused"
            event(state, trial["id"], "paused", now, reason="母策略参数或数据范围已变化")
            continue
        parent_params = trials[trial["parent_id"]]["params"] if trial["parent_id"] in trials else trial["base_params"]
        baseline_id = "baseline_" + trial["id"]
        for identity, params in ((baseline_id, parent_params), (trial["id"], trial["params"])):
            hits = selected(root["hits"], trial["market"], trial["base_params"], params)
            meta = deepcopy(root["meta"])
            meta.update(id=identity, name=trial["name"] if identity == trial["id"] else "同期母策略",
                        hit_count=len(hits), market_params={trial["market"]: params})
            strategies.append({"meta": meta, "hits": hits})
        mappings.append({"trial_id": trial["id"], "baseline_id": baseline_id,
                         "definition_hash": trial["definition_hash"]})
    if strategies:
        payload = {"generated_at": now.isoformat(timespec="seconds"), "strategies": strategies,
                   "lab": {"source_id": source["id"], "trials": mappings, "policy": policy()}}
        record = freeze_snapshot(payload, Path(directory) / "lab", frozen_at=now)
        state["processed_sources"][source["id"]] = record["id"]
    save_state(directory, state)
    return state


def observations(directory, stocks, indexes, now):
    output = []
    for record in read_archives(Path(directory) / "lab"):
        evaluated = {r["strategy_id"]: r for r in evaluate_record(record, stocks, indexes, as_of=now,
                                                                horizons=(policy()["horizon"],))}
        for mapping in record["payload"]["lab"]["trials"]:
            baseline = evaluated.get(mapping["baseline_id"])
            if not baseline:
                continue
            branch = evaluated.get(mapping["trial_id"])
            basket = branch["baskets"]["selected"] if branch else {
                "count": 0, "holdings": [], "complete": bool(baseline["exit_date"]),
                "return_pct": 0.0 if baseline["exit_date"] else None}
            output.append({"trial_id": mapping["trial_id"], "snapshot_id": record["id"],
                           "definition_hash": mapping["definition_hash"], "frozen_at": record["frozen_at"],
                           "entry_date": baseline["scheduled_entry_date"],
                           "exit_date": baseline["scheduled_exit_date"], "due": bool(baseline["exit_date"]),
                           "branch": basket, "parent": baseline["baskets"]["selected"],
                           "benchmark_pct": baseline["benchmark_pct"]})
    # Multiple scans for the same market opening are one cohort.
    unique = {}
    for row in sorted(output, key=lambda r: (r["frozen_at"], r["snapshot_id"])):
        unique.setdefault((row["trial_id"], row["entry_date"]), row)
    return sorted(unique.values(), key=lambda r: (r["entry_date"], r["trial_id"]))


def needed_prices(directory, stocks, indexes, now):
    return {h["code"] for row in observations(directory, stocks, indexes, now)
            for basket in (row["branch"], row["parent"]) for h in basket["holdings"]
            if h["status"] in ("missing_entry", "missing_exit")}


def reprice(basket, cost):
    values = []
    for hit in basket["holdings"]:
        if hit["status"] == "no_trade":
            values.append(0.0)
        elif hit["status"] == "matured":
            values.append((hit["exit_price"] / hit["entry_price"] * (1 - cost / 10000) / (1 + cost / 10000) - 1) * 100)
        else:
            return None
    return float(np.mean(values)) if values else 0.0


def metrics(rows, rules):
    due = [r for r in rows if r["due"]]
    paired = [r for r in due if r["branch"]["complete"] and r["parent"]["complete"] and r["benchmark_pct"] is not None]
    delta = [r["branch"]["return_pct"] - r["parent"]["return_pct"] for r in paired]
    independent, last_exit = 0, 0
    for row in paired:
        if row["entry_date"] >= last_exit:
            independent += 1
            last_exit = row["exit_date"]
    mean = lambda values: float(np.mean(values)) if len(values) else None
    lower = None
    if len(delta) >= min(rules["checkpoints"]):
        values = np.asarray(delta)
        block = rules["horizon"]
        starts = np.random.default_rng(271828).integers(len(values), size=(rules["bootstrap_samples"], int(np.ceil(len(values) / block))))
        positions = (starts[:, :, None] + np.arange(block)) % len(values)
        samples = values[positions.reshape(len(starts), -1)[:, :len(values)]].mean(axis=1)
        lower = float(np.quantile(samples, rules["family_alpha"] / rules["max_trials"] / len(rules["checkpoints"])))
    return {"due": len(due), "paired": len(paired), "coverage": len(paired) / len(due) if due else 0,
            "signal_rate": sum(r["branch"]["count"] > 0 for r in due) / len(due) if due else 0,
            "independent": independent, "mean_delta_pp": mean(delta), "lower_delta_pp": lower,
            "mean_return_pct": mean([r["branch"]["return_pct"] for r in paired]),
            "mean_excess_pp": mean([r["branch"]["return_pct"] - r["benchmark_pct"] for r in paired]),
            "stress_excess_pp": mean([reprice(r["branch"], rules["stress_cost_bps"]) - r["benchmark_pct"] for r in paired]),
            "worst_period_pct": min((r["branch"]["return_pct"] for r in paired), default=None)}


def gates(values, rules):
    positive = lambda key: values[key] is not None and values[key] > 0
    return {"coverage": values["coverage"] >= rules["min_coverage"],
            "signal_rate": values["signal_rate"] >= rules["min_signal_rate"],
            "independent": values["independent"] >= rules["min_independent_periods"],
            "improvement": positive("mean_delta_pp"), "uncertainty": positive("lower_delta_pp"),
            "benchmark": positive("mean_excess_pp"), "stress_cost": positive("stress_excess_pp"),
            "risk": values["worst_period_pct"] is not None and values["worst_period_pct"] >= rules["worst_period_floor_pct"]}


def spawn(state, mother, now, rules):
    if mother["generation"] >= rules["max_generations"]:
        return
    if any(t["parent_id"] == mother["id"] for t in state["trials"]):
        return
    for key, value, description in alternatives(mother["root_id"], mother["params"])[:rules["children_per_parent"]]:
        active = sum(t["status"] in ("testing", "review") and t["id"] != mother["id"]
                     and not any(child["parent_id"] == t["id"] for child in state["trials"])
                     for t in state["trials"])
        if len(state["trials"]) >= rules["max_trials"] or active >= rules["max_active"]:
            break
        params = {**mother["params"], key: value}
        if any(t["root_id"] == mother["root_id"] and t["market"] == mother["market"]
               and t["source_version"] == mother["source_version"] and t["params"] == params for t in state["trials"]):
            continue
        trial = {"id": "lab_" + digest([mother["id"], params])[:16], "root_id": mother["root_id"],
                 "parent_id": mother["id"], "generation": mother["generation"] + 1,
                 "market": mother["market"], "source_version": mother["source_version"],
                 "base_params": mother["base_params"], "params": params,
                 "created_at": now.isoformat(timespec="seconds"), "name": description,
                 "hypothesis": f"仅修改 {key}，研究相对母策略的扣费后收益增量",
                 "expected": "改善5日配对收益；必须以未来样本验证，不预设胜率或收益幅度",
                 "change": {"parameter": key, "from": mother["params"][key], "to": value},
                 "status": "testing", "last_checkpoint": 0, "assessments": []}
        trial["definition_hash"] = digest({field: trial[field] for field in CORE})
        state["trials"].append(trial)
        event(state, trial["id"], "created", now, parent_id=mother["id"], change=trial["change"])


def update_lab(records, tracking, stocks, indexes, directory, now, output_path=PUBLIC_OUT):
    state, rules = load_state(directory), policy()
    rows = observations(directory, stocks, indexes, now)
    for trial in list(state["trials"]):
        own = [r for r in rows if r["trial_id"] == trial["id"] and r["definition_hash"] == trial["definition_hash"]]
        trial["metrics"] = metrics(own, rules)
        if trial["status"] != "testing":
            continue
        due = [r for r in own if r["due"]]
        for checkpoint in rules["checkpoints"]:
            if checkpoint <= trial["last_checkpoint"] or len(due) < checkpoint:
                continue
            values = metrics(due[:checkpoint], rules)
            passed = gates(values, rules)
            evidence = {"checkpoint": checkpoint, "metrics": values, "gates": passed,
                        "snapshot_ids": [r["snapshot_id"] for r in due[:checkpoint]],
                        "cohort_hash": digest(due[:checkpoint]),
                        "definition_hash": trial["definition_hash"], "policy_hash": state["policy_hash"]}
            evidence["hash"] = digest(evidence)
            evidence_file = Path(directory) / "lab/evidence" / (evidence["hash"] + ".json")
            evidence_file.parent.mkdir(parents=True, exist_ok=True)
            frozen_evidence = {"assessment": evidence, "cohorts": due[:checkpoint]}
            if evidence_file.exists():
                if json.loads(evidence_file.read_text(encoding="utf-8")) != frozen_evidence:
                    raise ValueError("Conflicting frozen lab evidence")
            else:
                with evidence_file.open("x", encoding="utf-8") as output:
                    json.dump(frozen_evidence, output, ensure_ascii=False, allow_nan=False)
            trial["assessments"].append(evidence)
            trial["last_checkpoint"] = checkpoint
            if all(passed.values()):
                trial["status"] = "review"
            elif checkpoint == max(rules["checkpoints"]):
                trial["status"] = "rejected"
            event(state, trial["id"], "assessed", now, checkpoint=checkpoint, status=trial["status"], evidence_hash=evidence["hash"])
            if trial["status"] == "review":
                break
    roots = []
    if records:
        source = next((r for r in reversed(records) if r["provenance"] == "prospective"), None)
        for strategy in source["payload"]["strategies"] if source else []:
            for market, params in strategy["meta"].get("market_params", {}).items():
                identity = "root_" + digest([strategy["meta"]["id"], market, source["strategy_version"], params])[:16]
                unique = {}
                for row in tracking["evaluations"]:
                    if (row["prospective"] and row["horizon"] == rules["horizon"] and row["market"] == market
                            and row["strategy_id"] == strategy["meta"]["id"] and row["strategy_version"] == source["strategy_version"]):
                        unique.setdefault(row["scheduled_entry_date"], row)
                count = sum(r["baskets"]["selected"]["complete"] and r["benchmark_pct"] is not None for r in unique.values())
                root = {"id": identity, "root_id": strategy["meta"]["id"], "name": strategy["meta"]["name"],
                        "generation": 0, "market": market, "source_version": source["strategy_version"],
                        "base_params": params, "params": params, "matured": count,
                        "supported": bool(alternatives(strategy["meta"]["id"], params))}
                roots.append(root)
                if count >= rules["spawn_after"] and source["strategy_version"] == strategy_version():
                    spawn(state, root, now, rules)
    for trial in list(state["trials"]):
        if trial["status"] == "review":
            spawn(state, trial, now, rules)
    save_state(directory, state)
    report = {"schema_version": 1, "generated_at": now.isoformat(timespec="seconds"), "policy": rules,
              "policy_hash": state["policy_hash"], "parents": roots, "trials": state["trials"],
              "events": state["events"], "observations": rows,
              "review_workflow": "https://github.com/Mjeemjee/stock-screener/actions/workflows/review-lab.yml"}
    write_json(output_path, report)
    return report


def review(directory, trial_id, decision, evidence_hash, actor, rules_path=None, now=None):
    if decision not in ("approve", "reject", "pause") or not actor.strip():
        raise ValueError("An explicit owner decision and actor are required")
    now = now or datetime.now(timezone.utc)
    state = load_state(directory)
    trial = next(t for t in state["trials"] if t["id"] == trial_id)
    evidence = trial["assessments"][-1] if trial["assessments"] else None
    if decision == "pause":
        expected = evidence["hash"] if evidence else trial["definition_hash"]
        if trial["status"] not in ("testing", "review") or evidence_hash != expected:
            raise ValueError("Pause request is stale or this trial is not observing")
        trial["status"] = "paused"
        event(state, trial_id, "paused", now, actor=actor, reason="仓库所有者手动暂停")
        save_state(directory, state)
        return
    if trial["status"] != "review" or not evidence or evidence["hash"] != evidence_hash:
        raise ValueError("Review is stale or this trial is not eligible")
    if digest({key: value for key, value in evidence.items() if key != "hash"}) != evidence_hash:
        raise ValueError("Evidence integrity mismatch")
    frozen = json.loads((Path(directory) / "lab/evidence" / (evidence_hash + ".json")).read_text(encoding="utf-8"))
    if frozen["assessment"] != evidence or digest(frozen["cohorts"]) != evidence["cohort_hash"]:
        raise ValueError("Frozen evidence prices or observations were changed")
    if decision == "approve":
        if (not all(gates(metrics(frozen["cohorts"], policy()), policy()).values())
                or not all(evidence["gates"].values()) or trial["source_version"] != strategy_version()):
            raise ValueError("Evidence gates or source version no longer match")
        from screener import market_policy
        from screener.common import load_strategies
        from screener.free_hk_fundamentals import cloud_strategy
        modules = {m.META["id"]: m for m in load_strategies()}
        module = cloud_strategy({}) if trial["root_id"] == "value_dividend_hk" else modules[trial["root_id"]]
        path = Path(rules_path) if rules_path else market_policy.RULES_PATH
        config = json.loads(path.read_text(encoding="utf-8"))
        current = {**module.META["params"], **config["strategies"].get(trial["root_id"], {}).get(trial["market"], {}),
                   **module.META.get("market_params", {}).get(trial["market"], {})}
        if current != trial["base_params"]:
            raise ValueError("Mother parameters changed since this experiment was created")
        validate_params(trial["base_params"], trial["params"])
        config["strategies"].setdefault(trial["root_id"], {})[trial["market"]] = trial["params"]
        write_json(path, config)
    trial["status"] = "approved" if decision == "approve" else "rejected"
    event(state, trial_id, decision, now, actor=actor, evidence_hash=evidence_hash)
    save_state(directory, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=ARCHIVE_DIR)
    parser.add_argument("--output", type=Path, default=PUBLIC_OUT)
    parser.add_argument("--trial")
    parser.add_argument("--decision", choices=("approve", "reject", "pause"))
    parser.add_argument("--evidence-hash")
    parser.add_argument("--actor", default="")
    parser.add_argument("--report-only", action="store_true", help="Refresh lab without changing published screening/tracking data")
    args = parser.parse_args()
    if args.decision:
        review(args.archive_dir, args.trial, args.decision, args.evidence_hash, args.actor)
    if args.report_only:
        from screener.risk import load_histories, HISTORY_DIR
        records = read_archives(args.archive_dir)
        tracking = json.loads((args.output.parent / "tracking.json").read_text(encoding="utf-8-sig"))
        known = {r["id"] for r in records}
        if not {r["id"] for r in tracking["archives"]} <= known:
            raise ValueError("Public tracking references an archive missing from the cumulative backup")
        stocks, indexes = load_histories(HISTORY_DIR)
        for file in (args.archive_dir / "prices").glob("*.json"):
            node = json.loads(file.read_text(encoding="utf-8"))
            current = stocks.get(node["code"], [])
            if node["bars"] and (not current or node["bars"][-1][0] > current[-1][0]):
                stocks[node["code"]] = node["bars"]
        now = datetime.now(timezone.utc)
        prepare(records, args.archive_dir, now)
        update_lab(records, tracking, stocks, indexes, args.archive_dir, now, args.output)
        return
    from screener.tracking import update_tracking
    update_tracking(args.archive_dir, output_path=args.output.parent / "tracking.json")


if __name__ == "__main__":
    main()
