# -*- coding: utf-8 -*-
"""策略：超跌观察名单（逆向）

原理：均值回归——优质公司（仍盈利、大市值）跌近 52 周低点时，
悲观定价往往过度，出现逆向布局的赔率优势。
注意：这是观察名单而非买入信号，需要等待企稳/催化确认。
"""

META = {
    "id": "oversold_watch",
    "name": "超跌观察 · 逆向名单",
    "principle": "筛选「距 52 周低点很近但仍盈利的大公司」：市场可能过度悲观定价，"
    "一旦基本面没有继续恶化，估值修复的赔率可观。本质是均值回归思想的初筛，"
    "只产生观察名单，不构成买入信号。",
    "source": "De Bondt & Thaler (1985) 过度反应与均值回归；逆向投资通用框架",
    "markets": ["US", "HK"],
    "status": "watch",
    "params": {
        "near_low_pct": 12.0,      # 距 52 周低点 12% 以内
        "min_market_val": 1e10,    # 大市值（原币）：大公司暴雷概率相对低
        "require_profitable": True,
    },
    "risk": "接飞刀是逆向策略的天性：跌近低点的公司可能基本面真的在恶化。"
    "该名单只做观察，入场需另等企稳信号（放量止跌/利好催化/财报证伪悲观）。",
    "cloud_note": "云端版可用（PE/市值/52周低点均有数据源），市值口径为总市值。",
}


def run(df, params):
    p = {**META["params"], **(params or {})}
    pe = df["pe_ttm_ratio"].fillna(df["pe_ratio"])
    mask = (
        (df["off_52w_low_pct"] <= p["near_low_pct"])
        & (df["off_52w_low_pct"] >= 0)
        & (df["circular_market_val"] >= p["min_market_val"])
    )
    if p["require_profitable"]:
        mask &= pe > 0
    hits = df[mask].copy()
    hits["reason"] = hits.apply(
        lambda r: f"距52周低点仅 +{r['off_52w_low_pct']:.1f}%，市值 {r['circular_market_val']/1e9:.0f}B，仍盈利",
        axis=1,
    )
    return hits.sort_values("off_52w_low_pct", ascending=True)
