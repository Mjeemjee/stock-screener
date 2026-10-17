# -*- coding: utf-8 -*-
"""选股引擎公共部件：字段定义、清洗、策略发现、结果序列化。

本模块不依赖 futu，可被本机版（engine.py）与云端版（cloud_engine.py）共用。
"""
import importlib
import json
import os
import pkgutil
from copy import deepcopy

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE_DIR, "data", "screener_results.json")

# 输出到网页的字段（存在才保留）
KEEP_COLS = [
    "code", "name", "last_price", "prev_close_price", "change_rate",
    "pe_ratio", "pe_ttm_ratio", "pb_ratio", "dividend_ratio_ttm",
    "highest52weeks_price", "lowest52weeks_price",
    "circular_market_val", "hk_market_val", "turnover", "turnover_rate", "volume", "amplitude",
]
EXTRA_COLS = ["sector", "industry", "quote_time", "risk_status", "risk_as_of",
              "volatility_20d_pct", "drawdown_120d_pct", "risk_window_sessions",
              "median_turnover_20d", "earnings_date", "market_cap_basis", "fundamentals_source",
              "fundamentals_fetched_at", "fundamentals_report_date", "fundamentals_quote_date",
              "fundamentals_status"]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """基础清洗 + 流动性预过滤 + 附加字段（两个引擎共用）"""
    df = df.copy()
    input_count = len(df)
    for c in ("code", "name"):
        if c not in df.columns:
            df[c] = pd.Series(index=df.index, dtype="object")
    num_cols = [c for c in KEEP_COLS if c not in ("code", "name")]
    for c in num_cols:
        df[c] = pd.to_numeric(df.get(c, float("nan")), errors="coerce")
        df[c] = df[c].replace([float("inf"), -float("inf")], float("nan"))
    df["code"] = df["code"].astype("string").str.strip()
    df = df[df["code"].str.fullmatch(r"(?:US|HK)\.[A-Za-z0-9][A-Za-z0-9.\-]*", na=False)].copy()
    duplicate_count = int(df["code"].duplicated(keep="last").sum())
    df = df.drop_duplicates("code", keep="last")
    df["name"] = df["name"].astype("string").str.strip()
    df["name"] = df["name"].where(df["name"].notna() & df["name"].ne(""), df["code"])
    for c in ("prev_close_price", "highest52weeks_price", "lowest52weeks_price", "circular_market_val"):
        df[c] = df[c].where(df[c] > 0)
    invalid_range = df["highest52weeks_price"] < df["lowest52weeks_price"]
    df.loc[invalid_range, ["highest52weeks_price", "lowest52weeks_price"]] = float("nan")
    df["turnover_rate"] = df["turnover_rate"].where(df["turnover_rate"] >= 0)
    # A missing change rate is repaired per stock, with a positive denominator.
    derived_change = (df["last_price"] / df["prev_close_price"] - 1) * 100
    df["change_rate"] = df["change_rate"].fillna(derived_change)
    # 流动性预过滤：正常交易、价格 >= 1 原币、当日有成交
    tradable = (df["last_price"] >= 1) & (df["turnover"] > 0)
    if "suspension" in df.columns:
        suspended = df["suspension"].astype("string").str.lower().isin(["true", "1", "1.0", "yes"])
        tradable &= ~suspended
    df = df[tradable].copy()
    df["market"] = df["code"].str.split(".").str[0]
    by_mkt = df["market"].value_counts().to_dict()
    print(f"[clean] 过滤后分布: {by_mkt}", flush=True)
    # 距 52 周高点/低点幅度
    df["off_52w_high_pct"] = (df["last_price"] / df["highest52weeks_price"] - 1) * 100
    df["off_52w_low_pct"] = (df["last_price"] / df["lowest52weeks_price"] - 1) * 100
    df[num_cols + ["off_52w_high_pct", "off_52w_low_pct"]] = df[
        num_cols + ["off_52w_high_pct", "off_52w_low_pct"]
    ].replace([float("inf"), -float("inf")], float("nan"))
    df.attrs["data_quality"] = {
        "snapshot_count": input_count,
        "filtered_count": int(len(df)),
        "excluded_count": input_count - int(len(df)),
        "duplicate_count": duplicate_count,
    }
    return df.reset_index(drop=True)


def load_strategies():
    """自动发现 strategies/ 下的策略模块"""
    import screener.strategies as pkg

    mods = []
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"screener.strategies.{info.name}")
        if hasattr(mod, "META") and hasattr(mod, "run"):
            mods.append(mod)
    return sorted(mods, key=lambda m: m.META["id"])


