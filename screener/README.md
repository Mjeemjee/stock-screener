# 选股引擎与策略库

本目录是选股网站的核心：**引擎负责取数和调度，策略库里的每个文件就是一个可独立进化的选股策略**。

## 目录结构

```
screener/
├─ cloud_engine.py      # 云端版引擎：HKEX + NASDAQ + 腾讯快照，无需密钥，GitHub Actions 可跑
├─ engine.py            # 本机版引擎：富途 OpenD（需本机 OpenD 启动并登录）
├─ common.py            # 两版共用的清洗/策略发现/序列化
├─ factor_rank.py       # 三因子二次筛（方案 B）：对初筛命中名单做横截面重排序
├─ strategies/          # 策略库：一个文件 = 一个策略，引擎自动发现
│  ├─ momentum_breakout.py     # 动量突破（52周新高）
│  ├─ value_dividend.py        # 低估值高股息（仅本机版产出，云端缺 PB/股息率源）
│  └─ oversold_watch.py        # 超跌观察名单
└─ README.md            # 本文件
```

## 策略模块规范（新增策略必须遵守）

每个策略文件必须提供两个顶层对象：

```python
META = {
    "id": "strategy_snake_case",   # 与文件名一致
    "name": "策略中文名",
    "principle": "策略原理（为什么有效、逻辑链条）",
    "source": "策略来源（书籍/研报/某次讨论，可溯源）",
    "markets": ["US", "HK"],        # 适用市场
    "status": "active",             # active=启用 / watch=观察中 / paused=暂停
    "params": {"pe_max": 15},       # 可调参数（引擎原样透传给 run）
    "risk": "主要风险提示",
    "cloud_note": "云端版差异说明",  # 可选：云端数据源缺字段时的行为说明
}

def run(df, params):
    """df: 全市场快照 DataFrame（已做基础清洗和流动性过滤）。
    返回：命中该策略的行（df 的子集 + 附加 'reason' 列说明命中原因），按重要度排序。
    注意防御式编程：云端版缺少 pb_ratio/dividend_ratio_ttm/turnover_rate 字段（全 NaN），
    用到这些字段前必须检查 `df[col].notna().any()`，缺失时优雅降级或返回空。
    """
```

## 新策略入库流程（策略进化机制）

1. 用户提出有意思的策略（一句话、一篇文章、一个研报观点均可）。
2. AI 分析适用性：数据可得性（云端/本机字段是否够）、美股/港股的市场结构差异、策略失效场景。
3. 写成 `strategies/<id>.py` 模块，`status` 先标 `watch`（观察中）。
4. 跑 `python -m screener.cloud_engine` 验证输出合理性。
5. 网站「策略库」页展示全部策略（含观察中），用户确认后调为 `active`。

## 三因子二次筛（factor_rank）

初筛策略（动量/超跌/低估值）只基于单日快照，无法刻画"趋势质量"。`factor_rank.py`
对初筛命中名单拉历史 K 线，用聚宽 81505 的三因子（bias 偏移动量 / slope×R² 趋势
质量 / efficiency 价格效率比）做横截面 Z-Score 加权（0.3/0.3/0.4），把命中标的
按"趋势越干净越靠前"重排序。**它不改变命中名单，只改变排序**——这是方案 B 的核心。

有效性：`scripts/factor_ic_check.py` 在 547 只个股（2023-12~2026-10）上实测复合
因子 N=20 的 Rank IC 0.0385（>0.03 有效阈值）、ICIR 0.285、t=6.96。但 N=5 时 IC
仅 0.011，说明它是**中期（约 20 交易日）排序工具**，不是短线择时信号。

输出：每个命中标的附带 `factor_score / factor_rank / factor_note` 字段；`results`
顶层附带 `factor_rank` 摘要。取数失败不影响选股结果（因子缺失的标的置底）。

## 数据说明

- 云端版：港交所官方证券列表（港股宇宙）+ NASDAQ screener（美股宇宙）+ 腾讯 qt.gtimg.cn 批量快照。
- 本机版：富途 OpenAPI 全市场快照（字段更全：PB/股息率/换手率/振幅）。
- 流动性预过滤：价格 ≥ 1（美元/港币）、当日成交额 > 0，避免仙股/停牌股进入策略。
- 输出：`data/screener_results.json`，云端由 GitHub Actions 每日生成并部署。
