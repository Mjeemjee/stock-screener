/**
 * 横截面轮动引擎：复现聚宽文章 81505「ETF 三因子动量轮动」的轮动机制。
 *
 * 与既有「单标的信号 + 等权分散」引擎（engine.ts）的区别：
 *   engine.ts  ：每只标的独立出买卖信号，同时持有最多 N 只，等权分仓。
 *   rotation.ts：固定池内横截面打分，满仓持有**单一**标的，按乘法阈值换仓。
 *
 * 原作机制（逐条对齐 Python 源码）：
 *   1. 每个交易日对池内每只标的算三因子（bias / slope×R² / efficiency）。
 *   2. 三个因子各自在**当日可用标的的横截面**上做总体标准差 Z-Score（ddof=0），
 *      缺失任一因子的标的当日不参与（对应 Python 的 dropna）。
 *   3. 按权重加权求和（原作 0.3 / 0.3 / 0.4）得到综合分。
 *   4. 取综合分最高者为挑战者；空仓则直接买入。
 *   5. 已持仓时，仅当 `挑战者分数 > 持仓分数 × 阈值`（原作 1.5）才换仓，
 *      否则维持原持仓——这就是抑制频繁换手的乘法阈值。
 *
 * 本站适配（诚实记录差异）：
 *   - **T+1 执行**：信号在第 i 根收盘产生，第 i+1 根开盘成交（本站全站无未来函数约定，
 *     AC-404）。原作是 09:35 盘中同刻下单，本引擎延后一根 K 线。
 *   - **不模拟涨跌停**：原作在候选涨停/持仓跌停时跳过换仓；本站 ETF/个股历史数据
 *     不含涨跌停价字段，故不建模（ETF 涨跌停极少触发，影响可忽略）。
 *   - **停牌顺延**：某标的当日无 K 线则顺延到下一交易日成交（引擎统一行为）。
 */
import { computeMetrics, r4 } from './engine'
import { threeFactorSeries } from './threeFactors'
import type {
  BacktestOptions,
  BacktestResult,
  Bar,
  EquityPoint,
  Metrics,
  StockSeries,
  Trade,
} from './types'

export interface RotationWeights {
  bias: number
  slope: number
  efficiency: number
}

export interface RotationConfig {
  biasN: number
  momN: number
  slopeN: number
  effN: number
  weights: RotationWeights
  /** 乘法换仓阈值：挑战者分数 > 持仓分数 × 阈值 才换仓（原作 1.5） */
  rebalanceThreshold: number
  /** 参与打分所需的最少 K 线数，默认 biasN+momN-1（原作 49） */
  historyN?: number
}

/** 每个交易日的打分与决策（审计用） */
export interface RotationLogEntry {
  d: number
  /** 参与当日横截面的标的代码（已通过因子有效性过滤） */
  eligible: string[]
  /** 各标的综合分（仅含 eligible） */
  scores: Record<string, number>
  /** 当日综合分最高者 */
  challenger: string | null
  /** 当日决策：买入 / 换仓 / 维持 / 空仓 */
  action: 'buy' | 'switch' | 'hold' | 'flat'
  /** 决策时持仓（若无则 null） */
  incumbent: string | null
}

export interface RotationResult extends BacktestResult {
  rotation: RotationLogEntry[]
  /** 换仓次数（不含首次建仓） */
  switchCount: number
}

const isNum = (x: number | null | undefined): x is number =>
  x != null && Number.isFinite(x)

/**
 * 横截面轮动回测。
 *
 * @param pool   固定标的池（顺序即打分并列时的优先级，对应原作 ETF_POOL 顺序）
 * @param cfg    因子窗口、权重、换仓阈值
 * @param opts   初始资金 / 单边成本 / 起止日期 / 止损止盈（可选）
 * @param bench  基准 K 线（可选）
 */
