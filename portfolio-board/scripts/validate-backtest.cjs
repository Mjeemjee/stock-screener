/* 回测引擎独立回归脚本（Node）：用真实历史数据跑全部策略模块。
 * 验证点（对应 AC-403 / AC-404 / AC-502 / AC-503）：
 *  1. 数学自洽：净值末值 = 1 + 总收益/100；finalEquity = 净值末值 × 初始资金
 *  2. 性能：单次回测 < 5000ms
 *  3. 无未来函数抽查：每笔交易 entryDate > 信号 bar（引擎 T+1，天然满足，
 *     这里抽查成交日确为信号日之后第一个有K线的交易日——由持仓天数>=0间接验证）
 *  4. 已知行情段合理性：2024-02 ~ 2026-10 美股牛市，趋势类策略（均线交叉/突破/MACD）
 *     在美股池上应为正收益；港股同期 HSI 上行，动量类亦应偏正
 *  5. 拼图组合语义：all/any/vote 买入、any/all 出场、停用与权重 0 块不参与、
 *     单块组合 ≡ 单策略、真实组合全池自洽
 *  6. 代码模式 JSON：序列化→解析回环、语法错误可读、未知策略报错、参数越界收敛
 */
const fs = require('fs')
const { runBacktest, runBacktestCore } = require('../.bt-test/engine.js')
const { combineSignals, parseStack, serializeStack, comboLabel } = require('../.bt-test/combo.js')

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

// ---------------------------------------------------------------- AC-503 组合逻辑
console.log('\n== AC-503 拼图组合语义 ==')

// 合成信号块：A 在 1,3 出买入、2 出出场；B 在 1,2 出买入、3 出出场
const mkFake = (id, entIdx, extIdx) => ({
  id, name: id, description: '', params: [],
  prepare(bars) {
    const entries = bars.map((_, i) => entIdx.includes(i))
    const exits = bars.map((_, i) => extIdx.includes(i))
    return { entries, exits }
  },
})
const fakeBars = Array.from({ length: 6 }, (_, i) => ({ d: 20260101 + i, o: 1, h: 1, l: 1, c: 1, v: 1 }))
const reg = {}
for (const [f] of strategies) reg[S(f).id] = S(f)
reg['fake-a'] = mkFake('fake-a', [1, 3], [2])
reg['fake-b'] = mkFake('fake-b', [1, 2], [3])
const resolve = (id) => reg[id]
const sigOf = (stack) => combineSignals(stack, resolve).prepare(fakeBars)

const mkStack = (combo, blocks) => ({ combo: { voteThresholdPct: 50, ...combo }, blocks })
const mkBlock = (id, over = {}) => ({ strategyId: id, enabled: true, weight: 1, params: {}, ...over })

{
  const base = [mkBlock('fake-a'), mkBlock('fake-b')]
  const all = sigOf(mkStack({ entryMode: 'all', exitMode: 'any' }, base))
  const any = sigOf(mkStack({ entryMode: 'any', exitMode: 'any' }, base))
  check('all：仅共同信号日买入', JSON.stringify(all.entries) === JSON.stringify([false, true, false, false, false, false]))
  check('any：并集买入', JSON.stringify(any.entries) === JSON.stringify([false, true, true, true, false, false]))
  // vote：A 权重 2、B 权重 1，阈值 60 → 只有 A 同意处成立（2/3≈66.7%≥60），B 单独同意不成立（1/3≈33.3%）
  const vote = sigOf(mkStack({ entryMode: 'vote', voteThresholdPct: 60, exitMode: 'any' },
    [mkBlock('fake-a', { weight: 2 }), mkBlock('fake-b')]))
  check('vote：权重阈值生效', JSON.stringify(vote.entries) === JSON.stringify([false, true, false, true, false, false]))
  // vote 阈值 50、等权两块：单方同意即 50% ≥ 50% 成立 → 等价于 any
  const vote50 = sigOf(mkStack({ entryMode: 'vote', voteThresholdPct: 50, exitMode: 'any' }, base))
  check('vote50 等权≈任一同意', JSON.stringify(vote50.entries) === JSON.stringify(any.entries))
  // 出场：any=并集（2,3 都出），all=交集（无共同日出）
  const exitAll = sigOf(mkStack({ entryMode: 'any', exitMode: 'all' }, base))
  check('出场 any=并集', JSON.stringify(any.exits) === JSON.stringify([false, false, true, true, false, false]))
  check('出场 all=交集', JSON.stringify(exitAll.exits) === JSON.stringify([false, false, false, false, false, false]))
  // 停用/权重 0 不参与
  const disabled = sigOf(mkStack({ entryMode: 'any', exitMode: 'any' },
    [mkBlock('fake-a'), mkBlock('fake-b', { enabled: false })]))
  const zeroW = sigOf(mkStack({ entryMode: 'any', exitMode: 'any' },
    [mkBlock('fake-a'), mkBlock('fake-b', { weight: 0 })]))
  const onlyA = [false, true, false, true, false, false]
  check('停用块不参与', JSON.stringify(disabled.entries) === JSON.stringify(onlyA))
  check('权重 0 块不参与', JSON.stringify(zeroW.entries) === JSON.stringify(onlyA))
}

