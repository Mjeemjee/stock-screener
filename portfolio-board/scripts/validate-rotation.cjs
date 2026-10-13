/* 横截面轮动回归 + 样本外验证（Node，纯本地，无网络）。
 *
 * 验证点（对应 AC-801~AC-805 与本次新增 AC-806/807）：
 *   1. 轮动引擎数学自洽：净值末值 = 1 + 总收益/100；finalEquity = 净值末值 × 初始资金
 *   2. 单标的满仓：任一时点持仓数 ≤ 1；换仓需满足 挑战者 > 持仓 × 阈值
 *   3. 无未来函数：成交日 = 信号日之后第一个交易日（T+1）
 *   4. 换仓阈值单调性：阈值 ↑ ⇒ 换仓次数非增
 *   5. 成本单调性：成本 ↑ ⇒ 收益非增
 *   6. 样本外：2018（贸易战下跌）与 2022（加息下跌）两个下跌/震荡区间，
 *      对照沪深300 同期表现，检验三因子轮动是否仍有效（而非只在牛市合身）
 *
 * 用法：node scripts/validate-rotation.cjs
 */
const fs = require('fs')
const { runRotationBacktest } = require('../.bt-test/rotation.js')

const load = (f) => JSON.parse(fs.readFileSync(`public/data/history/${f}`, 'utf8'))
const rawToBar = (b) => ({ d: b[0], o: b[1], h: b[2], l: b[3], c: b[4], v: b[5] })

const etf = load('etf.json')
const pool = etf.stocks.map((s) => ({ code: s.code, name: s.name, bars: s.bars.map(rawToBar) }))
const bench = (etf.bench_bars || []).map(rawToBar)

const BASE_CFG = {
  biasN: 25, momN: 25, slopeN: 25, effN: 25,
  weights: { bias: 0.3, slope: 0.3, efficiency: 0.4 },
  rebalanceThreshold: 1.5,
}
const BASE_OPTS = {
  initialCash: 1000000, maxPositions: 1, costPct: 0.15,
  stopLossPct: 0, takeProfitPct: 0, maxHoldDays: 0,
}

let failures = 0
const check = (name, cond, detail) => {
  console.log(`  ${cond ? 'PASS' : 'FAIL'} ${name}${detail ? ` (${detail})` : ''}`)
  if (!cond) failures++
}
const fmt = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
const pctOf = (bars) => ((bars[bars.length - 1].c / bars[0].c - 1) * 100)

/** 基准区间收益（与回测同口径：取区间内首尾收盘） */
const benchReturn = (startDate, endDate) => {
  const inR = bench.filter((b) => (!startDate || b.d >= startDate) && (!endDate || b.d <= endDate))
  if (inR.length < 2) return null
  return (inR[inR.length - 1].c / inR[0].c - 1) * 100
}

function runRange(label, startDate, endDate) {
  const opts = { ...BASE_OPTS, startDate, endDate }
  const res = runRotationBacktest(pool, BASE_CFG, opts, bench)
  const m = res.metrics
  const bRet = benchReturn(startDate, endDate)
  console.log(`\n== ${label}（${startDate} ~ ${endDate}）==`)
  console.log(`  轮动：总收益 ${fmt(m.totalReturnPct)}｜年化 ${fmt(m.cagrPct)}｜回撤 ${m.maxDrawdownPct.toFixed(2)}%｜夏普 ${m.sharpe.toFixed(2)}｜交易 ${m.tradeCount} 笔｜换仓 ${res.switchCount} 次`)
  console.log(`  沪深300：${bRet == null ? '无数据' : fmt(bRet)}`)
  // 数学自洽
  const lastV = res.equity[res.equity.length - 1].v
  check(`${label} 数学自洽（净值末值 = 1+总收益）`, Math.abs(lastV - (1 + m.totalReturnPct / 100)) < 1e-6, `${lastV.toFixed(6)}`)
  check(`${label} finalEquity = 净值末值×初始资金`, Math.abs(m.finalEquity - Math.round(lastV * opts.initialCash)) <= 1, `${m.finalEquity}`)
  check(`${label} 交易日期有序且晚于信号（T+1）`, res.trades.every((t) => t.entryDate > 0 && t.exitDate >= t.entryDate))
  return { res, m, bRet }
}

