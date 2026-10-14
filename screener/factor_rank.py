# -*- coding: utf-8 -*-
"""三因子二次筛（方案 B）：对初筛命中名单做横截面重排序。

定位
----
bias / slope×R² / efficiency 三因子原为 4 只 ETF 的横截面轮动设计。
直接用于全市场 9,400 只选股不可行——云端快照只有单日截面，算不出需要
25~49 根 OHLC 的因子。故本模块只对「初筛已命中的标的」拉历史 K 线做二次排序，
把三因子用在它最擅长的位置：在候选池里分辨谁的趋势更「干净」。

有效性依据（scripts/factor_ic_check.py，547 只个股 / 2023-12~2026-10）
------------------------------------------------------------------------
  因子            N=20 IC   ICIR    t值
  bias            0.0336    0.241   5.89
  slope×R²        0.0324    0.228   5.58
  efficiency      0.0311    0.215   5.25
  三因子复合       0.0385    0.285   6.96     ← 本模块使用
复合因子 IC 0.0385 高于业界 0.03 有效阈值，t=6.96 显著；但 N=5 时 IC 仅 0.011，
说明它是**中期（约 20 交易日）排序工具**，不适用于短线择时。

与轮动引擎的口径关系
--------------------
因子数学与 portfolio-board/src/backtest/threeFactors.ts 一致（同一份公式的
Python 实现，见 scripts/ref_rotation.py 的 calculate_factors）。
差异：本模块在每个交易日对候选池做横截面 Z-Score 后加权，取**最后一日**的分数排序。
"""
import time

import numpy as np

BIAS_N = 25
MOM_N = 25
SLOPE_N = 25
EFF_N = 25
HISTORY_N = BIAS_N + MOM_N - 1          # 49
FACTOR_WEIGHTS = {"bias": 0.3, "slope": 0.3, "efficiency": 0.4}

# 二次筛上限：控制云端耗时（单标的请求间隔 0.15s）
MAX_CODES = 150
# 横截面样本数下限：太少则 Z-Score 无意义
MIN_CODES = 20
SLEEP = 0.15


def _slope_and_r2(y):
    y = np.asarray(y, dtype=float)
    if not np.isfinite(y).all():
        return np.nan, np.nan
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    total = np.sum((y - y.mean()) ** 2)
    resid = np.sum((y - (slope * x + intercept)) ** 2)
    return float(slope), float(1 - resid / total) if total > 0 else 1.0


def calculate_factors(bars):
    """bars: [[date,o,h,l,c,v], ...] 升序。返回三因子 dict 或 None。

    与聚宽原文 81505 的 calculate_factors 逐字一致（仅取最后一日）。
    """
    if bars is None or len(bars) < HISTORY_N:
        return None
    arr = np.asarray(bars[-HISTORY_N:], dtype=float)
    o, h, l, c = arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4]
    if not (np.isfinite(arr[:, 1:5]).all() and (arr[:, 1:5] > 0).all()):
        return None

    # bias：close/MA(25) 最近 25 天归一化序列的斜率
    ma = np.convolve(c, np.ones(BIAS_N) / BIAS_N, mode="valid")   # 长度 25
    bias = c[BIAS_N - 1:] / ma
    recent = bias[-MOM_N:]
    if recent[0] == 0:
        return None
    bias_slope, _ = _slope_and_r2(recent / recent[0])

    # slope × R²
    prices = c[-SLOPE_N:]
    slope, r2 = _slope_and_r2(prices / prices[0])

    # efficiency（Kaufman 变体）
    pivot = ((o + h + l + c) / 4.0)[-EFF_N:]
    log_pivot = np.log(pivot)
    net_move = float(log_pivot[-1] - log_pivot[0])
    path = float(np.abs(np.diff(log_pivot)).sum())
    efficiency = (100 * net_move * abs(net_move) / path) if path > 0 else 0.0

    if not (np.isfinite(bias_slope) and np.isfinite(slope) and np.isfinite(r2)):
        return None
    return {"bias": 10000 * bias_slope, "slope": 10000 * slope * r2,
            "efficiency": efficiency}


