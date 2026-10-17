# 选股引擎与策略库

## 免费港股财务补数（2026-10-17）

`free_hk_fundamentals.py` 以既有 requests 请求东方财富公开接口，完整校验分页，按官方港股普通股池匹配，再核对最新已收盘交易日的腾讯价格、港股市值/股数与股息率算术。缺失、陈旧、未来行情和不一致数据不进入价值筛选；接口失败不影响其他策略，不复用旧数据冒充新结果。无需 OpenD、API key 或新依赖。

云端将本机 `value_dividend` 替换为独立观察策略 `value_dividend_hk`：PE_TTM≤12、PB≤1.5、股息率≥5%、港股上市股份市值≥390亿港元；PE/PB需为正。市值口径与本机版不同，使用独立策略ID与归档；其他策略不变。美股 PE/PB/股息的补数尚未接入。

完整扫描使用原 `python -m screener.cloud_engine`，部署后既有定时流程自动调用；CI 同步运行方法库和公开暂存回归测试。独立、不更新追踪/不发布的源探测命令：

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.probe_free_hk_value --output reports/free_hk_probe.json
```

本机含私人数据时，不能直接把普通 dist 全目录当作发布包；使用白名单暂存并核验：

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.prepare_public_build portfolio-board/dist reports/public-release-20261017
```

港股市值口径独立于本机版；方法库中的原始理念、项目改编和数据缺口分别展示。

## 每日归档与效果追踪（2026-10-15）

两套引擎在截取展示名单前冻结全部候选到 `data/screening_archive/snapshots/`：包括实际参数、冻结时源码摘要、原市场内排序、最终市场内排序和行情/因子字段。新档只创建不覆盖，读取时核对哈希和排序注解。旧文件可导入但标记为历史导入，不参与前瞻汇总。

本地扫描并直接更新网页数据：

```powershell
.venv/Scripts/python.exe -X utf8 -m screener.cloud_engine --skip-history --output portfolio-board/public/data/screener_results.json --archive-dir data/screening_archive
.venv/Scripts/python.exe -X utf8 -m screener.tracking --sync-latest
.venv/Scripts/python.exe -X utf8 scripts/verify_tracking_delivery.py
```

完整默认扫描会刷新历史池，并按预算补充归档名单中缺失的价格；`--skip-history` 适合快速冻结最新名单。单独更新追踪及补价：

```powershell
.venv/Scripts/python.exe -X utf8 -m screener.tracking --fetch-missing
```

追踪协议：每市场原排序 Top 10 与最终排序 Top 10 等权，分别持有 5/20/60 个交易日。入场为冻结之后的第一次市场开盘，退出为 H 个交易日后的开盘；用 `exchange-calendars==4.13.2` 的 XNYS/XHKG 日历处理假日、夏令时和半日市，指数缺数据不会推迟入场。单边成本假设 15bp，指数为未扣费的价格基准。停牌无成交权重留现金；未知入场/退出价格不重分配，整个篮子不显示完整收益。同一入场日与版本只汇总最早冻结样本，重叠期间不复合为净值。

配置在 `market_rules.json`：港美门槛独立，港股初始金额按固定 7.8 HKD/USD 参考比例对齐规模，这不是最优参数或实时汇率。动量策略的 `use_median_liquidity` 默认关闭；开启时必须具备有效 20 日成交额中位数估算，否则标记数据不可用。中位数估算为日收盘价 × 成交股数，受复权和成交量口径影响。

风险字段为已完成日线计算的 20 日年化波动、最多 120 日回撤及成交额中位数；过期/不足数据不填零。行业来自可得元数据，财报日期暂无可靠源，页面明确显示缺失。

网站新增 `/tracking`、`/stock/:code` 和 `/watchlist`；观察名单仅保存在当前浏览器。展示上限仍为每策略 50 条，跨市场按各自排序交替取出，避免一个市场挤掉另一个市场。

每日工作流恢复最近累计档案，扫描后上传整份累计档案；新备份成功才清理多余同名备份，保留最近三份，每份均保留全部内部历史记录。单份 artifact 保存 90 天；长时间停跑仍需另行备份。2026-10-16 已完成首轮云端扫描和公网部署，并下载累计备份验证三份档案哈希，原两份初始档案完整保留。公网验收记录见 `reports/PUBLIC_DEPLOYMENT_20261016.md`。

方法依据：[交易日历库](https://github.com/gerrymanoim/exchange_calendars)、[HKMA 联系汇率制度](https://www.hkma.gov.hk/eng/key-functions/money/linked-exchange-rate-system/)、[GitHub artifact 文档](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)。

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

`factor_rank.py` 仅对启用中的 **美股动量突破** 候选拉历史日线，使用 bias / slope×R² /
efficiency 做横截面 Z-Score 加权（0.3/0.3/0.4）。港股、超跌观察与价值策略保留各自原始顺序。
先收集完整初筛名单，再对最多 150 个适用候选计算，最后截取每策略 50 条展示。
港股在混合名单中的位置保持不变，美股只在自身位置间重排。

历史混市场 IC 不能证明逐市场或完整选股流程有效。2026-10-14 的固定参数对照使用分市场、
次日开盘成交、20 日持有、双边费用与时间隔离验证，没有找到足够证据支持 MAD 抗极值标准化
替代默认算法。详见 `reports/factor_optimization_report.md`。历史池存在幸存者偏差，
缺少逐日初筛名单；上述实验只验证打分方法，不能证明完整选股策略的实盘收益。

输出：`factor_score / factor_rank / factor_note / factor_status / factor_as_of` 及总体覆盖率。
只使用 UTC 当日之前的完整美股日线；过期、交易日期不同、异常或不足 49 根的数据不参与打分。
有效同日样本不足 20 只时保留初筛顺序；未评分的美股在美股槽位中置后。
`winsorized_zscore` 仅是研究选项，默认仍为 `zscore`。

策略元数据区分 `execution_status=ok/unavailable/paused/error`，并提供
`hit_count/displayed_count/truncated/eligible_count/unavailable_count`。
缺失必要字段与正常零命中是不同状态；暂停策略不会执行。

快速独立扫描（跳过回测历史池刷新，不修改默认数据文件）：

```powershell
.venv/Scripts/python.exe -X utf8 -m screener.cloud_engine --skip-history --output reports/live_scan/screener_results.json
```

离线验收：

```powershell
.venv/Scripts/python.exe -m unittest discover -s screener/tests -v
python scripts/validate_factor_optimization.py --as-of 2026-10-14
python -m unittest discover -s scripts -p test_validate_factor_optimization.py
```

图表生成需要已安装 matplotlib 的 Python；本机系统 Python 具备它，项目 `.venv` 不具备。

## 数据说明

- 云端版：港交所官方证券列表（港股宇宙）+ NASDAQ screener（美股宇宙）+ 腾讯 qt.gtimg.cn 批量快照。
- 本机版：富途 OpenAPI 全市场快照（字段更全：PB/股息率/换手率/振幅）。
- 流动性预过滤：价格 ≥ 1（美元/港币）、当日成交额 > 0，避免仙股/停牌股进入策略。
- 输出：`data/screener_results.json`，云端由 GitHub Actions 每日生成并部署。
