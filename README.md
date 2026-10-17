# 港美股选股台（stock-screener）

2026-10-17 新增：新增「投资方法库」六组方法、出处/规则差异/数据需求与突破简化版回测入口；新增免费港股财务补数和「低估值高股息 · 港股市值版」观察策略。该版采用港股上市股份市值，独立于本机流通市值版本，美股基本面暂未覆盖。由现有每日云端流程取数、验证并发布。

2026-10-15 新增每日完整名单归档、5/20/60 交易日效果追踪、港美独立门槛、风险详情和浏览器观察名单。使用方式与计算协议见 `screener/README.md`，公网发布验收见 `reports/PUBLIC_DEPLOYMENT_20261016.md`。

一个**零成本、免挂机**的港美股量化选股网站：GitHub Actions 每个交易日定时扫描全市场，
GitHub Pages 托管前端，打开网页即看最新筛选结果。

**在线地址**：https://mjeemjee.github.io/stock-screener/

## 原理

```
港交所官方证券列表 ──┐
NASDAQ screener API ──┼→ 腾讯 qt.gtimg.cn 批量快照 → 策略引擎 → JSON → React 网站
（约 9,500 只宇宙）   ┘   （价格/涨跌/PE/市值/52周高低）
```

- **取数**：`screener/cloud_engine.py`，全部免费公开数据源，无需任何密钥
- **策略**：`screener/strategies/`，每个策略一个文件（META 元数据 + run 函数），引擎自动发现
- **定时**：`.github/workflows/daily.yml`，每个交易日北京时间 21:22 自动扫描并重新部署
- **前端**：`portfolio-board/`，React + Vite + Tailwind + shadcn/ui

## 内置策略

| 策略 | 状态 | 原理 |
|---|---|---|
| 动量突破 · 52周新高 | 启用 | George & Hwang (2004) 52周高点动量效应 |
| 超跌观察 · 逆向名单 | 观察 | De Bondt & Thaler (1985) 均值回归 |
| 低估值高股息 | 启用（本机版） | 富途数据，按流通市值筛选 |
| 低估值高股息 · 港股市值版 | 观察（云端版） | 东方财富 PE_TTM/PB/股息与腾讯价格核对，按港股上市股份市值筛选 |

## 本地运行

2026-10-15 优化版增加搜索、市场过滤、排序、CSV 导出、重试及数据质量状态。
三因子辅助排序现在仅用于美股动量候选，其他策略及港股保留原始筛选顺序。
回测、学习等页面按需加载，选股首页不再预载完整回测图表模块。
公网验收说明见 `reports/PUBLIC_DEPLOYMENT_20261016.md`；本机策略实验输出见 `reports/factor_optimization_report.md`。

```bash
pip install -r requirements-cloud.txt
python -m screener.cloud_engine --skip-history --output portfolio-board/public/data/screener_results.json --archive-dir data/screening_archive
cd portfolio-board && npm install && npm run dev
```

## 添加新策略

在 `screener/strategies/` 新建一个 `.py` 文件，定义 `META` 字典和 `run(df, params)` 函数即可，
引擎会自动发现。详见网站内「策略进化指南」页。

## 公网发布

在 GitHub Actions 手动运行 `daily-screener`，测试通过后扫描、构建并更新既有 GitHub Pages。
初始两份公开选股档案随源码保留，后续累计档案通过 workflow artifact 恢复并备份。
构建后会检查公开数据白名单；持仓、账户行情及本地密钥不允许进入发布目录。

## 免责声明

筛选结果仅为量化初筛，不构成投资建议。数据来自公开免费接口，可能存在延迟或口径差异。
