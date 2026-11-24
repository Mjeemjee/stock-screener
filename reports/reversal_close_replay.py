"""Replay the single 2026-11-24 HK reversal filter on its original archive ZIP."""
import argparse
from copy import deepcopy
import hashlib
import json
from math import isclose
from statistics import mean
from zipfile import ZipFile

from screener import factor_research as research, research_signals as signals
from screener.research_lab import reprice
from screener.research_review import complete
from screener.risk import exchange_calendar


ARCHIVE_SHA = "8a2a3d793002670846129ca72c514a212034e7cbca593f11227bf181a3f246cd"
PARENT = "factor_db7969eafdce83f7"


def sealed(archive, name):
    record = json.loads(archive.read(name))
    if research.digest(record["payload"]) != record["hash"]:
        raise ValueError("Evidence integrity mismatch: " + name)
    return record["payload"]


def replay(archive, state):
    program = next(p for p in state["programs"] if p["id"] == PARENT)
    rules = research.policy()
    if (program["engine_version"] != research.engine_version()
            or state["policy_hash"] != research.digest(rules)
            or program["definition_hash"] != research.digest({k: program[k] for k in research.CORE})):
        raise ValueError("Baseline engine, policy or definition does not match the archive")
    child = deepcopy(program)
    child["filters"].append({"feature": "close_location", "gte": 0.5})
    dates = set()
    rows = []
    for name in sorted(archive.namelist()):
        if not name.startswith("research/settled/" + PARENT + "_") or not name.endswith(".json"):
            continue
        row = sealed(archive, name)
        if row["trial_id"] != PARENT or row["definition_hash"] != program["definition_hash"]:
            raise ValueError("Not the frozen parent: " + name)
        if not complete(row):
            continue
        entry = row["entry_date"]
        frame = sealed(archive, "research/inputs/" + row["input_id"] + ".json")
        frozen = research.instant(frame["frozen_at"])
        if (entry in dates or frame["universe_hash"] != program["universe_hash"]
                or frame["id"] != row["input_id"]
                or frozen.replace(microsecond=0) != research.instant(row["frozen_at"])
                or frozen >= exchange_calendar("HK").session_open(str(entry))):
            raise ValueError("Duplicate or inconsistent point-in-time input: " + name)
        dates.add(entry)
        pool = {h["code"]: h for h in row["pool"]["holdings"]}
        if len(pool) != row["pool"]["count"] or set(pool) != set(frame["panel"]):
            raise ValueError("Incomplete or duplicate reference pool: " + name)
        old, new = ([h["code"] for h in signals.select(spec, frame["panel"], rules["top_n"])]
                    for spec in (program, child))
        original = row["branch"]
        old_net = mean(pool[c]["return_pct"] for c in old) if old else 0.0
        if ([h["code"] for h in original["holdings"]] != old
                or not isclose(old_net, original["return_pct"], abs_tol=1e-6)):
            raise ValueError("Could not reproduce the frozen parent: " + name)
        basket = {"holdings": [pool[c] for c in new]}
        new_net = mean(pool[c]["return_pct"] for c in new) if new else 0.0
        stress = rules["stress_cost_bps"]
        rows.append({"entry": entry, "exit": row["exit_date"], "changed": old != new,
                     "old_count": len(old), "new_count": len(new), "index_pct": row["benchmark_pct"],
                     "old_pct": old_net, "new_pct": new_net,
                     "stress_delta_pp": reprice(basket, stress) - reprice(original, stress)})
    return sorted(rows, key=lambda r: r["entry"])


def summarize(rows):
    if not rows:
        raise ValueError("No complete pairs")
    return {"periods": len(rows), "changed": sum(r["changed"] for r in rows),
            "delta_pp": mean(r["new_pct"] - r["old_pct"] for r in rows),
            "stress_delta_pp": mean(r["stress_delta_pp"] for r in rows),
            **{f"{side}_{key}": value for side in ("old", "new") for key, value in (
                ("net_pct", mean(r[side + "_pct"] for r in rows)),
                ("excess_pp", mean(r[side + "_pct"] - r["index_pct"] for r in rows)),
                ("worst_pct", min(r[side + "_pct"] for r in rows)),
                ("cash", sum(r[side + "_count"] == 0 for r in rows)))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    args = parser.parse_args()
    with open(args.archive, "rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != ARCHIVE_SHA:
            raise ValueError("Use the original archive named in ITER_NOTE.md")
        source.seek(0)
        with ZipFile(source) as archive:
            rows = replay(archive, json.loads(archive.read("research/state.json")))
    separate = []
    for row in rows:
        if not separate or row["entry"] >= separate[-1]["exit"]:
            separate.append(row)
    print(json.dumps({"all": summarize(rows), "nonoverlap": summarize(separate),
                      "nonoverlap_entries": [r["entry"] for r in separate], "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
