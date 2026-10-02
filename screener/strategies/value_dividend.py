# -*- coding: utf-8 -*-
"""策略：低估值高股息

原理：价值因子 + 红利因子复合——低 PE/PB 提供安全边际，高股息率提供现金流回报，
两者叠加在港股这种深度价值市场历史上长期跑赢（恒生高股息率指数长期跑赢恒指）。
适合作为底仓型选股，而非短线交易。
"""

META = {
    "id": "value_dividend",
    "name": "低估值高股息",
    "principle": "PE_TTM 低 + PB 低 + 股息率(TTM)高 的三重过滤，找「又便宜又愿意分钱」的公司。"
    "港股价值股折价普遍、分红文化浓，是该策略的主场；美股金融/能源/公用事业也常有命中。",
    "source": "Fama & French 价值因子；恒生高股息率指数编制思路",
    "markets": ["US", "HK"],
    "status": "active",
    "params": {
        "pe_ttm_max": 12.0,        # PE_TTM 上限（>0 保证盈利为正）
        "pb_max": 1.5,             # PB 上限
        "dividend_min": 5.0,       # 股息率 TTM 下限（%）
        "min_market_val": 5e9,     # 流通市值下限，防价值陷阱小票
    },
    "risk": "最大的坑是「价值陷阱」：高股息可能是股价暴跌造成的表象，"
    "或公司即将削减分红（如业绩下滑的地产/银行）。命中后需人工核对分红可持续性。",
    "cloud_note": "云端版（HKEX+NASDAQ+腾讯快照）没有 PB/股息率的可靠批量数据源，"
    "本策略在云端版不产出命中，仅在本机 futu 版生效。",
}


def run(df, params):
    p = {**META["params"], **(params or {})}
    # 云端数据源缺少 PB/股息率字段：直接返回空名单，不降级产出误导性结果
    if "pb_ratio" not in df.columns or not df["pb_ratio"].notna().any() \
            or "dividend_ratio_ttm" not in df.columns or not df["dividend_ratio_ttm"].notna().any():
        return df.iloc[0:0]
    pe = df["pe_ttm_ratio"].fillna(df["pe_ratio"])
    mask = (
        (pe > 0)
        & (pe <= p["pe_ttm_max"])
        & (df["pb_ratio"] > 0)
        & (df["pb_ratio"] <= p["pb_max"])
        & (df["dividend_ratio_ttm"] >= p["dividend_min"])
        & (df["circular_market_val"] >= p["min_market_val"])
    )
    hits = df[mask].copy()
    hits["reason"] = hits.apply(
        lambda r: (
            f"PE_TTM {(r['pe_ttm_ratio'] if r['pe_ttm_ratio'] == r['pe_ttm_ratio'] else r['pe_ratio']):.1f}，"
            f"PB {r['pb_ratio']:.2f}，股息率 {r['dividend_ratio_ttm']:.1f}%"
        ),
        axis=1,
    )
    return hits.sort_values("dividend_ratio_ttm", ascending=False)
