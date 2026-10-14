# -*- coding: utf-8 -*-
"""校验 screener/factor_rank.py 的因子实现与原文参考实现逐位一致。

对同一批真实 K 线，比较 factor_rank.calculate_factors（新，用于选股二次筛）
与 ref_rotation.calculate_factors（已与 TS 轮动引擎交叉验证过 5e-13）的输出。

用法：python scripts/verify_factor_rank.py
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from screener import factor_rank                      # noqa: E402
from scripts import ref_rotation                      # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import pandas as pd

    checked = 0
    max_err = {"bias": 0.0, "slope": 0.0, "efficiency": 0.0}
    for mkt in ("us", "hk"):
        p = os.path.join(ROOT, "portfolio-board", "public", "data", "history", f"{mkt}.json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        for s in d["stocks"][:40]:          # 抽样 40 只
            bars = s["bars"]
            if len(bars) < 60:
                continue
            a = factor_rank.calculate_factors(bars)
            df = pd.DataFrame(bars, columns=["date", "open", "high", "low", "close", "volume"])
            b = ref_rotation.calculate_factors(df)
            if a is None or b is None:
                assert a is None and b is None, f"{s['code']} 一方为 None"
                continue
            for k in max_err:
                e = abs(a[k] - b[k])
                max_err[k] = max(max_err[k], e)
            checked += 1

    print(f"比较标的：{checked}")
    for k, v in max_err.items():
        print(f"  {k:<12} 最大绝对误差 {v:.3e}")
    ok = checked > 0 and all(v < 1e-9 for v in max_err.values())
    print(f"\n结果：{'PASS 与参考实现一致' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())