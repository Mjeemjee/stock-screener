# -*- coding: utf-8 -*-
"""factor_rank 测试：分两层，避免把「打分逻辑」与「网络取数」混在一起验。

A. 确定性单测（无网络）：用固定合成数据校验 calculate_factors / score_candidates
   的数学与排名逻辑，逐位对比手工实现。
B. 联网端到端（可跳过）：用线上真实扫描结果跑二次筛，只校验结构与排序行为
   （不对比具体分数——网络源回退会改变复权口径，分数不可复现）。

用法：python scripts/test_factor_rank_e2e.py [--offline]
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from screener import factor_rank   # noqa: E402

FAIL = 0


def check(name, cond, detail=""):
    global FAIL
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" ({detail})" if detail else ""))
    if not cond:
        FAIL += 1


def synth_bars(seed, n=60, trend=0.0):
    """确定性合成 K 线：固定随机种子 + 给定趋势漂移。"""
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(trend, 0.012, n))
    high = close * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, n)))
    openp = low + (high - low) * rng.random(n)
    vol = (rng.random(n) * 1e6 + 1e5).astype(int)
    dates = np.arange(20240101, 20240101 + n)
    return [[int(d), float(o), float(h), float(l), float(c), int(v)]
            for d, o, h, l, c, v in zip(dates, openp, high, low, close, vol)]


def manual_factors(bars):
    """独立手工实现（不复用 factor_rank 内部函数）。"""
    arr = np.asarray(bars, dtype=float)
    c, o, h, l = arr[:, 4], arr[:, 1], arr[:, 2], arr[:, 3]
    n = len(c)

    def slr(y):
        x = np.arange(len(y), dtype=float)
        s, i0 = np.polyfit(x, y, 1)
        tot = np.sum((y - y.mean()) ** 2)
        res = np.sum((y - (s * x + i0)) ** 2)
        return s, (1 - res / tot if tot > 0 else 1.0)

    ma = np.array([c[i - 24:i + 1].mean() for i in range(24, n)])
    bias = c[24:] / ma
    rb = bias[-25:]
    bs, _ = slr(rb / rb[0])
    s, r2 = slr(c[-25:] / c[-25])
    piv = ((o + h + l + c) / 4)[-25:]
    lp = np.log(piv)
    net = lp[-1] - lp[0]
    path = np.abs(np.diff(lp)).sum()
    eff = 100 * net * abs(net) / path if path > 0 else 0.0
    return {"bias": 10000 * bs, "slope": 10000 * s * r2, "efficiency": eff}


def test_a_math():
    print("A. 确定性单测（因子数学 + 打分逻辑）")
    # A1 因子值逐位一致
    worst = 0.0
    for seed in range(30):
        bars = synth_bars(seed, trend=(seed % 5 - 2) * 0.001)
        got = factor_rank.calculate_factors(bars)
        exp = manual_factors(bars)
        for k in exp:
            worst = max(worst, abs(got[k] - exp[k]))
    check("calculate_factors 与手工实现一致", worst < 1e-9, f"max err {worst:.2e}")

    # A2 不足 49 根返回 None
    check("K 线不足 49 根返回 None", factor_rank.calculate_factors(synth_bars(1, n=48)) is None)

    # A3 含 0 价返回 None（必须落在窗口内：因子只看最后 49 根）
    bad = synth_bars(2)
    bad[-1][4] = 0.0
    check("含 0 价返回 None", factor_rank.calculate_factors(bad) is None)
    bad2 = synth_bars(2)
    bad2[5][4] = 0.0      # 窗口外：不应影响结果（与原实现口径一致）
    check("窗口外的 0 价不影响（只看最后49根）", factor_rank.calculate_factors(bad2) is not None)

    # A4 score_candidates 与手工 Z-Score 一致
    raw = {}
    for i in range(30):
        raw[f"S{i:02d}"] = factor_rank.calculate_factors(synth_bars(100 + i, trend=i * 0.0008))
    got = factor_rank.score_candidates(raw)
    keys = ["bias", "slope", "efficiency"]
    w = np.array([factor_rank.FACTOR_WEIGHTS[k] for k in keys])
    codes = list(raw)
    t = np.array([[raw[c][k] for k in keys] for c in codes])
    z = (t - t.mean(axis=0)) / t.std(axis=0, ddof=0)
    exp = dict(zip(codes, z @ w))
    worst = max(abs(got[c] - exp[c]) for c in codes)
    check("score_candidates 与手工 Z-Score 一致", worst < 1e-12, f"max err {worst:.2e}")

    # A5 样本不足 MIN_CODES 时返回空
    few = {c: raw[c] for c in list(raw)[:5]}
    check(f"样本 < {factor_rank.MIN_CODES} 只时返回空", factor_rank.score_candidates(few) == {})

    # A6 排名方向：趋势越强的标的分数越高
    trends = sorted(raw, key=lambda c: raw[c]["slope"], reverse=True)
    top = max(got, key=got.get)
    check("斜率最大的标的得分最高", top == trends[0], f"top={top} slope_max={trends[0]}")

    # A7 常量列不产生 NaN（std=0 保护）
    flat = {f"F{i}": {"bias": 1.0, "slope": 2.0, "efficiency": 3.0} for i in range(25)}
    out = factor_rank.score_candidates(flat)
    check("常量因子列不产生 NaN", out and all(np.isfinite(v) for v in out.values()))


def test_b_e2e():
    print("\nB. 联网端到端（真实扫描结果 → 二次筛）")
    src = os.path.join(os.environ["TEMP"], "real_results.json")
    if not os.path.exists(src):
        print(f"  [skip] 缺少 {src}，跳过")
        return
    payload = json.load(open(src, encoding="utf-8"))
    results = payload["strategies"]
    summary = factor_rank.rerank(results, max_codes=25)
    print("  摘要:", json.dumps(summary, ensure_ascii=False))
    check("二次筛已应用", bool(summary.get("applied")), str(summary.get("reason", "")))

    ok_order, ok_bottom = True, True
    for r in results:
        ranks = [h.get("factor_rank") for h in r["hits"]]
        known = [x for x in ranks if x is not None]
        if known != sorted(known):
            ok_order = False
        if known:
            i0 = ranks.index(None) if None in ranks else len(ranks)
            if any(x is not None for x in ranks[i0:]):
                ok_bottom = False
    check("hits 按 factor_rank 升序", ok_order)
    check("无分数项置底", ok_bottom)

    scored = [h for r in results for h in r["hits"] if h.get("factor_rank")]
    check("命中项带 factor_note 说明", all(h.get("factor_note") for h in scored))
    for h in sorted(scored, key=lambda x: x["factor_rank"])[:5]:
        print(f"    #{h['factor_rank']:<3} {h['code']:<12} {h['factor_note']}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    test_a_math()
    if "--offline" not in sys.argv:
        test_b_e2e()
    print(f"\n结果：{'全部通过' if FAIL == 0 else str(FAIL) + ' 项失败'}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())