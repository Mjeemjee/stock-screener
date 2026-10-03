/** 回测引擎：指标计算 + 组合级模拟。
 *
 * 交易规则（所有策略共用）：
 *  - 信号在第 i 根 K 线收盘产生，第 i+1 根开盘成交（T+1，无未来函数）
 *  - 等权分仓：单笔目标金额 = 当前净值 / 最大持仓数，不超过可用现金
 *  - 单边成本 = 佣金+滑点合并百分比，买卖各收一次；允许零碎股（简化）
 *  - 出场优先级：策略出场信号 / 止损 / 止盈 / 最大持有K线数，先到先出
 */
import type {
  BacktestOptions,
  BacktestResult,
  Bar,
  EquityPoint,
  Metrics,
  StockSeries,
  StrategyModule,
  Trade,
} from './types'

// ---------------------------------------------------------------- 指标工具

export function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null)
  let sum = 0
  for (let i = 0; i < values.length; i++) {
    sum += values[i]
    if (i >= period) sum -= values[i - period]
    if (i >= period - 1) out[i] = sum / period
  }
  return out
}

export function ema(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null)
  const k = 2 / (period + 1)
  let prev = 0
  for (let i = 0; i < values.length; i++) {
    if (i === period - 1) {
      let s = 0
      for (let j = 0; j < period; j++) s += values[j]
      prev = s / period
      out[i] = prev
    } else if (i >= period) {
      prev = values[i] * k + prev * (1 - k)
      out[i] = prev
    }
  }
  return out
}

/** Wilder RSI */
export function rsi(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null)
  if (closes.length <= period) return out
  let gain = 0
  let loss = 0
  for (let i = 1; i <= period; i++) {
    const ch = closes[i] - closes[i - 1]
    if (ch > 0) gain += ch
    else loss -= ch
  }
  let avgGain = gain / period
  let avgLoss = loss / period
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
  for (let i = period + 1; i < closes.length; i++) {
    const ch = closes[i] - closes[i - 1]
    avgGain = (avgGain * (period - 1) + Math.max(ch, 0)) / period
    avgLoss = (avgLoss * (period - 1) + Math.max(-ch, 0)) / period
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
  }
  return out
}

export function macd(closes: number[], fast: number, slow: number, signalP: number) {
  const ef = ema(closes, fast)
  const es = ema(closes, slow)
  const dif: (number | null)[] = closes.map((_, i) =>
    ef[i] != null && es[i] != null ? ef[i]! - es[i]! : null,
  )
  const dea: (number | null)[] = new Array(closes.length).fill(null)
  const firstValid = dif.findIndex((d) => d != null)
  if (firstValid >= 0) {
    const sub = dif.slice(firstValid) as number[]
    const e = ema(sub, signalP)
    for (let i = 0; i < sub.length; i++) dea[firstValid + i] = e[i]
  }
  return { dif, dea }
}

/** 前 N 根（不含当根）滚动最大值 */
export function rollingMaxPrev(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null)
  for (let i = period; i < values.length; i++) {
    let m = -Infinity
    for (let j = i - period; j < i; j++) if (values[j] > m) m = values[j]
    out[i] = m
  }
  return out
}

/** 前 N 根（不含当根）滚动最小值 */
export function rollingMinPrev(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null)
  for (let i = period; i < values.length; i++) {
    let m = Infinity
    for (let j = i - period; j < i; j++) if (values[j] < m) m = values[j]
    out[i] = m
  }
  return out
}

/** 滚动标准差（含当根，用于布林带） */
export function rollingStd(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null)
  let sum = 0
  let sumSq = 0
  for (let i = 0; i < values.length; i++) {
    sum += values[i]
    sumSq += values[i] * values[i]
    if (i >= period) {
      sum -= values[i - period]
      sumSq -= values[i - period] * values[i - period]
    }
    if (i >= period - 1) {
      const mean = sum / period
      const varr = Math.max(sumSq / period - mean * mean, 0)
      out[i] = Math.sqrt(varr)
    }
  }
  return out
}

/** a 上穿 b：a[i] > b[i] 且 a[i-1] <= b[i-1]（null 不参与） */
export function crossUp(a: (number | null)[], b: (number | null)[]): boolean[] {
  const out = new Array<boolean>(a.length).fill(false)
  for (let i = 1; i < a.length; i++) {
    const x0 = a[i - 1]
    const x1 = a[i]
    const y0 = b[i - 1]
    const y1 = b[i]
    if (x0 == null || x1 == null || y0 == null || y1 == null) continue
    out[i] = x1 > y1 && x0 <= y0
  }
  return out
}

