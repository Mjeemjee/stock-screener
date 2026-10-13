# -*- coding: utf-8 -*-
"""聚宽文章 81505 轮动逻辑的参考实现（逐字对齐原文），用于与 TS 轮动引擎交叉验证。

只做「打分 + 选挑战者」，不做撮合（撮合差异见 rotation.ts 注释）。
输出 JSON：{date: {scores:{code:score}, challenger:code}}，供 Node 端逐日比对。

用法：python scripts/ref_rotation.py > ref_scores.json
"""
import json
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

BIAS_N = 25
MOMENTUM_DAY = 25
SLOPE_N = 25
EFFICIENCY_N = 25
HISTORY_N = BIAS_N + MOMENTUM_DAY - 1
FACTOR_WEIGHTS = {"bias": 0.3, "slope": 0.3, "efficiency": 0.4}


def _slope_and_r2(values):
    y = np.asarray(values, dtype=float)
    if not np.isfinite(y).all():
        return np.nan, np.nan
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    total = np.sum((y - y.mean()) ** 2)
    residual = np.sum((y - (slope * x + intercept)) ** 2)
    return float(slope), float(1 - residual / total) if total > 0 else 1.0


def calculate_factors(frame):
    if len(frame) < HISTORY_N:
        return None
    frame = frame.iloc[-HISTORY_N:]
    if frame[["open", "high", "low", "close"]].isna().any().any():
        return None
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        return None
    close = frame["close"].astype(float)
    bias = close / close.rolling(BIAS_N, min_periods=1).mean()
    recent_bias = bias.iloc[-MOMENTUM_DAY:]
    bias_slope, _ = _slope_and_r2(recent_bias.values / recent_bias.iloc[0])
    prices = close.iloc[-SLOPE_N:]
    slope, r2 = _slope_and_r2(prices.values / prices.iloc[0])
    recent = frame.iloc[-EFFICIENCY_N:]
    pivot = recent[["open", "high", "low", "close"]].mean(axis=1).astype(float)
    log_pivot = np.log(pivot)
    net_move = float(log_pivot.iloc[-1] - log_pivot.iloc[0])
    path = float(log_pivot.diff().abs().sum())
    efficiency = (100 * net_move * abs(net_move) / path) if path > 0 else 0.0
    return {"bias": 10000 * bias_slope, "slope": 10000 * slope * r2, "efficiency": efficiency}


def score_candidates(raw, weights=FACTOR_WEIGHTS):
    if not raw:
        return {}
    table = pd.DataFrame.from_dict(raw, orient="index")
    table = table[list(weights)].replace([np.inf, -np.inf], np.nan).dropna()
    if table.empty:
        return {}
    std = table.std(axis=0, ddof=0).replace(0, np.nan)
    z = ((table - table.mean(axis=0)) / std).fillna(0.0)
    return z.mul(pd.Series(weights)).sum(axis=1).to_dict()


def main():
    data = json.load(open(f"{ROOT}/portfolio-board/public/data/history/etf.json", encoding="utf-8"))
    frames = {}
    for s in data["stocks"]:
        df = pd.DataFrame(s["bars"], columns=["date", "open", "high", "low", "close", "volume"])
        df["date"] = df["date"].astype(int)
        frames[s["code"]] = df

    # 全交易日并集
    all_dates = sorted({int(d) for s in data["stocks"] for d in [b[0] for b in s["bars"]]})
    out = {}
    for d in all_dates:
        raw = {}
        for code, df in frames.items():
            # 对应原文 rebalance() 的 `if current[code].paused: continue`
            # 当日无 K 线 = 停牌，剔除出横截面（与原策略一致）
            if d not in set(df["date"]):
                continue
            sub = df[df["date"] <= d]
            f = calculate_factors(sub)
            if f is not None:
                raw[code] = f
        scores = score_candidates(raw)
        if not scores:
            continue
        # max() 取先出现者（Python dict 保序，等于池顺序）
        order = [s["code"] for s in data["stocks"]]
        challenger = max((c for c in order if c in scores), key=lambda c: scores[c])
        out[str(d)] = {
            "scores": {k: round(float(v), 12) for k, v in scores.items()},
            "challenger": challenger,
        }
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()