def to_records(df: pd.DataFrame, limit: int | None = None) -> list:
    cols = [c for c in KEEP_COLS + EXTRA_COLS + ["off_52w_high_pct", "off_52w_low_pct",
                             "factor_score", "factor_rank", "factor_note", "factor_status", "factor_as_of", "reason"]
            if c in df.columns]
    out = df[cols].copy() if limit is None else df[cols].head(limit).copy()
    out = out.astype(object).where(out.notna(), None)
    return json.loads(json.dumps(out.to_dict("records"), default=str), parse_constant=lambda _: None)


def run_strategies(df: pd.DataFrame, strategies=None, limit: int | None = None) -> list:
    """Run each strategy against its declared markets; retain all hits before ranking."""
    results = []
    for mod in load_strategies() if strategies is None else strategies:
        meta = deepcopy(mod.META)
        meta.update(hit_count=0, displayed_count=0, truncated=False, eligible_count=0)
        result = {"meta": meta, "hits": []}
        results.append(result)
        if meta.get("status") == "paused":
            meta["execution_status"] = "paused"
            continue
        try:
            from screener.market_policy import market_parameters
            version, policies = market_parameters(meta)
            meta["policy_version"] = version
            meta["market_params"] = policies
            source = df[df["market"].isin(meta.get("markets", ["US", "HK"]))].copy()
            frames, eligible_count, missing_fields = [], 0, set()
            for market, group in source.groupby("market", sort=False):
                params = policies.get(market, meta.get("params", {}))
                eligible = pd.Series(True, index=group.index, dtype=bool)
                requirements = mod.required_fields(params) if hasattr(mod, "required_fields") else []
                for requirement in requirements:
                    alternatives = (requirement,) if isinstance(requirement, str) else requirement
                    present = pd.Series(False, index=group.index, dtype=bool)
                    for field in alternatives:
                        if field in group.columns:
                            present |= group[field].notna()
                    eligible &= present
                    if not present.any():
                        missing_fields.add(f"{market}:" + "|".join(alternatives))
                eligible_count += int(eligible.sum())
                if eligible.any():
                    hits = mod.run(group.loc[eligible].copy(), params)
                    if hits is not None:
                        frames.append(hits.copy())
            meta["eligible_count"] = eligible_count
            meta["unavailable_count"] = len(source) - eligible_count
            meta["missing_fields"] = sorted(missing_fields)
            if not source.empty and not eligible_count:
                meta["execution_status"] = "unavailable"
                meta["data_note"] = "缺少策略所需有效字段，当前数据源无法运行此策略"
                continue
            hits = pd.concat(frames) if frames else source.iloc[0:0].copy()
            if "reason" not in hits.columns:
                hits["reason"] = "命中筛选条件"
            meta["execution_status"] = "ok"
            meta["hit_count"] = int(len(hits))
            result["hits"] = to_records(hits)
            market_ranks = {}
            for rank, hit in enumerate(result["hits"], 1):
                market = hit["code"].split(".")[0]
                market_ranks[market] = market_ranks.get(market, 0) + 1
                hit["original_rank"] = rank
                hit["original_market_rank"] = market_ranks[market]
            print(f"  - {meta['id']}: {len(hits)} 命中", flush=True)
        except Exception as exc:
            meta["execution_status"] = "error"
            meta["error"] = str(exc)
            print(f"  - {meta['id']}: 执行失败 {exc}", flush=True)
    return finalize_results(results, limit=limit)


def finalize_results(results: list, limit: int | None = 50) -> list:
    """Apply the display limit only after every candidate has been ranked."""
    for result in results:
        if limit is not None:
            # Preserve each market's ordering and visibility without comparing currencies.
            by_market = {}
            for hit in result["hits"]:
                by_market.setdefault(hit["code"].split(".")[0], []).append(hit)
            selected = []
            for rank in range(max((len(hits) for hits in by_market.values()), default=0)):
                for hits in by_market.values():
                    if rank < len(hits) and len(selected) < limit:
                        selected.append(hits[rank])
                if len(selected) >= limit:
                    break
            result["hits"] = selected
        meta = result["meta"]
        meta["displayed_count"] = len(result["hits"])
        meta["truncated"] = meta.get("hit_count", len(result["hits"])) > len(result["hits"])
    return results


def save_payload(payload: dict, path: str = OUT) -> None:
    payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str), parse_constant=lambda _: None)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"saved: {path}（耗时 {payload['elapsed_sec']}s）", flush=True)
