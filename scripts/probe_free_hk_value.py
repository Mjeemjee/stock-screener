"""Cloud-ready HK source probe; writes only to the explicitly selected report file.

Run: python -m scripts.probe_free_hk_value --output reports/free_hk_probe.json
Does not publish, rebuild history, update tracking or require OpenD/credentials.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from screener.cloud_engine import fetch_hk_universe, fetch_tx_snapshots
from screener.common import clean, run_strategies
from screener.free_hk_fundamentals import enrich, cloud_strategy


def main(output):
    path = Path(output)
    root = Path(__file__).resolve().parents[1]
    target = path.resolve()
    if not target.is_relative_to(root / "reports") or target.suffix != ".json":
        raise ValueError("Probe output must be a .json file inside the project reports directory")
    universe = fetch_hk_universe()
    quotes = fetch_tx_snapshots(universe["code"].tolist())
    enriched, summary = enrich(quotes, universe["code"].tolist())
    result = run_strategies(clean(enriched), [cloud_strategy(summary)])[0]
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "scope": "standalone_source_probe_no_tracking_or_publication",
               "universe_count": len(universe), "fundamentals": summary, "strategy": result}
    # A probe must never overwrite the live site's results or immutable archives.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"output": str(target), "source_status": summary["status"],
                      "matched": summary["matched_count"], "verified": summary["verified_count"],
                      "dividend_available": summary["dividend_available_count"],
                      "hits": result["meta"]["hit_count"]}, ensure_ascii=False))
    return 0 if summary["status"] == "ok" else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    raise SystemExit(main(parser.parse_args().output))