def score_candidates(raw, weights=FACTOR_WEIGHTS):
    """横截面 Z-Score（总体标准差 ddof=0）后加权求和。"""
    codes = list(raw)
    if len(codes) < MIN_CODES:
        return {}
    keys = list(weights)
    table = np.array([[raw[c][k] for k in keys] for c in codes], dtype=float)
    mean = table.mean(axis=0)
    std = table.std(axis=0, ddof=0)
    std[std == 0] = np.nan
    z = (table - mean) / std
    z = np.nan_to_num(z, nan=0.0)
    combo = z @ np.array([weights[k] for k in keys], dtype=float)
    return {c: float(s) for c, s in zip(codes, combo)}


def _fetch_bars(code, market):
    """按市场选择取数器（复用 history_fetch 的免费源）。"""
    from screener import history_fetch as hf

    if market == "HK":
        return hf.hk_bars(code)
    return hf.us_bars(code)


def rerank(results, *, max_codes=MAX_CODES, sleep=SLEEP, log=print):
    """对策略命中结果做三因子二次筛（原地修改 results）。

    results: cloud_engine 的 [{"meta":..., "hits":[...]}, ...]
    为每个 hit 附加 factor_score / factor_rank；把能算出因子的 hit 按分数降序置顶。
    返回统计摘要 dict。
    """
    t0 = time.time()
    # 1) 收集去重后的候选代码（按各策略命中顺序，保持稳定性）
    ordered = []
    seen = set()
    for r in results:
        for h in r["hits"]:
            code = h.get("code")
            if code and code not in seen:
                seen.add(code)
                ordered.append(code)
    if not ordered:
        return {"applied": False, "reason": "无候选标的"}

    candidates = ordered[:max_codes]
    log(f"[factor] 候选 {len(ordered)} 只，取前 {len(candidates)} 只拉历史K线")

    # 2) 拉历史 K 线并算因子
    raw, failures = {}, 0
    for i, code in enumerate(candidates):
        market = code.split(".")[0]
        try:
            bars = _fetch_bars(code, market)
        except Exception:
            bars = None
        f = calculate_factors(bars) if bars else None
        if f:
            raw[code] = f
        else:
            failures += 1
        if (i + 1) % 25 == 0:
            log(f"[factor] {i+1}/{len(candidates)}（成功 {len(raw)}，"
                f"耗时 {time.time()-t0:.0f}s）")
        time.sleep(sleep)

    # 3) 横截面打分
    scores = score_candidates(raw)
    if not scores:
        log(f"[factor] 有效样本 {len(raw)} 只 < {MIN_CODES}，跳过二次筛")
        return {"applied": False, "fetched": len(raw), "failures": failures,
                "reason": f"有效样本不足（{len(raw)} < {MIN_CODES}）"}

    # 4) 回填分数 + 重排序（无分数者置底）
    ranked = sorted(scores, key=lambda c: scores[c], reverse=True)
    rank_of = {c: i + 1 for i, c in enumerate(ranked)}
    total = len(ranked)
    for r in results:
        for h in r["hits"]:
            c = h.get("code")
            if c in scores:
                h["factor_score"] = round(scores[c], 4)
                h["factor_rank"] = rank_of[c]
                h["factor_note"] = (
                    f"三因子 #{rank_of[c]}/{total}（分 {scores[c]:.2f}）"
                    f"｜bias {raw[c]['bias']:.1f} · slope×R² {raw[c]['slope']:.1f}"
                    f" · eff {raw[c]['efficiency']:.1f}"
                )
        r["hits"].sort(key=lambda h: h.get("factor_rank", 10**9))

    summary = {"applied": True, "fetched": len(raw), "failures": failures,
               "ranked": total, "elapsed_sec": round(time.time() - t0, 1)}
    log(f"[factor] 二次筛完成：{total} 只排名，失败 {failures}，"
        f"耗时 {summary['elapsed_sec']}s")
    return summary