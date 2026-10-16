"""Explicit per-market parameter resolution; no historical-return tuning."""
import json
from pathlib import Path

RULES_PATH = Path(__file__).with_name("market_rules.json")


def market_parameters(meta):
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    configured = rules["strategies"].get(meta["id"], {})
    overrides = meta.get("market_params", {})
    return rules["version"], {
        market: {**meta.get("params", {}), **configured.get(market, {}), **overrides.get(market, {})}
        for market in meta.get("markets", ["US", "HK"])
    }
