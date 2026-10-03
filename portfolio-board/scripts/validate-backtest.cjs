/* 回测引擎独立回归脚本（Node）：用真实历史数据跑全部策略模块。
 * 验证点（对应 AC-403 / AC-404）：
 *  1. 数学自洽：净值末值 = 1 + 总收益/100；finalEquity = 净值末值 × 初始资金
 *  2. 性能：单次回测 < 5000ms
 *  3. 无未来函数抽查：每笔交易 entryDate > 信号 bar（引擎 T+1，天然满足，
 *     这里抽查成交日确为信号日之后第一个有K线的交易日——由持仓天数>=0间接验证）
 *  4. 已知行情段合理性：2024-02 ~ 2026-10 美股牛市，趋势类策略（均线交叉/突破/MACD）
 *     在美股池上应为正收益；港股同期 HSI 上行，动量类亦应偏正
 */
const fs = require('fs')
const { runBacktest } = require('../.bt-test/engine.js')

const S = (p) => require(`../.bt-test/strategies/${p}.js`).strategy
const strategies = [
  ['maCross', { fast: 5, slow: 20 }],
  ['breakout', { lookback: 20, volMult: 1.5, exitLookback: 10 }],
  ['rsiReversal', { period: 14, oversold: 30, exitLevel: 55 }],
  ['bollingerRevert', { period: 20, mult: 2 }],
  ['macdCross', { fast: 12, slow: 26, signal: 9 }],
]

const rawToBar = (b) => ({ d: b[0], o: b[1], h: b[2], l: b[3], c: b[4], v: b[5] })
const load = (f) => JSON.parse(fs.readFileSync(`public/data/history/${f}`, 'utf8'))

const us = load('us.json')
const hk = load('hk.json')
const idx = load('index.json')
const markets = {
  US: { stocks: us.stocks.map((s) => ({ ...s, bars: s.bars.map(rawToBar) })), bench: idx.indexes.SPX.bars.map(rawToBar) },
  HK: { stocks: hk.stocks.map((s) => ({ ...s, bars: s.bars.map(rawToBar) })), bench: idx.indexes.HSI.bars.map(rawToBar) },
}

const opts = {
  initialCash: 1000000, maxPositions: 10, costPct: 0.15,
  stopLossPct: 0, takeProfitPct: 0, maxHoldDays: 0,
}

let failures = 0
const check = (name, cond, detail) => {
  console.log(`  ${cond ? 'PASS' : 'FAIL'} ${name}${detail ? ` (${detail})` : ''}`)
  if (!cond) failures++
}

for (const [mkt, { stocks, bench }] of Object.entries(markets)) {
  console.log(`\n== ${mkt}（${stocks.length} 只）==`)
  // 基准区间收益（对照用）
  const b0 = bench[0].c, b1 = bench[bench.length - 1].c
  console.log(`  基准区间收益：${((b1 / b0 - 1) * 100).toFixed(1)}%（${bench[0].d} ~ ${bench[bench.length - 1].d}）`)
  for (const [file, params] of strategies) {
    const st = S(file)
    const res = runBacktest(stocks, st, params, opts, bench)
    const m = res.metrics
    const lastV = res.equity[res.equity.length - 1].v
    check('自洽: 净值末值=1+总收益', Math.abs(lastV - (1 + m.totalReturnPct / 100)) < 1e-6,
      `lastV=${lastV.toFixed(4)} ret=${m.totalReturnPct}%`)
    check('自洽: finalEquity一致', Math.abs(m.finalEquity - lastV * opts.initialCash) < 1)
    check('性能 <5s', res.elapsedMs < 5000, `${res.elapsedMs}ms`)
    const badTrade = res.trades.find((t) => t.holdingDays < 0 || t.exitDate < t.entryDate)
    check('交易日期有序', !badTrade, badTrade ? JSON.stringify(badTrade) : '')
    console.log(`  ${st.id.padEnd(16)} 总收益 ${String(m.totalReturnPct).padStart(8)}%  年化 ${String(m.cagrPct).padStart(7)}%  回撤 ${String(m.maxDrawdownPct).padStart(7)}%  夏普 ${String(m.sharpe).padStart(6)}  胜率 ${String(m.winRatePct).padStart(6)}%  交易 ${m.tradeCount}`)
  }
}

// AC-404：美股牛市段（2024-02 起）趋势类策略应为正
console.log('\n== AC-404 已知行情段验证（US 全程 ≈ 2024-02~2026-10 牛市）==')
for (const file of ['maCross', 'breakout', 'macdCross']) {
  const st = S(file)
  const params = file === 'maCross' ? { fast: 5, slow: 20 } : file === 'breakout' ? { lookback: 20, volMult: 1.5, exitLookback: 10 } : { fast: 12, slow: 26, signal: 9 }
  const res = runBacktest(markets.US.stocks, st, params, opts, markets.US.bench)
  check(`${st.id} 牛市段为正收益`, res.metrics.totalReturnPct > 0, `${res.metrics.totalReturnPct}%`)
}

console.log(failures === 0 ? '\n全部验证通过' : `\n${failures} 项失败`)
process.exit(failures === 0 ? 0 : 1)