export function crossDown(a: (number | null)[], b: (number | null)[]): boolean[] {
  const out = new Array<boolean>(a.length).fill(false)
  for (let i = 1; i < a.length; i++) {
    const x0 = a[i - 1]
    const x1 = a[i]
    const y0 = b[i - 1]
    const y1 = b[i]
    if (x0 == null || x1 == null || y0 == null || y1 == null) continue
    out[i] = x1 < y1 && x0 >= y0
  }
  return out
}

// ---------------------------------------------------------------- 模拟器

interface Prepared {
  s: StockSeries
  entries: boolean[]
  exits: boolean[]
  dateIdx: Map<number, number>
}

interface Position {
  code: string
  name: string
  shares: number
  entryPrice: number
  entryDate: number
  entryBarIdx: number
  entryCost: number
  lastClose: number
  lastDate: number
}

const r4 = (x: number) => Math.round(x * 10000) / 10000

function computeMetrics(
  equity: EquityPoint[],
  trades: Trade[],
  initialCash: number,
): Metrics {
  const n = equity.length
  const finalV = n > 0 ? equity[n - 1].v : 1
  const totalReturnPct = (finalV - 1) * 100
  const cagrPct = n > 1 && finalV > 0 ? (Math.pow(finalV, 252 / n) - 1) * 100 : 0

  let peak = -Infinity
  let maxDd = 0
  for (const p of equity) {
    if (p.v > peak) peak = p.v
    const dd = p.v / peak - 1
    if (dd < maxDd) maxDd = dd
  }

  const rets: number[] = []
  for (let i = 1; i < n; i++) rets.push(equity[i].v / equity[i - 1].v - 1)
  let sharpe = 0
  if (rets.length > 1) {
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length
    const variance = rets.reduce((a, b) => a + (b - mean) * (b - mean), 0) / (rets.length - 1)
    const std = Math.sqrt(variance)
    sharpe = std > 0 ? (mean / std) * Math.sqrt(252) : 0
  }

  const wins = trades.filter((t) => t.pnl > 0)
  const losses = trades.filter((t) => t.pnl <= 0)
  const sumWin = wins.reduce((a, t) => a + t.pnl, 0)
  const sumLoss = Math.abs(losses.reduce((a, t) => a + t.pnl, 0))

  return {
    totalReturnPct: r4(totalReturnPct),
    cagrPct: r4(cagrPct),
    maxDrawdownPct: r4(maxDd * 100),
    sharpe: r4(sharpe),
    winRatePct: trades.length > 0 ? r4((wins.length / trades.length) * 100) : 0,
    tradeCount: trades.length,
    avgPnlPct: trades.length > 0 ? r4(trades.reduce((a, t) => a + t.pnlPct, 0) / trades.length) : 0,
    profitFactor: sumLoss > 0 ? r4(sumWin / sumLoss) : null,
    finalEquity: Math.round(finalV * initialCash),
  }
}