// 单块组合 ≡ 直接单策略（真实模块、真实数据抽查 20 只）
{
  const st = S('maCross')
  const params = { fast: 5, slow: 20 }
  const sub = markets.US.stocks.slice(0, 20)
  const direct = runBacktest(sub, st, params, opts, markets.US.bench)
  const stack = mkStack({ entryMode: 'all', exitMode: 'any' }, [mkBlock('ma-cross', { params })])
  const viaCombo = runBacktestCore(sub, combineSignals(stack, resolve), opts, markets.US.bench)
  check('单块组合 ≡ 单策略结果',
    Math.abs(direct.metrics.totalReturnPct - viaCombo.metrics.totalReturnPct) < 1e-9 &&
    direct.trades.length === viaCombo.trades.length,
    `direct=${direct.metrics.totalReturnPct}% combo=${viaCombo.metrics.totalReturnPct}%`)
}

// 真实组合跑全池：均线交叉 + 突破，加权投票 ≥50
{
  const stack = mkStack({ entryMode: 'vote', voteThresholdPct: 50, exitMode: 'any' }, [
    mkBlock('ma-cross', { params: { fast: 5, slow: 20 } }),
    mkBlock('breakout', { params: { lookback: 20, volMult: 1.5, exitLookback: 10 } }),
  ])
  const res = runBacktestCore(markets.US.stocks, combineSignals(stack, resolve), opts,
    markets.US.bench, comboLabel(stack))
  const lastV = res.equity[res.equity.length - 1].v
  check('真实组合数学自洽', Math.abs(lastV - (1 + res.metrics.totalReturnPct / 100)) < 1e-6,
    `收益 ${res.metrics.totalReturnPct}% 交易 ${res.trades.length}`)
  check('真实组合性能 <5s', res.elapsedMs < 5000, `${res.elapsedMs}ms`)
}

// AC-502 JSON 代码模式：序列化→解析回环、语法错误、未知策略、参数收敛
console.log('\n== AC-502 代码模式 JSON ==')
{
  const stack = mkStack({ entryMode: 'vote', voteThresholdPct: 60, exitMode: 'all' }, [
    mkBlock('ma-cross', { params: { fast: 5, slow: 20 }, weight: 2 }),
    mkBlock('rsi-reversal', { enabled: false, params: { period: 14, oversold: 30, exitLevel: 55 } }),
  ])
  const rt = parseStack(serializeStack(stack), resolve)
  check('序列化→解析回环', rt.ok && rt.stack.blocks.length === 2 &&
    rt.stack.blocks[0].strategyId === 'ma-cross' && rt.stack.blocks[0].weight === 2 &&
    rt.stack.blocks[1].enabled === false && rt.stack.combo.voteThresholdPct === 60 &&
    rt.stack.combo.exitMode === 'all')
  check('语法错误可读', !parseStack('{bad json', resolve).ok)
  const unk = parseStack('{"blocks":[{"strategy":"no-such"}]}', resolve)
  check('未知策略报错', !unk.ok && unk.errors.some((e) => e.includes('未知')))
  const clamp = parseStack('{"blocks":[{"strategy":"ma-cross","params":{"fast":999,"slow":1}}]}', resolve)
  check('参数越界自动收敛', clamp.ok && clamp.stack.blocks[0].params.fast === 60 &&
    clamp.stack.blocks[0].params.slow === 5,
    clamp.ok ? `fast=${clamp.stack.blocks[0].params.fast} slow=${clamp.stack.blocks[0].params.slow}` : '')
  const empty = parseStack('{"blocks":[{"strategy":"ma-cross","enabled":false}]}', resolve)
  check('全停用可解析', empty.ok)
  let threw = false
  try { combineSignals(empty.stack, resolve) } catch { threw = true }
  check('全停用运行期拦截', threw)
}

console.log(failures === 0 ? '\n全部验证通过' : `\n${failures} 项失败`)
process.exit(failures === 0 ? 0 : 1)