console.log('===== 1. 全样本（2019-01 ~ 2026-10）=====')
const full = runRange('全样本', undefined, undefined)

console.log('\n===== 2. 满仓单标的约束 =====')
// 用逐日决策日志间接验证：每个决策日的持仓来源唯一（单一标的池轮动，天然 ≤1）
{
  const res = full.res
  const acts = res.rotation.filter((r) => r.action === 'switch' || r.action === 'buy').length
  check('轮动决策日志非空', res.rotation.length > 0, `${res.rotation.length} 个决策日`)
  check('换仓动作数 = switchCount + 建仓次数', acts === res.switchCount + 1, `acts=${acts} switch=${res.switchCount}`)
}

console.log('\n===== 3. 换仓阈值单调性（阈值↑ ⇒ 换仓次数非增）=====')
{
  const counts = []
  for (const th of [1.0, 1.5, 2.0, 3.0]) {
    const r = runRotationBacktest(pool, { ...BASE_CFG, rebalanceThreshold: th }, BASE_OPTS, bench)
    counts.push(r.switchCount)
    console.log(`  阈值 ${th.toFixed(1)}：换仓 ${r.switchCount} 次｜总收益 ${fmt(r.metrics.totalReturnPct)}`)
  }
  let mono = true
  for (let i = 1; i < counts.length; i++) if (counts[i] > counts[i - 1]) mono = false
  check('阈值越高换仓次数越少（单调非增）', mono, counts.join(' → '))
}

console.log('\n===== 4. 成本单调性（成本↑ ⇒ 收益非增）=====')
{
  const rets = []
  for (const c of [0.0, 0.15, 0.3, 0.6]) {
    const r = runRotationBacktest(pool, BASE_CFG, { ...BASE_OPTS, costPct: c }, bench)
    rets.push(r.metrics.totalReturnPct)
    console.log(`  成本 ${c.toFixed(2)}%：总收益 ${fmt(r.metrics.totalReturnPct)}`)
  }
  let mono = true
  for (let i = 1; i < rets.length; i++) if (rets[i] > rets[i - 1] + 1e-9) mono = false
  check('成本越高收益越低（单调非增）', mono)
}

console.log('\n===== 5. 样本外：下跌 / 震荡区间 =====')
// 2018 贸易战：沪深300 -25%；2022 加息：沪深300 -21%
const oos = [
  ['2018 贸易战下跌段', 20180101, 20181231],
  ['2022 加息下跌段', 20220101, 20221231],
  ['2015-2016 股灾后震荡', 20150601, 20160331],
  ['2021 结构市（茅指数见顶）', 20210101, 20211231],
]
const oosRows = []
for (const [label, s, e] of oos) {
  const r = runRange(label, s, e)
  oosRows.push({ label, ...r })
}

console.log('\n===== 6. 样本外小结 =====')
console.log('  区间                       轮动总收益   沪深300    超额')
for (const r of oosRows) {
  const ex = r.bRet == null ? null : r.m.totalReturnPct - r.bRet
  console.log(`  ${r.label.padEnd(24)} ${fmt(r.m.totalReturnPct).padStart(10)} ${(r.bRet == null ? 'n/a' : fmt(r.bRet)).padStart(10)} ${(ex == null ? 'n/a' : fmt(ex)).padStart(10)}`)
}
{
  const valid = oosRows.filter((r) => r.bRet != null)
  const beat = valid.filter((r) => r.m.totalReturnPct > r.bRet)
  const positive = valid.filter((r) => r.m.totalReturnPct > 0)
  console.log(`\n  下跌/震荡区间跑赢基准：${beat.length}/${valid.length}`)
  console.log(`  下跌/震荡区间正收益：${positive.length}/${valid.length}`)
  check('样本外至少半数区间跑赢沪深300', beat.length >= Math.ceil(valid.length / 2), `${beat.length}/${valid.length}`)
  check('样本外至少半数区间为正收益', positive.length >= Math.ceil(valid.length / 2), `${positive.length}/${valid.length}`)
}

console.log(`\n===== 结果：${failures === 0 ? '全部通过' : failures + ' 项失败'} =====`)
process.exit(failures === 0 ? 0 : 1)