export function runBacktest(
  stocks: StockSeries[],
  strategy: StrategyModule,
  params: Record<string, number>,
  opts: BacktestOptions,
  bench?: Bar[],
): BacktestResult {
  const t0 = performance.now()
  const cost = opts.costPct / 100
  const inRange = (d: number) =>
    (!opts.startDate || d >= opts.startDate) && (!opts.endDate || d <= opts.endDate)

  // 1) 预计算每只股票的信号与日期索引
  const prepared: Prepared[] = []
  for (const s of stocks) {
    if (s.bars.length < 60) continue
    const { entries, exits } = strategy.prepare(s.bars, params)
    const dateIdx = new Map<number, number>()
    s.bars.forEach((b, i) => dateIdx.set(b.d, i))
    prepared.push({ s, entries, exits, dateIdx })
  }
  const byCode = new Map(prepared.map((p) => [p.s.code, p]))

  // 2) 交易日历（范围内）
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

  // 3) 逐日模拟
  let cash = opts.initialCash
  const positions = new Map<string, Position>()
  const pendingBuys = new Set<string>()
  const pendingSells = new Map<string, string>()
  const trades: Trade[] = []
  const equity: EquityPoint[] = []
  let lastEquity = opts.initialCash

  const closeTrade = (pos: Position, price: number, d: number, reason: string, barIdx: number) => {
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
    positions.delete(pos.code)
  }

  for (const d of calendar) {
    // 3a 开盘先卖
    for (const [code, reason] of [...pendingSells]) {
      const prep = byCode.get(code)
      const pos = positions.get(code)
      if (!prep || !pos) {
        pendingSells.delete(code)
        continue
      }
      const i = prep.dateIdx.get(d)
      if (i == null) continue // 今日停牌，顺延
      closeTrade(pos, prep.s.bars[i].o, d, reason, i)
      pendingSells.delete(code)
    }
    // 3b 开盘再买
    for (const code of [...pendingBuys]) {
      const prep = byCode.get(code)
      if (!prep) {
        pendingBuys.delete(code)
        continue
      }
      const i = prep.dateIdx.get(d)
      if (i == null) continue
      pendingBuys.delete(code)
      if (positions.has(code) || positions.size >= opts.maxPositions) continue
      const price = prep.s.bars[i].o
      if (!(price > 0)) continue
      const alloc = Math.min(cash, lastEquity / opts.maxPositions)
      if (alloc < opts.initialCash * 0.005) continue // 现金不足一格，放弃
      const shares = alloc / (price * (1 + cost))
      cash -= shares * price * (1 + cost)
      positions.set(code, {
        code,
        name: prep.s.name,
        shares,
        entryPrice: price,
        entryDate: d,
        entryBarIdx: i,
        entryCost: shares * price * (1 + cost),
        lastClose: prep.s.bars[i].c,
        lastDate: d,
      })
    }
    // 3c 收盘评估信号
    for (const prep of prepared) {
      const i = prep.dateIdx.get(d)
      if (i == null) continue
      const bar = prep.s.bars[i]
      const pos = positions.get(prep.s.code)
      if (pos) {
        pos.lastClose = bar.c
        pos.lastDate = d
        if (pendingSells.has(prep.s.code)) continue
        let reason: string | null = null
        if (prep.exits[i]) reason = '策略出场信号'
        const chgPct = (bar.c / pos.entryPrice - 1) * 100
        if (!reason && opts.stopLossPct > 0 && chgPct <= -opts.stopLossPct)
          reason = `止损 -${opts.stopLossPct}%`
        if (!reason && opts.takeProfitPct > 0 && chgPct >= opts.takeProfitPct)
          reason = `止盈 +${opts.takeProfitPct}%`
        if (!reason && opts.maxHoldDays > 0 && i - pos.entryBarIdx >= opts.maxHoldDays)
          reason = `持有满 ${opts.maxHoldDays} 根K线`
        if (reason) pendingSells.set(prep.s.code, reason)
      } else if (!pendingBuys.has(prep.s.code)) {
        if (positions.size + pendingBuys.size >= opts.maxPositions) continue
        if (prep.entries[i] && i + 1 < prep.s.bars.length) pendingBuys.add(prep.s.code)
      }
    }
    // 3d 收盘估值
    let eq = cash
    for (const pos of positions.values()) eq += pos.shares * pos.lastClose
    lastEquity = eq
    equity.push({ d, v: eq / opts.initialCash, bench: benchMap.get(d) ?? null })
  }

  // 4) 期末强制清算（按最后已知收盘价）
  const lastDay = calendar[calendar.length - 1] ?? 0
  for (const pos of [...positions.values()]) {
    const prep = byCode.get(pos.code)
    const barIdx = prep ? (prep.dateIdx.get(pos.lastDate) ?? pos.entryBarIdx) : pos.entryBarIdx
    closeTrade(pos, pos.lastClose, lastDay, '期末清算', barIdx)
  }
  if (equity.length > 0) {
    const finalEq = cash
    equity[equity.length - 1] = {
      d: lastDay,
      v: finalEq / opts.initialCash,
      bench: benchMap.get(lastDay) ?? null,
    }
  }

  // 5) 回撤序列与指标
  let peak = -Infinity
  const drawdown = equity.map((p) => {
    if (p.v > peak) peak = p.v
    return { d: p.d, dd: r4((p.v / peak - 1) * 100) }
  })
  trades.sort((a, b) => b.exitDate - a.exitDate)

  return {
    metrics: computeMetrics(equity, trades, opts.initialCash),
    equity,
    drawdown,
    trades,
    strategyId: strategy.id,
    params,
    options: opts,
    stockCount: prepared.length,
    elapsedMs: Math.round(performance.now() - t0),
  }
}
