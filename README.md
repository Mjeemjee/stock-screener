# 港美股选股台（stock-screener）

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
| 低估值高股息 | 启用（仅本机版） | Fama-French 价值因子 + 红利因子；云端缺 PB/股息率数据源 |

## 本地运行

```bash
pip install -r requirements-cloud.txt
python -m screener.cloud_engine          # 生成 data/screener_results.json
cd portfolio-board && npm install && npm run dev
```

## 添加新策略

在 `screener/strategies/` 新建一个 `.py` 文件，定义 `META` 字典和 `run(df, params)` 函数即可，
引擎会自动发现。详见网站内「策略进化指南」页。

## 免责声明

筛选结果仅为量化初筛，不构成投资建议。数据来自公开免费接口，可能存在延迟或口径差异。
