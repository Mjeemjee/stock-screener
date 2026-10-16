# -*- coding: utf-8 -*-
"""策略：动量突破（52 周新高）

原理：行为金融的动量效应——创出 52 周新高的股票，由于锚定效应与信息扩散缓慢，
短期倾向于延续趋势（George & Hwang, 2004, Journal of Finance：
52周高点动量研究）。本项目的具体筛选条件及各市场适用性仍需独立验证。
"""

META = {
    "id": "momentum_breakout",
    "name": "动量突破 · 52周新高",
    "principle": "筛选接近 52 周高点、满足市值与流动性条件的股票，研究趋势延续的可能性。"
    "换手率或成交额门槛用于流动性过滤，不等于相对历史放量。"
    "具体筛选条件及港美市场适用性仍需分别验证；仅美股动量候选使用三因子辅助排序。",
    "source": "George & Hwang (2004) The 52-Week High and Momentum Investing, Journal of Finance",
    "markets": ["US", "HK"],
    "status": "active",
    "params": {
        "near_high_pct": 3.0,        # 距 52 周最高价 3% 以内视为逼近新高
        "min_market_val": 2e9,       # 流通市值下限（原币），过滤小盘噪声
        "min_turnover_rate": 0.5,    # 当日换手率下限（%）
        "min_turnover": 2e7,         # 云端兜底：无换手率字段时用成交额下限（原币）
        "only_up_day": True,         # 当日收涨
    },
    "cloud_note": "云端版无换手率字段，改用成交额 >= 2000 万原币作为流动性过滤。",
    "risk": "假突破回杀是最大风险；大盘普跌日新高股往往次日补跌。"
    "港股小盘股容易单日脉冲式新高，已用市值+换手率过滤，但仍需人工复核成交量结构。",
}


def required_fields(params):
    p = {**META["params"], **(params or {})}
    fields = ["off_52w_high_pct", "circular_market_val", ("turnover_rate", "turnover")]
    if p["only_up_day"]:
        fields.append("change_rate")
    if p.get("use_median_liquidity"):
        fields.append("median_turnover_20d")
    return fields


def run(df, params):
    p = {**META["params"], **(params or {})}
    mask = (
        (df["off_52w_high_pct"] >= -p["near_high_pct"])
        & (df["circular_market_val"] >= p["min_market_val"])
    )
    # Availability is per stock: another stock's reported rate cannot disable the fallback.
    has_rate = df["turnover_rate"].notna()
    mask &= (has_rate & (df["turnover_rate"] >= p["min_turnover_rate"])) | (
        ~has_rate & (df["turnover"] >= p["min_turnover"])
    )
    if p["only_up_day"]:
        mask &= df["change_rate"] > 0
    if p.get("use_median_liquidity"):
        mask &= df["median_turnover_20d"] >= p["min_median_turnover_20d"]
    hits = df[mask].copy()
    reasons = []
    for _, row in hits.iterrows():
        liquidity = (f"换手 {row['turnover_rate']:.1f}%" if has_rate.loc[row.name]
                     else f"成交额 {row['turnover']/1e6:.0f}M 原币")
        change = f"，当日涨跌 {row['change_rate']:.1f}%" if row["change_rate"] == row["change_rate"] else ""
        reasons.append(f"距52周高点 {row['off_52w_high_pct']:.1f}%{change}，{liquidity}")
    hits["reason"] = reasons
    return hits.sort_values(["off_52w_high_pct", "circular_market_val", "code"], ascending=[False, False, True])
