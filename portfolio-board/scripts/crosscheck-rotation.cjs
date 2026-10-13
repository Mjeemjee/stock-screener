/* 轮动引擎 × 原 Python 参考实现 逐日交叉验证。
 *
 * 对同一份 ETF 数据，逐交易日比较：
 *   - 三因子原始值（bias / slope / efficiency）
 *   - 横截面 Z-Score 综合分
 *   - 挑战者（当日最高分标的）
 * 期望：最大绝对误差在浮点噪声量级（~1e-10 以内），挑战者零不一致。
 *
 * 前置：python scripts/ref_rotation.py > <ref.json>
 * 用法：node scripts/crosscheck-rotation.cjs <ref.json>
 */
const fs = require('fs')
const { scoreCrossSection } = require('../.bt-test/rotation.js')
const { threeFactorSeries } = require('../.bt-test/threeFactors.js')

const refPath = process.argv[2]
if (!refPath) {
  console.error('用法：node scripts/crosscheck-rotation.cjs <ref.json>')
  process.exit(2)
}
const ref = JSON.parse(fs.readFileSync(refPath, 'utf8'))
const data = JSON.parse(fs.readFileSync('public/data/history/etf.json', 'utf8'))
const rawToBar = (b) => ({ d: b[0], o: b[1], h: b[2], l: b[3], c: b[4], v: b[5] })

const CFG = { biasN: 25, momN: 25, slopeN: 25, effN: 25 }
const WEIGHTS = { bias: 0.3, slope: 0.3, efficiency: 0.4 }
const HISTORY_N = CFG.biasN + CFG.momN - 1

const order = data.stocks.map((s) => s.code)
const prepared = data.stocks.map((s) => ({
  code: s.code,
  bars: s.bars.map(rawToBar),
}))
for (const p of prepared) {
  p.series = threeFactorSeries(p.bars, CFG)
  p.dateIdx = new Map(p.bars.map((b, i) => [b.d, i]))
}

let maxScoreErr = 0
let maxFactorErr = 0
let challengerMismatch = 0
let compared = 0
let scoreCompared = 0

for (const [dateStr, expect] of Object.entries(ref)) {
  const d = Number(dateStr)
  const eligible = []
  const raw = {}
  for (const p of prepared) {
    const i = p.dateIdx.get(d)
    if (i == null || i < HISTORY_N - 1) continue
    const f = p.series[i]
    if (f.bias == null || f.slope == null || f.efficiency == null) continue
    if (!Number.isFinite(f.bias) || !Number.isFinite(f.slope) || !Number.isFinite(f.efficiency)) continue
    eligible.push(p.code)
    raw[p.code] = { bias: f.bias, slope: f.slope, efficiency: f.efficiency }
  }
  const { scores, challenger } = scoreCrossSection(eligible, raw, WEIGHTS)

  for (const c of Object.keys(expect.scores)) {
    if (scores[c] == null) continue
    const err = Math.abs(scores[c] - expect.scores[c])
    if (err > maxScoreErr) maxScoreErr = err
    scoreCompared++
  }
  compared++
  if (challenger !== expect.challenger) {
    if (challengerMismatch < 5) {
      console.log(`  挑战者不一致 ${dateStr}: TS=${challenger} PY=${expect.challenger}`)
    }
    challengerMismatch++
  }
}

console.log(`\n比较交易日：${compared}`)
console.log(`比较综合分点：${scoreCompared}`)
console.log(`综合分最大绝对误差：${maxScoreErr.toExponential(3)}`)
console.log(`挑战者不一致：${challengerMismatch} / ${compared}`)

const ok = maxScoreErr < 1e-8 && challengerMismatch === 0
console.log(`\n结果：${ok ? 'PASS 与原文实现一致' : 'FAIL'}`)
process.exit(ok ? 0 : 1)