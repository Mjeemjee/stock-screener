# -*- coding: utf-8 -*-
"""三因子二次筛（方案 B）：对初筛命中名单做横截面重排序。

定位
----
bias / slope×R² / efficiency 三因子原为 4 只 ETF 的横截面轮动设计。
直接用于全市场 9,400 只选股不可行——云端快照只有单日截面，算不出需要
25~49 根 OHLC 的因子。故本模块只对「初筛已命中的标的」拉历史 K 线做二次排序，
把三因子用在它最擅长的位置：在候选池里分辨谁的趋势更「干净」。

研究边界
--------
旧的混市场 IC 不能证明各市场或各初筛策略均有效。现有分市场研究对港股
缺乏支持，且存在当期股票池的幸存者偏差。默认只对美股动量名单排序；
港股与逆向/价值策略保留各自排序。抗极值标准化仅供独立验证，默认不启用。

与轮动引擎的口径关系
--------------------
因子数学与 portfolio-board/src/backtest/threeFactors.ts 一致（同一份公式的
Python 实现，见 scripts/ref_rotation.py 的 calculate_factors）。
差异：本模块在每个交易日对候选池做横截面 Z-Score 后加权，取**最后一日**的分数排序。
"""
import time
from datetime import date, datetime, timezone

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
    try:
        arr = np.asarray(bars[-HISTORY_N:], dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim != 2 or arr.shape[1] < 5:
        return None
    o, h, l, c = arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4]
    if not (np.isfinite(arr[:, 1:5]).all() and (arr[:, 1:5] > 0).all()):
        return None
    if not np.isfinite(arr[:, 0]).all() or not (np.diff(arr[:, 0]) > 0).all():
        return None
    if ((h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)).any():
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


def score_candidates(raw, weights=FACTOR_WEIGHTS, *, method="zscore"):
    """有限值横截面打分；winsorized_zscore 为固定参数的研究候选。"""
    if method not in ("zscore", "winsorized_zscore"):
        raise ValueError(f"Unknown scoring method: {method}")
    keys = list(weights)
    codes = [c for c, f in raw.items()
             if all(isinstance(f.get(k), (int, float)) and np.isfinite(f[k]) for k in keys)]
    if len(codes) < MIN_CODES:
        return {}
    table = np.array([[raw[c][k] for k in keys] for c in codes], dtype=float)
    if method == "winsorized_zscore":
        med = np.median(table, axis=0)
        spread = 3 * 1.4826 * np.median(np.abs(table - med), axis=0)
        table = np.clip(table, med - spread, med + spread)
    mean = table.mean(axis=0)
    std = table.std(axis=0, ddof=0)
    std[std == 0] = np.nan
    z = (table - mean) / std
    z = np.nan_to_num(z, nan=0.0)
    combo = z @ np.array([weights[k] for k in keys], dtype=float)
    if method == "winsorized_zscore":
        combo_std = combo.std()
        combo = (combo - combo.mean()) / combo_std if combo_std > 0 else np.zeros_like(combo)
    return {c: float(s) for c, s in zip(codes, combo)}


def _fetch_bars(code, market):
    """按市场选择取数器（复用 history_fetch 的免费源）。"""
    from screener import history_fetch as hf

    if market == "HK":
        return hf.hk_bars(code)
    return hf.us_bars(code)


