# 回测策略模块规范

一个文件 = 一个回测策略。放在本目录（`src/backtest/strategies/`）下，构建期自动发现（`import.meta.glob`），**新增策略不需要改动任何其他代码**。

## 最小模板

```ts
import { sma, crossUp, crossDown } from '../engine'
import type { StrategyModule } from '../types'

export const strategy: StrategyModule = {
  id: 'my-strategy',           // 唯一、小写连字符
  name: '我的策略',             // 网页下拉框显示名
  description: '原理、适用环境、主要风险，说人话。',
  params: [
    // 网页表单按此自动生成（数字输入框，带 min/max/step 约束）
    { key: 'period', label: '周期', default: 20, min: 5, max: 120, step: 1 },
  ],
  prepare(bars, p) {
    // bars: 单只股票的日K（前复权，升序），p: 用户调好的参数
    // 返回与 bars 等长的两个布尔数组：
    //   entries[i] = 第 i 根收盘出现买入信号（次一根开盘成交）
    //   exits[i]   = 第 i 根收盘出现卖出信号（次一根开盘成交）
    const closes = bars.map((b) => b.c)
    const m = sma(closes, Math.round(p.period))
    ...
    return { entries, exits }
  },
}
```

## 规则

1. **无未来函数**：`entries[i]`/`exits[i]` 只能用 ≤ i 的数据计算（用 `rollingMaxPrev` 等"不含当根"工具时自行注意口径）。
2. **纯函数**：prepare 不发起网络请求、不读全局状态；同一输入必须同一输出。
3. **参数取值**：`p[key]` 一律为 number；需要整数时自行 `Math.round`。
4. **工具函数**：`sma / ema / rsi / macd / rollingMaxPrev / rollingMinPrev / rollingStd / crossUp / crossDown` 由 `../engine` 提供，优先复用。
5. **共用交易规则**（引擎统一执行，策略不用管）：T+1 开盘成交、等权分仓、单边成本、止损/止盈/最大持有天数（用户在网页高级参数里配）。
6. 出场若只依赖策略信号不够，提示用户在高级参数里加止损——在 description 里写明。

## 入库流程

新策略文件 → `npm run build` 通过 → 回测页验证结果合理（对照已知行情段）→ 在 `releases/TEST_REPORT.md` 记录验证 → 完成。

回归验证（改动引擎或策略后建议跑）：

```bash
cd portfolio-board
npx tsc src/backtest/engine.ts src/backtest/combo.ts src/backtest/srLevels.ts src/backtest/strategies/maCross.ts \
  src/backtest/strategies/breakout.ts src/backtest/strategies/rsiReversal.ts \
  src/backtest/strategies/bollingerRevert.ts src/backtest/strategies/macdCross.ts \
  src/backtest/strategies/srBounce.ts src/backtest/strategies/srBreakout.ts \
  --outDir .bt-test --module commonjs --target es2020 --moduleResolution node --skipLibCheck
# 在 .bt-test/ 写入 {"type":"commonjs"} 的 package.json（项目根是 ESM，需要覆盖）
node scripts/validate-backtest.cjs                   # 在 portfolio-board 根目录运行
```

注意：编译列表不要包含 `strategies/index.ts`（import.meta.glob 是构建期特性，CJS 下无法编译）；`scripts/validate-backtest.cjs` 顶部的 strategies 数组是手维护的，新增策略后把模块名+默认参数加进去。
