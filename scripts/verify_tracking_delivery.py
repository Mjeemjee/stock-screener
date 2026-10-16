"""Audit the currently published local snapshot against immutable full archives."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from screener.risk import session_open  # noqa: E402
from screener.tracking import instant, read_archives, write_json  # noqa: E402


def main():
    records = read_archives()
    prospective = [record for record in records if record["provenance"] == "prospective"]
    assert prospective, "No prospective archive exists"
    record = prospective[-1]
    current = json.loads((ROOT / "portfolio-board/public/data/screener_results.json").read_text(encoding="utf-8"))
    tracking = json.loads((ROOT / "portfolio-board/public/data/tracking.json").read_text(encoding="utf-8"))
    assert current["archive_id"] == record["id"]
    assert record["complete_candidates"]
    full = {result["meta"]["id"]: result for result in record["payload"]["strategies"]}
    for result in current["strategies"]:
        archived = full[result["meta"]["id"]]
        assert len(archived["hits"]) == result["meta"]["hit_count"]
        assert len(result["hits"]) <= 50
        assert len(result["hits"]) == result["meta"]["displayed_count"]
        assert {hit["code"] for hit in result["hits"]} <= {hit["code"] for hit in archived["hits"]}
        assert {hit["code"].split(".")[0] for hit in result["hits"]} == {
            hit["code"].split(".")[0] for hit in archived["hits"]}
    by_id = {entry["id"]: entry for entry in records}
    for row in tracking["evaluations"]:
        if row["scheduled_entry_date"]:
            assert session_open(row["scheduled_entry_date"], row["market"]) > instant(by_id[row["snapshot_id"]]["frozen_at"])
        if row["exit_date"] is None:
            assert not row["baskets"]["selected"]["complete"]
    assert tracking["protocol"]["version"] == 2
    assert len(tracking["archives"]) == len(records)
    result = {
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "PASS",
        "archive_count": len(records), "provenance": dict(Counter(entry["provenance"] for entry in records)),
        "latest_snapshot": record["id"], "frozen_at": record["frozen_at"],
        "candidate_count": sum(len(entry["hits"]) for entry in full.values()),
        "displayed_count": sum(len(entry["hits"]) for entry in current["strategies"]),
        "per_strategy": {key: {"candidates": len(value["hits"]),
                               "markets": dict(Counter(hit["code"].split(".")[0] for hit in value["hits"]))}
                         for key, value in full.items()},
        "tracking_rows": len(tracking["evaluations"]),
        "matured_pairs": sum(row["matured_pairs"] for row in tracking["summary"]),
        "calendar": tracking["protocol"]["calendar"],
        "checks": ["archive hashes and ranking annotations", "full-before-display candidates",
                   "per-market display coverage", "entry strictly after freeze", "pending not matured",
                   "calendar protocol and archive index agreement"],
    }
    write_json(ROOT / "reports/tracking_delivery.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
