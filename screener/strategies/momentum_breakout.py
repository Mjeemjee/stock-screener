# -*- coding: utf-8 -*-
"""策略：动量突破（52 周新高）

原理：行为金融的动量效应——创出 52 周新高的股票，由于锚定效应与信息扩散缓慢，
短期倾向于延续趋势（George & Hwang, 2004, Journal of Finance：
52周高点动量显著优于传统价格动量）。在美股、港股均有大量实证支持。
"""

META = {
    "id": "momentum_breakout",
    "name": "动量突破 · 52周新高",
    "principle": "股价创/逼近 52 周新高说明上方无套牢盘，配合当日放量（换手率不低），"
    "趋势延续概率高。经典动量策略，美股实证最充分（George & Hwang 2004），"
    "港股在流动性好的大中盘标的上同样适用。",
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


def run(df, params):
    p = {**META["params"], **(params or {})}
    mask = (
        (df["off_52w_high_pct"] >= -p["near_high_pct"])
        & (df["circular_market_val"] >= p["min_market_val"])
    )
    # 换手率字段存在且非全空（本机 futu 版）→ 用换手率；否则（云端版）→ 用成交额兜底
    use_rate = "turnover_rate" in df.columns and df["turnover_rate"].notna().any()
    if use_rate:
        mask &= df["turnover_rate"] >= p["min_turnover_rate"]
    else:
        mask &= df["turnover"] >= p["min_turnover"]
    if p["only_up_day"]:
        mask &= df["change_rate"] > 0
    hits = df[mask].copy()
    if use_rate:
        hits["reason"] = hits.apply(
            lambda r: f"距52周高点 {r['off_52w_high_pct']:.1f}%，当日涨 {r['change_rate']:.1f}%，换手 {r['turnover_rate']:.1f}%",
            axis=1,
        )
    else:
        hits["reason"] = hits.apply(
            lambda r: f"距52周高点 {r['off_52w_high_pct']:.1f}%，当日涨 {r['change_rate']:.1f}%，成交额 {r['turnover']/1e6:.0f}M",
            axis=1,
        )
    return hits.sort_values(["off_52w_high_pct", "circular_market_val"], ascending=[False, False])
