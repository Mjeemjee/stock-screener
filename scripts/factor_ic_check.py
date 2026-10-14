# -*- coding: utf-8 -*-
"""三因子在个股横截面上的选股能力检验（IC 分析）。

背景：bias / slope×R² / efficiency 三因子原设计用于 4 只 ETF 的横截面轮动。
方案 B 想把它们用作个股选股的一次筛，但必须先验证：
在个股横截面上，因子值高低是否与未来收益相关？

方法（标准因子检验）：
  1. 对每个交易日 t，用截至 t 的 OHLC 计算每只股票的三因子值；
  2. 计算 t → t+N 的前向收益（N = 5 / 10 / 20 交易日）；
  3. 每个交易日做横截面 Spearman 秩相关（Rank IC）；
  4. 汇总：IC 均值、IC 标准差、ICIR = 均值/标准差、t 统计量、胜率。

判据（业界惯例）：
  |IC 均值| > 0.03 视为有效；ICIR > 0.3 为可接受；t > 2 为统计显著。

用法：python scripts/factor_ic_check.py
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "portfolio-board", "public", "data", "history")

BIAS_N = 25
MOM_N = 25
SLOPE_N = 25
EFF_N = 25
HISTORY_N = BIAS_N + MOM_N - 1   # 49
FACTOR_WEIGHTS = {"bias": 0.3, "slope": 0.3, "efficiency": 0.4}


def _slope_and_r2(y: np.ndarray):
    if not np.isfinite(y).all():
        return np.nan, np.nan
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    total = np.sum((y - y.mean()) ** 2)
    resid = np.sum((y - (slope * x + intercept)) ** 2)
    return float(slope), float(1 - resid / total) if total > 0 else 1.0


def factors_at(bars: np.ndarray):
    """bars: (T,6) [date,o,h,l,c,v]，返回三因子或 None。逐日滚动计算。"""
    close = bars[:, 4].astype(float)
    o, h, l = bars[:, 1].astype(float), bars[:, 2].astype(float), bars[:, 3].astype(float)
    n = len(close)
    out = np.full((n, 3), np.nan)
    for i in range(HISTORY_N - 1, n):
        w = slice(i - HISTORY_N + 1, i + 1)
        c = close[w]
        if not np.isfinite(c).all() or (c <= 0).any():
            continue
        # bias: close/MA(25) 最近 25 天归一化后的斜率
        ma = pd.Series(c).rolling(BIAS_N, min_periods=BIAS_N).mean().values
        bias = c / ma
        rb = bias[-MOM_N:]
        if not np.isfinite(rb).all() or rb[0] == 0:
            continue
        bs, _ = _slope_and_r2(rb / rb[0])
        # slope x r2
        p = c[-SLOPE_N:]
        s, r2 = _slope_and_r2(p / p[0])
        # efficiency
        pivot = ((o[w] + h[w] + l[w] + c) / 4.0)[-EFF_N:]
        lp = np.log(pivot)
        net = lp[-1] - lp[0]
        path = np.abs(np.diff(lp)).sum()
        eff = 100 * net * abs(net) / path if path > 0 else 0.0
        if np.isfinite(bs) and np.isfinite(s) and np.isfinite(r2):
            out[i] = [10000 * bs, 10000 * s * r2, eff]
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # 汇总所有股票：date -> {code: [f1,f2,f3]}, 以及 date -> {code: close}
    frames = []
    for mkt in ("us", "hk"):
        p = os.path.join(HIST, f"{mkt}.json")
        if not os.path.exists(p):
            print(f"[warn] 缺少 {p}")
            continue
        d = json.load(open(p, encoding="utf-8"))
        for s in d["stocks"]:
            bars = np.array(s["bars"], dtype=float)
            if len(bars) < HISTORY_N + 25:
                continue
            f = factors_at(bars)
            df = pd.DataFrame(f, columns=["bias", "slope", "efficiency"])
            df["date"] = bars[:, 0].astype(int)
            df["close"] = bars[:, 4]
            df["code"] = s["code"]
            frames.append(df)
    allf = pd.concat(frames, ignore_index=True)
    allf = allf.dropna(subset=["bias", "slope", "efficiency"])
    print(f"[data] 有效因子样本 {len(allf)} 行，{allf['code'].nunique()} 只标的，"
          f"{allf['date'].min()}~{allf['date'].max()}")

    # 宽表：date x code
    def pivot(col):
        return allf.pivot_table(index="date", columns="code", values=col)

    facs = {k: pivot(k) for k in ("bias", "slope", "efficiency")}
    close = pivot("close")
    # 复合分：三因子各自横截面 Z-Score 后加权
    zs = {}
    for k, w in FACTOR_WEIGHTS.items():
        v = facs[k]
        zs[k] = (v - v.mean(axis=1).values[:, None]) / v.std(axis=1, ddof=0).values[:, None]
    combo = sum(FACTOR_WEIGHTS[k] * zs[k] for k in FACTOR_WEIGHTS)

    print(f"\n{'因子':<12}{'N':>4}{'IC均值':>10}{'IC标准差':>11}{'ICIR':>9}{'t值':>8}{'IC>0占比':>10}{'样本日':>8}")
    print("-" * 74)
    for name, mat in [("bias", facs["bias"]), ("slope×R²", facs["slope"]),
                      ("efficiency", facs["efficiency"]), ("三因子复合", combo)]:
        for N in (5, 10, 20):
            fwd = close.shift(-N) / close - 1
            ics = []
            for d in mat.index:
                if d not in fwd.index:
                    continue
                a = mat.loc[d].dropna()
                b = fwd.loc[d].dropna()
                common = a.index.intersection(b.index)
                if len(common) < 20:
                    continue
                r = pd.Series(a[common]).rank().corr(pd.Series(b[common]).rank())
                if np.isfinite(r):
                    ics.append(r)
            if len(ics) < 5:
                continue
            ics = np.array(ics)
            ic, sd = ics.mean(), ics.std(ddof=1)
            icir = ic / sd if sd > 0 else 0
            t = icir * math.sqrt(len(ics))
            print(f"{name:<12}{N:>4}{ic:>10.4f}{sd:>11.4f}{icir:>9.3f}{t:>8.2f}"
                  f"{(ics > 0).mean():>10.1%}{len(ics):>8}")


if __name__ == "__main__":
    main()