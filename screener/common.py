# -*- coding: utf-8 -*-
"""选股引擎公共部件：字段定义、清洗、策略发现、结果序列化。

本模块不依赖 futu，可被本机版（engine.py）与云端版（cloud_engine.py）共用。
"""
import importlib
import json
import os
import pkgutil

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE_DIR, "data", "screener_results.json")

# 输出到网页的字段（存在才保留）
KEEP_COLS = [
    "code", "name", "last_price", "prev_close_price", "change_rate",
    "pe_ratio", "pe_ttm_ratio", "pb_ratio", "dividend_ratio_ttm",
    "highest52weeks_price", "lowest52weeks_price",
    "circular_market_val", "turnover", "turnover_rate", "volume", "amplitude",
]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """基础清洗 + 流动性预过滤 + 附加字段（两个引擎共用）"""
    df = df.copy()
    num_cols = [c for c in KEEP_COLS if c in df.columns and c not in ("code", "name")]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # 快照无 change_rate 字段时，用最新价/昨收计算（%）
    if "change_rate" not in df.columns or df["change_rate"].isna().all():
        df["change_rate"] = (df["last_price"] / df["prev_close_price"] - 1) * 100
    # 流动性预过滤：正常交易、价格 >= 1 原币、当日有成交
    df = df[(df["last_price"] >= 1) & (df["turnover"] > 0)]
    df["market"] = df["code"].str.split(".").str[0]
    by_mkt = df["market"].value_counts().to_dict()
    print(f"[clean] 过滤后分布: {by_mkt}", flush=True)
    # 距 52 周高点/低点幅度
    df["off_52w_high_pct"] = (df["last_price"] / df["highest52weeks_price"] - 1) * 100
    df["off_52w_low_pct"] = (df["last_price"] / df["lowest52weeks_price"] - 1) * 100
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


def to_records(df: pd.DataFrame, limit: int) -> list:
    cols = [c for c in KEEP_COLS + ["off_52w_high_pct", "off_52w_low_pct", "reason"] if c in df.columns]
    out = df[cols].head(limit).copy()
    out = out.astype(object).where(out.notna(), None)
    return json.loads(json.dumps(out.to_dict("records"), default=str), parse_constant=lambda _: None)


def save_payload(payload: dict, path: str = OUT) -> None:
    payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str), parse_constant=lambda _: None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"saved: {path}（耗时 {payload['elapsed_sec']}s）", flush=True)
