# 选股引擎与策略库

## 独立长期验证（2026-10-21）

网站 `/lab/long-horizon` 展示原固定研究池的流动性与长期动量组合，以及同期纯动量、纯流动性对照。实际生成时刻冻结，下一尚未开盘的交易日入场，固定持有 21 个交易日；不回填前瞻记录，不改正式选股，不自动交易。每日刷新固定池最多 8 个标的，覆盖率不足 80% 的市场暂停创建新期次。

旧研究历史只作诊断，目前未证明组合优于两个对照。约 1 个月有首期结果；6/12/24 个非重叠期次约需半年/一年/两年。第 24 期进行预先固定的统计复核，未达标不会靠继续挑选后续样本改判。详见 `LONG_HORIZON_PROTOCOL.md`。

## 策略进化实验室

入口为网站 `/lab`。每日追踪更新后自动评估，正式选股条件不变，除非仓库所有者明确批准晋级。

- 首版只研究母策略候选内的收紧参数分支，继承原排名；不自动编写新策略源码，也不自动下单。
- 主验证周期为 5 交易日。母策略同版本积累 8 个完整到期期数后，最多派生 2 个单参数分支。
- 每个分支仅使用出生之后的新名单，与同期重新冻结的母策略按同一个入场/退出时点比较。
- 在 20/40/60 个到期期数固定评估；缺价不重分配，空信号留现金；样本不足不判成功。
- 需要覆盖率、非重叠样本、扣费超额、高成本压力、最差单期及修正后区间下界共同达标。
- 最多同时观察 6 个分支、累计 12 个试验、2 代。失败记录和关卡证据不删除；旧备份不能回滚研究预算。
- 达标为“待晋级审核”，不代表已经证明未来有效。最差单期不是账户最大回撤，实盘前仍需独立资金配置和风险评估。

审核时从页面下载申请，使用 GitHub Actions 的 `review-strategy-lab`，填入 `trial_id`、`evidence_hash` 和决定：
`pause` 可手动暂停观察；`reject` 拒绝候选；`approve` 仅在证据哈希、源码、母策略参数和门槛均匹配时，
提交对应市场的 `market_rules.json` 修改并触发新扫描。权限由 GitHub 仓库控制，公开网页没有写入凭据。
晋级写入独立的 `promotions` 配置，先对原母策略候选完整排名，再收紧条件，不改变因子计算的候选范围。
正式名单与实验继承相同的排名语义；导出的市场参数为晋级后有效条件，并保留原始初筛参数及审批证据。

完整协议与初始假设见 `LAB_EVALUATION.md`，研究规则在 `lab_policy.json`。修改规则需要显式开启新研究或迁移，不能静默清空试验预算。

手动刷新实验室报告（保留已发布的选股和追踪文件）：

```bash
python -m screener.research_lab --report-only
```

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

## 因子研究实验室（第二版）

入口 `/lab/research`，与原有参数分支实验独立保存。初始研究为放量突破、
波动收缩突破和短期反转，各自独立研究美股、港股，共六项。每个市场固定
40 只流动性历史池股票；缺失成员不会被偷偷替换。研究不是全市场回测。

每日扫描完成后运行 `python -m screener.factor_research --fetch-missing`：
保存已完成交易日的行情和因子输入，记录新信号，更新五交易日结果。行情
不足或过期时暂停新信号，不追补过去的选股决定。净收益扣除单边 15bp，
另做单边 30bp 压力检查，并与同期固定股票池、父策略和市场指数比较。

某项研究有 20 期完整结果后，最多每七天启动一次受限公式搜索，尝试加入
新的因子或交互项。所有候选（含失败者）留档；通过探索检查的候选启动
新的前瞻实验，历史探索成绩不计入其验收。累计最多六次搜索、18 项研究。
20/40/60 期固定关卡同时检查成本、覆盖率、独立区间、相关性和统计下界，
不是按短期收益排名自动晋升。完整协议见 `FACTOR_RESEARCH.md`。

网页可构建、保存、导入和导出研究提案。启动、暂停、拒绝和审核通过由仓库
所有者在 GitHub Actions 的 `review-factor-research` 工作流执行；提交页面
下载的研究 ID、证据哈希或提案 JSON。审核通过仅标记纸面研究，不替换正式
选股、不下单。自动公式搜索继续运行；可选 DeepSeek Flash 提案助手只生成
待人工审核的提案，绝不执行模型生成的代码。

### DeepSeek Flash 接入

在仓库 Settings > Secrets and variables > Actions 中添加 `DEEPSEEK_API_KEY`。
不要提交密钥文件或放入前端环境变量。手动运行 `publish-verified-site` 后，
网站会显示真实连接状态；认证失败、模型不可用与未配置密钥会分别显示。
这里的“连接已验证”只表示模型列表接口验证成功，不代表已完成付费推理。

每日跟踪后运行 `python -m screener.deepseek_research --generate`。某项研究
有 20 期完整配对结果时，最多每七天调用一次，一项母策略最多一轮，累计
六轮。每轮最多两次请求、每次最多 4,096 输出 token（含思考）、最多三个
提案。调用前冻结额度，失败或中断也计数，防止重跑重复收费。请求数量和
token 有上限，但不承诺固定金额；供应商价格、重试会影响账单。

模型仅接收因子定义、母策略和已完成收益摘要，不发送持仓、账户或密钥。
模型输出经过公式、字段、重复性校验后在“研究提案”显示；收益仍未验证。
下载提案后通过 `review-factor-research` 的 `start` 操作启动新实验，再按
原有规则跟踪。云端累计档案 `research/ai_requests/` 保存请求和结果证据。
无密钥或服务故障时，原有公式搜索、选股及跟踪不受影响。

累计证据保存在 `screening_archive/research/` 并随云端累计备份恢复。修改
引擎会暂停受影响的实验；策略定义、池成员和研究预算不能静默重置。
历史诊断使用当前股票池和复权行情，有幸存者及修订偏差，不能证明未来收益。

## 数据来源

- 云端版：港交所官方证券列表（港股宇宙）+ NASDAQ screener（美股宇宙）+ 腾讯 qt.gtimg.cn 批量快照。
- 本机版：富途 OpenAPI 全市场快照（字段更全：PB/股息率/换手率/振幅）。
- 流动性预过滤：价格 ≥ 1（美元/港币）、当日成交额 > 0，避免仙股/停牌股进入策略。
- 输出：`data/screener_results.json`，云端由 GitHub Actions 每日生成并部署。
