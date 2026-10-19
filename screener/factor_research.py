"""Independent factor studies: fixed pools, typed proposals and future-only trials."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re

from screener import research_signals as signals
from screener import research_validation as validation
from screener.research_lab import digest, gates, metrics
from screener.risk import HISTORY_DIR, load_histories
from screener.tracking import (ARCHIVE_DIR, ROOT, evaluate_record, freeze_snapshot,
                               instant, read_archives, write_json)

POLICY_PATH = Path(__file__).with_name("research_policy.json")
PUBLIC_OUT = ROOT / "portfolio-board/public/data/research.json"
CORE = ("id", "name", "family", "market", "parent_id", "generation", "op_type", "hypothesis",
        "change", "expected", "expression", "filters", "baseline", "controls", "created_at",
        "engine_version", "policy_hash", "universe_hash", "discovery")
WORKFLOW = "https://github.com/Mjeemjee/stock-screener/actions/workflows/review-factor-research.yml"


def policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def engine_version():
    names = ("factor_research.py", "research_signals.py", "research_validation.py", "research_lab.py",
             "factor_rank.py", "tracking.py", "risk.py", "research_policy.json")
    return digest({name: Path(__file__).with_name(name).read_text(encoding="utf-8") for name in names})


def sealed(path, payload):
    path = Path(path)
    envelope = {"hash": digest(payload), "payload": payload}
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read_sealed(path) != payload:
            raise ValueError("Immutable research evidence conflict: " + path.name)
    else:
        with path.open("x", encoding="utf-8") as out:
            json.dump(envelope, out, ensure_ascii=False, allow_nan=False)
    return envelope["hash"]


def read_sealed(path):
    node = json.loads(Path(path).read_text(encoding="utf-8"))
    if digest(node["payload"]) != node["hash"]:
        raise ValueError("Research evidence integrity mismatch")
    return node["payload"]


def load_state(directory):
    path = Path(directory) / "research/state.json"
    rules = policy()
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "schema_version": 1, "policy_hash": digest(rules), "universes": {}, "programs": [],
        "events": [], "searches": [], "inputs": {}, "fetch_attempts": {}}
    if state["policy_hash"] != digest(rules):
        raise ValueError("Research policy changed; explicitly migrate, never reset the study budget")
    ids = [p["id"] for p in state["programs"]]
    if len(ids) != len(set(ids)) or len(ids) > rules["max_programs"] or len(state["searches"]) > rules["max_searches"]:
        raise ValueError("Research identities or lifetime budget invalid")
    for universe in state["universes"].values():
        if universe["hash"] != digest({k: v for k, v in universe.items() if k != "hash"}):
            raise ValueError("Fixed universe changed")
        codes = [m["code"] for m in universe["members"]]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate fixed universe members")
    for program in state["programs"]:
        signals.validate_spec(program)
        if program["definition_hash"] != digest({k: program[k] for k in CORE}):
            raise ValueError("Research definition changed")
        if program["universe_hash"] != state["universes"][program["market"]]["hash"]:
            raise ValueError("Experiment universe changed")
    return state


def save_state(directory, state):
    write_json(Path(directory) / "research/state.json", state)


def log(state, action, now, program_id=None, **detail):
    state["events"].append({"action": action, "at": now.isoformat(), "program_id": program_id, **detail})


def register(state, spec, market, now, discovery, parent=None):
    rules = policy()
    signals.validate_spec(spec)
    for field in ("name", "op_type", "hypothesis", "change", "expected"):
        if not isinstance(spec.get(field), str) or not 1 <= len(spec[field].strip()) <= (60 if field == "name" else 400):
            raise ValueError("Missing or oversized proposal field: " + field)
    if market not in state["universes"]:
        raise ValueError("The research market has no frozen universe")
    if len(state["programs"]) >= rules["max_programs"]:
        raise ValueError("Research lifetime program budget exhausted")
    if sum(p["status"] in ("testing", "review", "approved") for p in state["programs"]) >= rules["max_active"]:
        raise ValueError("Concurrent research program limit reached")
    version = engine_version()
    if any(p["market"] == market and p["engine_version"] == version and signals.fingerprint(p) == signals.fingerprint(spec)
           for p in state["programs"]):
        raise ValueError("Duplicate research formula")
    generation = parent["generation"] + 1 if parent else 1
    if generation > rules["max_generations"] or parent and parent["market"] != market:
        raise ValueError("Invalid parent market or generation")
    controls = [signals.feature(k) for k, v in signals.FEATURES.items() if v["family"] == "control"]
    controls += [deepcopy(p["expression"]) for p in state["programs"] if p["market"] == market]
    program = {k: deepcopy(spec[k]) for k in ("name", "op_type", "hypothesis", "change", "expected", "expression", "filters")}
    program.update(family=spec.get("family", "custom"), market=market, parent_id=parent["id"] if parent else None,
                   generation=generation, baseline={k: deepcopy(parent[k]) for k in ("expression", "filters")} if parent else None,
                   controls=controls, created_at=now.isoformat(), engine_version=version, policy_hash=state["policy_hash"],
                   universe_hash=state["universes"][market]["hash"], discovery=discovery)
    program["id"] = "factor_" + digest(program)[:16]
    program["definition_hash"] = digest({k: program[k] for k in CORE})
    program.update(status="testing", assessments=[], last_checkpoint=0)
    state["programs"].append(program)
    log(state, "created", now, program["id"], parent_id=program["parent_id"], origin=discovery["kind"])
    return program


def initialize(state, history_dir, now):
    for market in ("US", "HK"):
        if market in state["universes"]:
            continue
        path = Path(history_dir) / (market.lower() + ".json")
        if not path.exists():
            continue
        source = json.loads(path.read_text(encoding="utf-8"))
        members, seen = [], set()
        for stock in source.get("stocks", []):
            code = stock.get("code", "")
            if not re.fullmatch(market + r"\.[A-Za-z0-9][A-Za-z0-9.\-]*", code) or code in seen:
                continue
            members.append({"code": code, "name": stock.get("name") or code})
            seen.add(code)
            if len(members) == policy()["pool_size"]:
                break
        if len(members) < policy()["min_cross_section"]:
            continue
        universe = {"market": market, "members": members, "created_at": now.isoformat(),
                    "source_generated_at": source.get("generated_at"), "source_count": len(source.get("stocks", [])),
                    "basis": "首次可用流动性历史池的前40只；固定成员，不随策略命中名单变化"}
        universe["hash"] = digest(universe)
        state["universes"][market] = universe
        for spec in signals.SEEDS:
            register(state, spec, market, now, {"kind": "predeclared", "note": "预先声明的新策略家族"})


def update_prices(state, directory, history_dir, now, fetch_missing=False, max_fetch=8):
    stocks, indexes = load_histories(history_dir)
    cache = Path(directory) / "research/prices"
    members = [m["code"] for u in state["universes"].values() for m in u["members"]]
    for code in members:
        path = cache / (code + ".json")
        saved = json.loads(path.read_text(encoding="utf-8"))["bars"] if path.exists() else []
        incoming = stocks.get(code, [])
        market = code.split(".")[0]
        incoming = validation.usable_prices({code: incoming}, market, now).get(code, [])
        if incoming and (not saved or incoming[-1][0] >= saved[-1][0]):
            write_json(path, {"code": code, "observed_at": now.isoformat(), "bars": incoming})
        else:
            stocks[code] = saved
    if fetch_missing:
        from screener.history_fetch import hk_bars, us_bars
        due = [code for code in members if not stocks.get(code)
               or stocks[code][-1][0] < validation.last_completed(code.split(".")[0], now)]
        for code in sorted(due, key=lambda c: (state["fetch_attempts"].get(c, ""), c))[:max_fetch]:
            state["fetch_attempts"][code] = now.isoformat()
            try:
                fetched = (hk_bars if code.startswith("HK.") else us_bars)(code)
                valid = validation.usable_prices({code: fetched or []}, code.split(".")[0], now).get(code, [])
                if valid and (not stocks.get(code) or valid[-1][0] >= stocks[code][-1][0]):
                    stocks[code] = valid
                    write_json(cache / (code + ".json"), {"code": code, "observed_at": now.isoformat(), "bars": valid})
            except (ValueError, RuntimeError, OSError) as exc:
                log(state, "price_unavailable", now, code=code, reason=str(exc)[:180])
    return stocks, indexes


def freeze_inputs(state, directory, stocks, now):
    quality = []
    base = Path(directory) / "research"
    rules = policy()
    for program in state["programs"]:
        if program["status"] in ("testing", "review", "approved") and program["engine_version"] != engine_version():
            program["status"] = "paused"
            log(state, "paused", now, program["id"], reason="研究引擎版本变化，需重新提出并验证")
    for market, universe in state["universes"].items():
        day = validation.last_completed(market, now)
        input_id = market + "_" + str(day)
        prices = validation.usable_prices(stocks, market, now)
        panel, missing, bars = validation.panel_at(universe["members"], prices, market, day)
        coverage = len(panel) / len(universe["members"])
        ready = len(panel) >= rules["min_cross_section"] and coverage >= rules["min_data_coverage"]
        quality.append({"market": market, "session": day, "valid": len(panel), "total": len(universe["members"]),
                        "coverage": coverage, "missing": missing, "status": "ready" if ready else "insufficient_data",
                        "already_frozen": input_id in state["inputs"]})
        if input_id in state["inputs"] or not ready:
            continue
        frame = {"id": input_id, "market": market, "session": day, "frozen_at": now.isoformat(),
                 "universe_hash": universe["hash"], "panel": panel, "missing": missing, "bars": bars}
        path = base / "inputs" / (input_id + ".json")
        if path.exists():
            frame = read_sealed(path)
        if frame["universe_hash"] != universe["hash"]:
            raise ValueError("Frozen input belongs to a different research universe")
        input_hash = sealed(path, frame)
        panel = frame["panel"]
        strategies, mappings = [], []
        def strategy(identity, name, chosen):
            hits = [{**hit, "original_rank": i, "original_market_rank": i} for i, hit in enumerate(chosen, 1)]
            return {"meta": {"id": identity, "name": name, "hit_count": len(hits)}, "hits": hits}
        strategies.append(strategy("research_pool", "同期研究池等权", [{"code": c} for c in sorted(panel)]))
        for program in state["programs"]:
            if (program["market"] != market or program["status"] not in ("testing", "review", "approved")
                    or instant(program["created_at"]) > instant(frame["frozen_at"])):
                continue
            chosen = signals.select(program, panel, rules["top_n"])
            strategies.append(strategy(program["id"], program["name"], chosen))
            baseline_id = "research_pool"
            if program["baseline"]:
                baseline_id = "parent_" + program["id"]
                strategies.append(strategy(baseline_id, "同期父策略", signals.select(program["baseline"], panel, rules["top_n"])))
            mappings.append({"program_id": program["id"], "definition_hash": program["definition_hash"],
                             "baseline_id": baseline_id, "selected": chosen})
        payload = {"generated_at": frame["frozen_at"], "strategies": strategies,
                   "research": {"input_id": input_id, "input_hash": input_hash, "programs": mappings}}
        record = freeze_snapshot(payload, base / "runs", frozen_at=instant(frame["frozen_at"]))
        state["inputs"][input_id] = {"hash": input_hash, "run_id": record["id"]}
    return quality


def observations(state, directory, stocks, indexes, now):
    base = Path(directory) / "research"
    programs = {p["id"]: p for p in state["programs"]}
    output, seen = [], set()
    for record in read_archives(base / "runs"):
        context = record["payload"]["research"]
        if state["inputs"].get(context["input_id"], {}).get("run_id") != record["id"]:
            continue
        frame = read_sealed(base / "inputs" / (context["input_id"] + ".json"))
        if digest(frame) != context["input_hash"]:
            raise ValueError("Research input/run binding changed")
        evaluated = {r["strategy_id"]: r for r in evaluate_record(record, stocks, indexes, as_of=now,
                     horizons=(policy()["horizon"],), top_n=None, cost_bps=policy()["cost_bps"])}
        pool = evaluated.get("research_pool")
        if not pool:
            continue
        for mapping in context["programs"]:
            program = programs[mapping["program_id"]]
            if mapping["definition_hash"] != program["definition_hash"]:
                raise ValueError("Research run definition mismatch")
            identity = (program["id"], pool["scheduled_entry_date"])
            if identity in seen:
                continue
            seen.add(identity)
            cache = base / "settled" / (program["id"] + "_" + str(identity[1]) + ".json")
            if cache.exists():
                output.append(read_sealed(cache))
                continue
            empty = {"count": 0, "holdings": [], "complete": bool(pool["exit_date"]),
                     "return_pct": 0.0 if pool["exit_date"] else None}
            branch = evaluated.get(program["id"], {}).get("baskets", {}).get("selected", empty)
            parent = evaluated.get(mapping["baseline_id"], {}).get("baskets", {}).get("selected", empty)
            row = {"trial_id": program["id"], "definition_hash": program["definition_hash"],
                   "snapshot_id": record["id"], "input_id": context["input_id"],
                   "frozen_at": record["frozen_at"], "entry_date": pool["scheduled_entry_date"],
                   "exit_date": pool["scheduled_exit_date"], "due": bool(pool["exit_date"]),
                   "branch": branch, "parent": parent, "pool": pool["baskets"]["selected"],
                   "benchmark_pct": pool["benchmark_pct"], "selected": mapping["selected"],
                   "rank_ic": None, "pearson_ic": None, "novelty_max": None, "control_correlations": []}
            if row["due"]:
                row.update(validation.diagnostics(program, frame["panel"], row["pool"], program["controls"]))
            if row["due"] and all(row[b]["complete"] for b in ("branch", "parent", "pool")) and row["benchmark_pct"] is not None:
                sealed(cache, row)
            output.append(row)
    return sorted(output, key=lambda r: (r["entry_date"], r["trial_id"]))


def assess(rows, rules):
    values = metrics(rows, {**rules, "max_trials": rules["comparison_budget"]})
    values.update(rank_ic=validation.average([r["rank_ic"] for r in rows if r["due"]]),
                  pearson_ic=validation.average([r["pearson_ic"] for r in rows if r["due"]]),
                  novelty=validation.novelty(rows))
    checks = gates(values, rules)
    checks["novelty"] = values["novelty"] is not None and values["novelty"] < rules["max_correlation"]
    return values, checks


def checkpoints(state, rows, directory, now):
    rules = policy()
    for program in state["programs"]:
        own = [r for r in rows if r["trial_id"] == program["id"]]
        program["metrics"], _ = assess(own, rules)
        if program["status"] != "testing":
            continue
        due = [r for r in own if r["due"]]
        for n in rules["checkpoints"]:
            if len(due) < n or n <= program["last_checkpoint"]:
                continue
            values, checks = assess(due[:n], rules)
            evidence = {"program_id": program["id"], "definition_hash": program["definition_hash"],
                        "policy_hash": state["policy_hash"], "checkpoint": n, "metrics": values,
                        "gates": checks, "cohorts": due[:n]}
            evidence_hash = digest(evidence)
            sealed(Path(directory) / "research/evidence" / (evidence_hash + ".json"), evidence)
            program["assessments"].append({k: v for k, v in evidence.items() if k != "cohorts"} | {"hash": evidence_hash})
            program["last_checkpoint"] = n
            if all(checks.values()):
                program["status"] = "review"
            elif n == max(rules["checkpoints"]):
                program["status"] = "rejected"
            log(state, "assessed", now, program["id"], checkpoint=n, status=program["status"], evidence_hash=evidence_hash)
            if program["status"] != "testing":
                break


def discover(state, rows, directory, now):
    rules = policy()
    if len(state["searches"]) >= rules["max_searches"] or len(state["programs"]) >= rules["max_programs"]:
        return
    if sum(p["status"] in ("testing", "review", "approved") for p in state["programs"]) >= rules["max_active"]:
        return
    if state["searches"] and now - instant(state["searches"][-1]["at"]) < timedelta(days=rules["search_interval_days"]):
        return
    for parent in list(state["programs"]):
        if parent["generation"] >= rules["max_generations"] or parent["status"] not in ("testing", "review", "approved"):
            continue
        if any(s["parent_id"] == parent["id"] for s in state["searches"]):
            continue
        own = [r for r in rows if r["trial_id"] == parent["id"] and r["due"]
               and all(r[b]["complete"] for b in ("branch", "parent", "pool")) and r["benchmark_pct"] is not None]
        if len(own) < rules["discovery_after"]:
            continue
        own = own[:rules["discovery_after"]]
        controls = [signals.feature(k) for k, v in signals.FEATURES.items() if v["family"] == "control"]
        controls += [p["expression"] for p in state["programs"] if p["market"] == parent["market"]]
        search = {"at": now.isoformat(), "parent_id": parent["id"], "market": parent["market"],
                  "kind": "exploratory_formula_search", "cohort_count": len(own),
                  "cohort_hash": digest(own), "last_label_date": max(r["exit_date"] for r in own), "candidates": []}
        qualifying = []
        for spec in list(signals.candidates(parent))[:rules["max_candidates_per_search"]]:
            duplicate = any(p["market"] == parent["market"] and signals.fingerprint(p) == signals.fingerprint(spec)
                            for p in state["programs"])
            deltas, diagnostics, signals_present = [], [], []
            for row in own:
                panel = read_sealed(Path(directory) / "research/inputs" / (row["input_id"] + ".json"))["panel"]
                chosen = signals.select(spec, panel, rules["top_n"])
                signals_present.append(bool(chosen))
                returns = {h["code"]: h["return_pct"] for h in row["pool"]["holdings"]}
                branch_return = sum(returns[h["code"]] for h in chosen) / len(chosen) if chosen else 0.0
                deltas.append(branch_return - row["branch"]["return_pct"])
                diagnostics.append({**validation.diagnostics(spec, panel, row["pool"], controls), "due": True})
            corr = validation.novelty(diagnostics)
            ic = validation.average([r["rank_ic"] for r in diagnostics])
            delta = validation.average(deltas)
            signal_rate = sum(signals_present) / len(signals_present)
            passed = (not duplicate and corr is not None and corr < rules["max_correlation"]
                      and ic is not None and ic > rules["min_discovery_ic"] and delta > 0
                      and signal_rate >= rules["min_signal_rate"])
            item = {"spec": spec, "mean_delta_pp": delta, "rank_ic": ic, "novelty": corr,
                    "signal_rate": signal_rate, "duplicate": duplicate, "qualified": passed}
            search["candidates"].append(item)
            if passed:
                qualifying.append(item)
        search["hash"] = digest(search)
        sealed(Path(directory) / "research/searches" / (search["hash"] + ".json"), {"search": search, "cohorts": own})
        state["searches"].append(search)
        if qualifying:
            best = max(qualifying, key=lambda c: c["mean_delta_pp"])
            register(state, best["spec"], parent["market"], now,
                     {"kind": "automatic_research", "search_hash": search["hash"],
                      "last_label_date": search["last_label_date"], "exploratory_delta_pp": best["mean_delta_pp"],
                      "note": "从已到期样本提出新公式；这些样本不计入本实验成绩"}, parent)
        log(state, "research_completed", now, parent["id"], search_hash=search["hash"],
            tested=len(search["candidates"]), qualified=len(qualifying))
        break


def owner_action(directory, decision, actor, program_id=None, evidence_hash=None, proposal=None, now=None):
    now = now or datetime.now(timezone.utc)
    if not actor.strip():
        raise ValueError("Owner actor required")
    state = load_state(directory)
    if decision == "start":
        if not isinstance(proposal, dict) or set(proposal) - {"name", "op_type", "hypothesis", "change", "expected", "expression", "filters", "market", "parent_id"}:
            raise ValueError("Unsupported proposal fields")
        parent = next((p for p in state["programs"] if p["id"] == proposal.get("parent_id")), None)
        if proposal.get("parent_id") and not parent:
            raise ValueError("Unknown proposal parent")
        program = register(state, proposal, proposal.get("market"), now, {"kind": "owner_proposal", "actor": actor}, parent)
        log(state, "started_by_owner", now, program["id"], actor=actor)
    elif decision in ("pause", "reject", "approve"):
        program = next((p for p in state["programs"] if p["id"] == program_id), None)
        if not program or program["status"] not in ("testing", "review", "approved"):
            raise ValueError("Program is no longer active")
        latest = program["assessments"][-1] if program["assessments"] else None
        expected = latest["hash"] if latest else program["definition_hash"]
        if evidence_hash != expected:
            raise ValueError("Owner request is stale")
        if decision == "approve":
            if program["status"] != "review" or program["engine_version"] != engine_version():
                raise ValueError("Program is not eligible for review")
            evidence = read_sealed(Path(directory) / "research/evidence" / (expected + ".json"))
            if (digest(evidence) != expected or evidence["definition_hash"] != program["definition_hash"]
                    or evidence["policy_hash"] != state["policy_hash"] or evidence["program_id"] != program_id
                    or evidence["checkpoint"] not in policy()["checkpoints"] or len(evidence["cohorts"]) != evidence["checkpoint"]
                    or any(r["definition_hash"] != program["definition_hash"] or r["trial_id"] != program_id for r in evidence["cohorts"])
                    or not all(assess(evidence["cohorts"], policy())[1].values())):
                raise ValueError("Research review evidence no longer matches")
        program["status"] = {"pause": "paused", "reject": "rejected", "approve": "approved"}[decision]
        log(state, decision, now, program["id"], actor=actor, evidence_hash=evidence_hash)
    else:
        raise ValueError("Unsupported owner decision")
    save_state(directory, state)


def run(directory=ARCHIVE_DIR, history_dir=HISTORY_DIR, output=PUBLIC_OUT, *, now=None, fetch_missing=False):
    now = now or datetime.now(timezone.utc)
    state = load_state(directory)
    initialize(state, history_dir, now)
    save_state(directory, state)
    stocks, indexes = update_prices(state, directory, history_dir, now, fetch_missing)
    quality = freeze_inputs(state, directory, stocks, now)
    save_state(directory, state)
    rows = observations(state, directory, stocks, indexes, now)
    checkpoints(state, rows, directory, now)
    discover(state, rows, directory, now)
    save_state(directory, state)
    for program in state["programs"]:
        path = Path(directory) / "research/diagnostics" / (program["id"] + ".json")
        if not path.exists():
            universe = state["universes"][program["market"]]
            diagnostic = validation.historical_diagnostic(program, universe["members"],
                validation.usable_prices(stocks, program["market"], now), program["market"], now, policy())
            sealed(path, diagnostic)
        program["historical"] = read_sealed(path)
        own = [r for r in rows if r["trial_id"] == program["id"]]
        program["latest_selection"] = own[-1]["selected"] if own else []
        program["latest_frozen_at"] = own[-1]["frozen_at"] if own else None
    save_state(directory, state)
    public_rows = [{k: v for k, v in row.items() if k not in ("selected", "control_correlations")}
                   for row in rows]
    report = {"schema_version": 1, "generated_at": now.isoformat(), "policy": policy(), "policy_hash": state["policy_hash"],
              "engine_version": engine_version(), "universes": list(state["universes"].values()),
              "features": signals.FEATURES, "quality": quality, "programs": state["programs"],
              "observations": public_rows, "events": state["events"], "searches": state["searches"],
              "review_workflow": WORKFLOW, "generator": "bounded_formula_research",
              "model_connected": False}
    write_json(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=ARCHIVE_DIR)
    parser.add_argument("--history-dir", type=Path, default=HISTORY_DIR)
    parser.add_argument("--output", type=Path, default=PUBLIC_OUT)
    parser.add_argument("--fetch-missing", action="store_true")
    parser.add_argument("--action-env", action="store_true")
    args = parser.parse_args()
    if args.action_env:
        import os
        raw = os.environ.get("RESEARCH_PROPOSAL", "").strip()
        if len(raw) > 16000:
            raise ValueError("Proposal too large")
        owner_action(args.archive_dir, os.environ.get("RESEARCH_DECISION", ""), os.environ.get("RESEARCH_ACTOR", ""),
                     os.environ.get("RESEARCH_PROGRAM"), os.environ.get("RESEARCH_EVIDENCE"), json.loads(raw) if raw else None)
    run(args.archive_dir, args.history_dir, args.output, fetch_missing=args.fetch_missing)


if __name__ == "__main__":
    main()