export function runRotationBacktest(
  pool: StockSeries[],
  cfg: RotationConfig,
  opts: BacktestOptions,
  bench?: Bar[],
): RotationResult {
  const t0 = performance.now()
  const cost = opts.costPct / 100
  const inRange = (d: number) =>
    (!opts.startDate || d >= opts.startDate) && (!opts.endDate || d <= opts.endDate)
  const historyN = cfg.historyN ?? cfg.biasN + cfg.momN - 1

  // 1) 预计算池内每只标的的三因子序列与日期索引
  interface Prepared {
    s: StockSeries
    series: ReturnType<typeof threeFactorSeries>
    dateIdx: Map<number, number>
  }
  const prepared: Prepared[] = []
  for (const s of pool) {
    if (s.bars.length < historyN) continue
    const dateIdx = new Map<number, number>()
    s.bars.forEach((b, i) => dateIdx.set(b.d, i))
    prepared.push({
      s,
      series: threeFactorSeries(s.bars, {
        biasN: cfg.biasN,
        momN: cfg.momN,
        slopeN: cfg.slopeN,
        effN: cfg.effN,
      }),
      dateIdx,
    })
  }
  const byCode = new Map(prepared.map((p) => [p.s.code, p]))

  // 2) 交易日历（范围内，池内所有标的的并集）
  const dateSet = new Set<number>()
  for (const p of prepared)
    for (const b of p.s.bars) if (inRange(b.d)) dateSet.add(b.d)
  const calendar = [...dateSet].sort((a, b) => a - b)

  // 基准归一化
  const benchMap = new Map<number, number>()
  if (bench && bench.length > 0) {
    const inR = bench.filter((b) => inRange(b.d))
    const base = inR[0]?.c
    if (base) for (const b of inR) benchMap.set(b.d, b.c / base)
  }

  // 3) 逐日模拟（满仓单标的）
  let cash = opts.initialCash
  let held: {
    code: string
    name: string
    shares: number
    entryPrice: number
    entryDate: number
    entryBarIdx: number
    entryCost: number
    lastClose: number
    lastDate: number
  } | null = null
  const trades: Trade[] = []
  const equity: EquityPoint[] = []
  const rotation: RotationLogEntry[] = []
  let switchCount = 0
  /** 待执行动作：下一交易日开盘执行 */
  let pending: { target: string | null; reason: string } | null = null

  const closeTrade = (pos: NonNullable<typeof held>, price: number, d: number, reason: string, barIdx: number) => {
    const proceeds = pos.shares * price * (1 - cost)
    cash += proceeds
    trades.push({
      code: pos.code,
      name: pos.name,
      entryDate: pos.entryDate,
      entryPrice: r4(pos.entryPrice),
      exitDate: d,
      exitPrice: r4(price),
      pnlPct: r4(((price * (1 - cost)) / (pos.entryPrice * (1 + cost)) - 1) * 100),
      pnl: Math.round(proceeds - pos.entryCost),
      holdingDays: barIdx - pos.entryBarIdx,
      reason,
    })
  }

  for (const d of calendar) {
    // 3a 开盘先执行上一交易日的待办（卖出 → 买入）
    if (pending) {
      const target: string | null = pending.target
      const reason: string = pending.reason
      // 卖出当前持仓
      if (held) {
        const prep = byCode.get(held.code)
        const i = prep?.dateIdx.get(d)
        if (prep && i != null) {
          closeTrade(held, prep.s.bars[i].o, d, reason, i)
          held = null
        }
        // 停牌则顺延：pending 保留，held 保留
        else {
          // 无法在今日卖出，放弃本次换仓（下一交易日重新决策）
          pending = null
        }
      }
      // 买入目标
      if (pending && target && !held) {
        const prep = byCode.get(target)
        const i = prep?.dateIdx.get(d)
        if (prep && i != null) {
          const price = prep.s.bars[i].o
          if (price > 0) {
            const shares = cash / (price * (1 + cost))
            cash -= shares * price * (1 + cost)
            held = {
              code: target,
              name: prep.s.name,
              shares,
              entryPrice: price,
              entryDate: d,
              entryBarIdx: i,
              entryCost: shares * price * (1 + cost),
              lastClose: prep.s.bars[i].c,
              lastDate: d,
            }
          }
        }
      }
      pending = null
    }

    // 3b 收盘：更新持仓估值 + 止损/止盈（可选）+ 重新打分决策
    if (held) {
      const prep = byCode.get(held.code)
      const i = prep?.dateIdx.get(d)
      if (prep && i != null) {
        held.lastClose = prep.s.bars[i].c
        held.lastDate = d
        const chgPct = (prep.s.bars[i].c / held.entryPrice - 1) * 100
        if (opts.stopLossPct > 0 && chgPct <= -opts.stopLossPct) {
          pending = { target: null, reason: `止损 -${opts.stopLossPct}%` }
        } else if (opts.takeProfitPct > 0 && chgPct >= opts.takeProfitPct) {
          pending = { target: null, reason: `止盈 +${opts.takeProfitPct}%` }
        } else if (
          opts.maxHoldDays > 0 &&
          i - held.entryBarIdx >= opts.maxHoldDays
        ) {
          pending = { target: null, reason: `持有满 ${opts.maxHoldDays} 根K线` }
        }
      }
    }

    // 3c 横截面打分（仅在无待办动作时决策）
    if (!pending) {
      const eligible: string[] = []
      const raw: Record<string, { bias: number; slope: number; efficiency: number }> = {}
      for (const p of prepared) {
        const i = p.dateIdx.get(d)
        if (i == null || i < historyN - 1) continue
        const f = p.series[i]
        if (!isNum(f.bias) || !isNum(f.slope) || !isNum(f.efficiency)) continue
        eligible.push(p.s.code)
        raw[p.s.code] = { bias: f.bias, slope: f.slope, efficiency: f.efficiency }
      }

      const { scores, challenger } = scoreCrossSection(eligible, raw, cfg.weights)

      const incumbent: string | null = held ? held.code : null
      let action: RotationLogEntry['action'] = 'flat'
      if (challenger != null) {
        if (incumbent == null) {
          action = 'buy'
          pending = { target: challenger, reason: '轮动建仓' }
        } else if (incumbent === challenger) {
          action = 'hold'
        } else if (
          scores[incumbent] != null &&
          !(scores[challenger] > scores[incumbent] * cfg.rebalanceThreshold)
        ) {
          action = 'hold'
        } else {
          action = 'switch'
          switchCount++
          pending = { target: challenger, reason: '轮动换仓' }
        }
      }
      rotation.push({ d, eligible, scores, challenger, action, incumbent })
    }

    // 3d 收盘估值
    let eq = cash
    if (held) eq += held.shares * held.lastClose
    equity.push({ d, v: eq / opts.initialCash, bench: benchMap.get(d) ?? null })
  }

  // 4) 期末强制清算（按最后已知收盘价）
  const lastDay = calendar[calendar.length - 1] ?? 0
  if (held) {
    const prep = byCode.get(held.code)
    const barIdx = prep ? (prep.dateIdx.get(held.lastDate) ?? held.entryBarIdx) : held.entryBarIdx
    closeTrade(held, held.lastClose, lastDay, '期末清算', barIdx)
    held = null
  }
  if (equity.length > 0) {
    equity[equity.length - 1] = {
      d: lastDay,
      v: cash / opts.initialCash,
      bench: benchMap.get(lastDay) ?? null,
    }
  }

  // 5) 回撤序列与指标（与 engine.ts 同一套定义）
  let peak = -Infinity
  const drawdown = equity.map((p) => {
    if (p.v > peak) peak = p.v
    return { d: p.d, dd: r4((p.v / peak - 1) * 100) }
  })
  trades.sort((a, b) => b.exitDate - a.exitDate)

  const metrics: Metrics = computeMetrics(equity, trades, opts.initialCash)

  return {
    metrics,
    equity,
    drawdown,
    trades,
    strategyId: 'rotation',
    label: `横截面轮动 · ${prepared.length} 只池 · 阈值 ${cfg.rebalanceThreshold}`,
    params: {},
    options: opts,
    stockCount: prepared.length,
    elapsedMs: Math.round(performance.now() - t0),
    rotation,
    switchCount,
  }
}
/**
 * 横截面打分（纯函数，供轮动引擎与交叉验证脚本共用）。
 *
 * 对 eligible 内的标的，三个因子各自做总体标准差 Z-Score（ddof=0；标准差为 0 时 z=0），
 * 再按 weights 加权求和。挑战者 = 综合分最大者，并列时取 eligible 中先出现者
 * （eligible 由池顺序生成，对应原作 Python dict 保序 + max() 行为）。
 */
export function scoreCrossSection(
  eligible: string[],
  raw: Record<string, { bias: number; slope: number; efficiency: number }>,
  weights: RotationWeights,
): { scores: Record<string, number>; challenger: string | null } {
  const scores: Record<string, number> = {}
  let challenger: string | null = null
  if (eligible.length === 0) return { scores, challenger }

  const keys: (keyof RotationWeights)[] = ['bias', 'slope', 'efficiency']
  const zByKey: Record<string, Record<string, number>> = {}
  for (const k of keys) {
    const vals = eligible.map((c) => raw[c][k])
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length
    const variance = vals.reduce((a, b) => a + (b - mean) * (b - mean), 0) / vals.length
    const std = Math.sqrt(variance)
    const z: Record<string, number> = {}
    for (const c of eligible) z[c] = std > 0 ? (raw[c][k] - mean) / std : 0
    zByKey[k] = z
  }

  let best = -Infinity
  for (const c of eligible) {
    const sc =
      weights.bias * zByKey.bias[c] +
      weights.slope * zByKey.slope[c] +
      weights.efficiency * zByKey.efficiency[c]
    scores[c] = sc
    if (sc > best) {
      best = sc
      challenger = c
    }
  }
  return { scores, challenger }
}