def rerank(results, *, max_codes=MAX_CODES, sleep=SLEEP, log=print,
           as_of=None, fetch_bars=None, method="zscore"):
    """对策略命中结果做三因子二次筛（原地修改 results）。

    results: cloud_engine 的 [{"meta":..., "hits":[...]}, ...]
    为每个 hit 附加 factor_score / factor_rank；把能算出因子的 hit 按分数降序置顶。
    返回统计摘要 dict。
    """
    t0 = time.time()
    cutoff = date.fromisoformat(as_of) if as_of else datetime.now(timezone.utc).date()
    getter = fetch_bars or _fetch_bars
    # 1) 收集去重后的候选代码（按各策略命中顺序，保持稳定性）
    ordered = []
    seen = set()
    for r in results:
        for h in r["hits"]:
            for key in ("factor_score", "factor_rank", "factor_note", "factor_as_of"):
                h.pop(key, None)
            h["factor_status"] = "unsupported_scope"
            code = h.get("code")
            eligible = (r["meta"].get("id") == "momentum_breakout"
                        and r["meta"].get("status") == "active"
                        and code and code.startswith("US."))
            if eligible:
                h["factor_status"] = "budget_excluded"
            if eligible and code not in seen:
                seen.add(code)
                ordered.append(code)
    summary = {"applied": False, "method": method, "scope": "US momentum_breakout",
               "candidates": len(ordered), "attempted": 0, "fetched": 0,
               "failures": 0, "ranked": 0, "coverage": 0.0}
    if not ordered:
        return {**summary, "reason": "无适用的美股动量候选"}

    candidates = ordered[:max_codes]
    log(f"[factor] 候选 {len(ordered)} 只，取前 {len(candidates)} 只拉历史K线")

    # 2) 拉历史 K 线并算因子
    raw, failures, dates, statuses = {}, 0, {}, {}
    for i, code in enumerate(candidates):
        market = code.split(".")[0]
        try:
            bars = getter(code, market)
            # US 当日可能尚未收盘，只采用 UTC 日期之前的完整日线。
            bars = [b for b in (bars or []) if int(b[0]) < int(cutoff.strftime("%Y%m%d"))]
            last_date = datetime.strptime(str(int(bars[-1][0])), "%Y%m%d").date() if bars else None
            f = calculate_factors(bars)
        except Exception:
            f, last_date = None, None
        if f and last_date and (cutoff - last_date).days <= 7:
            raw[code] = f
            dates[code] = last_date
            statuses[code] = "insufficient_sample"
        else:
            failures += 1
            statuses[code] = "stale_history" if f else "history_unavailable"
        if (i + 1) % 25 == 0:
            log(f"[factor] {i+1}/{len(candidates)}（成功 {len(raw)}，"
                f"耗时 {time.time()-t0:.0f}s）")
        time.sleep(sleep)

    # 3) 横截面打分
    # 同一截面的信号必须使用同一交易日，不能将停更数据混入今天的排名。
    latest = max(dates.values()) if dates else None
    for code in list(raw):
        if dates[code] != latest:
            raw.pop(code)
            statuses[code] = "stale_history"
            failures += 1
    scores = score_candidates(raw, method=method)

    # 4) 回填分数 + 重排序（无分数者置底）
    ranked = sorted(scores, key=lambda c: scores[c], reverse=True)
    rank_of = {c: i + 1 for i, c in enumerate(ranked)}
    total = len(ranked)
    for r in results:
        for h in r["hits"]:
            c = h.get("code")
            if h["factor_status"] == "unsupported_scope":
                continue
            h["factor_status"] = statuses.get(c, "budget_excluded")
            if c in scores:
                h["factor_status"] = "ranked"
                h["factor_as_of"] = dates[c].isoformat()
                h["factor_score"] = round(scores[c], 4)
                h["factor_rank"] = rank_of[c]
                h["factor_note"] = (
                    f"三因子 #{rank_of[c]}/{total}（分 {scores[c]:.2f}）"
                    f"｜bias {raw[c]['bias']:.1f} · slope×R² {raw[c]['slope']:.1f}"
                    f" · eff {raw[c]['efficiency']:.1f}"
                )
        # 只重排 US 槽位，港股原有相对顺序及位置均保留。
        slots = [i for i, h in enumerate(r["hits"]) if h["factor_status"] != "unsupported_scope"]
        ranked_hits = sorted((r["hits"][i] for i in slots), key=lambda h: h.get("factor_rank", 10**9))
        for i, h in zip(slots, ranked_hits):
            r["hits"][i] = h

    summary.update({"applied": bool(scores), "attempted": len(candidates),
                    "fetched": len(raw), "failures": failures, "ranked": total,
                    "coverage": round(total / len(ordered), 4),
                    "elapsed_sec": round(time.time() - t0, 1)})
    if not scores:
        summary["reason"] = f"同日有效样本不足（{len(raw)} < {MIN_CODES}），保留初筛顺序"
    log(f"[factor] 二次筛完成：{total} 只排名，失败 {failures}，"
        f"耗时 {summary['elapsed_sec']}s")
    return summary
