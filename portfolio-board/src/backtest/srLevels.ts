/** 支撑/阻力位检测器（净室实现）。
 *
 * 算法思想（公开技术方法，不复制任何第三方代码）：
 *  1. ATR(14) 归一化：分箱宽度、区带宽度、距离过滤全部以 ATR 为尺度，跨标的可比
 *  2. 体积守恒成交量剖面：每根 K 线的成交量均匀摊入其覆盖的价格箱（总量守恒），
 *     并按时间衰减加权（半衰期 = 窗口一半），近期成交权重更高
 *  3. ZigZag 摆动点：反转幅度 ≥ zigzagAtrMult × ATR 才确认一个摆动高低点
 *  4. 候选关键位 = 剖面峰 + 摆动点簇心，区带半宽夹逼到 [0.3, 1.2] × ATR
 *  5. 触及统计：价格进入区带计一次触及，离开 ≥ 0.5×ATR 后才计下一次（去重）
 *  6. 打分 = log1p(触及次数) + 0.8 × 陈旧度（越久未被考验越不可靠），NMS 合并（0.5×ATR）
 *  7. 相对参考收盘分类支撑/阻力，距离过滤到 [minDistAtr, maxDistAtr] × ATR
 *
 * 因果性：computeLevels(bars, end, ...) 只读取 bars[0..end]；
 * 策略在滚动刷新时以 end = i-1 调用，第 i 根 K 线的信号不接触第 i 根数据（策略自身的入场判断除外）。
 */
import type { Bar } from './types'

export interface SrLevel {
  /** 关键位中心价 */
  price: number
  /** 区带下沿 */
  lower: number
  /** 区带上沿 */
  upper: number
  /** 相对参考收盘的分类 */
  kind: 'support' | 'resistance'
  /** 窗口内触及次数（去重后） */
  touches: number
  /** log1p(触及) + 0.8 × 陈旧度，越大越可靠 */
  score: number
}

export interface SrDetectOptions {
  /** 剖面与摆动观察窗口（交易日数） */
  windowDays: number
  /** ZigZag 反转阈值（ATR 倍数） */
  zigzagAtrMult: number
  /** 每侧最多保留关键位数 */
  maxPerSide: number
  /** 关键位距现价最小距离（ATR 倍数） */
  minDistAtr: number
  /** 关键位距现价最大距离（ATR 倍数） */
  maxDistAtr: number
}

export const SR_DEFAULTS: SrDetectOptions = {
  windowDays: 120,
  zigzagAtrMult: 2,
  maxPerSide: 3,
  minDistAtr: 0.3,
  maxDistAtr: 5,
}

/** ATR（Wilder 平滑），前 period-1 项为 null */
export function atrSeries(bars: Bar[], period = 14): (number | null)[] {
  const n = bars.length
  const out: (number | null)[] = new Array(n).fill(null)
  if (n < period + 1) return out
  let sum = 0
  for (let i = 1; i <= period; i++) {
    const b = bars[i]
    const pc = bars[i - 1].c
    sum += Math.max(b.h - b.l, Math.abs(b.h - pc), Math.abs(b.l - pc))
  }
  let atr = sum / period
  out[period] = atr
  for (let i = period + 1; i < n; i++) {
    const b = bars[i]
    const pc = bars[i - 1].c
    const tr = Math.max(b.h - b.l, Math.abs(b.h - pc), Math.abs(b.l - pc))
    atr = (atr * (period - 1) + tr) / period
    out[i] = atr
  }
  return out
}

interface Candidate {
  price: number
  halfWidth: number
  touches: number
  lastTouch: number
}

interface Pivot {
  price: number
  idx: number
}

/** ZigZag 摆动点（窗口内，反转阈值 zigzagAtrMult × ATR），返回价格与所在 K 线下标 */
function zigzagPivots(bars: Bar[], from: number, to: number, threshold: number): Pivot[] {
  const pts: Pivot[] = []
  // 定向阶段：首个超过阈值的单向运动确定初始方向，其反向极值即第一个摆动点
  let dir = 0
  let runHi = bars[from].h
  let runHiIdx = from
  let runLo = bars[from].l
  let runLoIdx = from
  let extreme = bars[from].c
  let extremeIdx = from
  let i = from + 1
  for (; i <= to; i++) {
    const b = bars[i]
    if (b.h > runHi) { runHi = b.h; runHiIdx = i }
    if (b.l < runLo) { runLo = b.l; runLoIdx = i }
    if (b.h - runLo >= threshold) {
      pts.push({ price: runLo, idx: runLoIdx }) // 低点之后单边上行 → 低点是摆动点
      dir = 1
      extreme = runHi
      extremeIdx = runHiIdx
      i++
      break
    }
    if (runHi - b.l >= threshold) {
      pts.push({ price: runHi, idx: runHiIdx }) // 高点之后单边下行 → 高点是摆动点
      dir = -1
      extreme = runLo
      extremeIdx = runLoIdx
      i++
      break
    }
  }
  // 跟踪阶段：dir 为 ±1，两分支互斥
  for (; i <= to; i++) {
    const b = bars[i]
    if (dir > 0 && b.h > extreme) { extreme = b.h; extremeIdx = i }
    if (dir < 0 && b.l < extreme) { extreme = b.l; extremeIdx = i }
    if (dir > 0 && extreme - b.l >= threshold) {
      pts.push({ price: extreme, idx: extremeIdx }) // 摆动高点
      dir = -1
      extreme = b.l
      extremeIdx = i
    } else if (dir < 0 && b.h - extreme >= threshold) {
      pts.push({ price: extreme, idx: extremeIdx }) // 摆动低点
      dir = 1
      extreme = b.h
      extremeIdx = i
    }
  }
  return pts
}

/**
 * 检测关键位。只读取 bars[0..end]（含 end），严格因果。
 * 计算量 O(window × bins)，供滚动刷新调用。
 */
export function computeLevels(bars: Bar[], end: number, opts: SrDetectOptions): SrLevel[] {
  if (end < 20) return []
  const atr = atrSeries(bars)[end]
  if (atr == null || atr <= 0) return []
  const from = Math.max(1, end - opts.windowDays + 1)
  const refClose = bars[end].c

  // ---- 体积守恒成交量剖面（时间衰减加权） ----
  let pmin = Infinity
  let pmax = -Infinity
  for (let i = from; i <= end; i++) {
    if (bars[i].l < pmin) pmin = bars[i].l
    if (bars[i].h > pmax) pmax = bars[i].h
  }
  if (!(pmax > pmin)) return []
  const binW = Math.max(0.25 * atr, (pmax - pmin) / 400) // 0.25×ATR 分箱，下限防退化
  const nBins = Math.min(400, Math.max(10, Math.ceil((pmax - pmin) / binW) + 1))
  const profile = new Float64Array(nBins)
  const span = end - from + 1
  const halfLife = Math.max(5, span / 2)
  for (let i = from; i <= end; i++) {
    const b = bars[i]
    const decay = Math.pow(0.5, (end - i) / halfLife)
    const lo = Math.max(0, Math.floor((b.l - pmin) / binW))
    const hi = Math.min(nBins - 1, Math.floor((b.h - pmin) / binW))
    const share = (b.v * decay) / (hi - lo + 1) // 守恒：总量 = v × decay
    for (let k = lo; k <= hi; k++) profile[k] += share
  }
  // 轻平滑（3 箱滑动均值）
  const smooth = new Float64Array(nBins)
  for (let k = 0; k < nBins; k++) {
    const a = profile[Math.max(0, k - 1)]
    const c = profile[k]
    const d = profile[Math.min(nBins - 1, k + 1)]
    smooth[k] = (a + c + d) / 3
  }

  // ---- 候选：剖面峰（局部极大，显著度 ≥ 12% 峰值；半宽取半峰宽，夹逼 [0.3, 1.2]×ATR） ----
  let peakMax = 0
  for (let k = 0; k < nBins; k++) if (smooth[k] > peakMax) peakMax = smooth[k]
  const cands: Candidate[] = []
  if (peakMax > 0) {
    for (let k = 1; k < nBins - 1; k++) {
      if (smooth[k] >= smooth[k - 1] && smooth[k] >= smooth[k + 1] && smooth[k] >= 0.12 * peakMax) {
        // 半峰宽：峰两侧连续 ≥ 峰高一半的箱数（平台区自然得到宽区带）
        let loK = k
        while (loK > 0 && smooth[loK - 1] >= smooth[k] / 2) loK--
        let hiK = k
        while (hiK < nBins - 1 && smooth[hiK + 1] >= smooth[k] / 2) hiK++
        const widthBins = Math.max(1, hiK - loK + 1)
        const halfWidth = Math.min(1.2 * atr, Math.max(0.3 * atr, (widthBins * binW) / 2))
        cands.push({ price: pmin + (k + 0.5) * binW, halfWidth, touches: 0, lastTouch: -1 })
      }
    }
  }
  // ---- 候选：ZigZag 摆动点（按 0.5×ATR 聚类取均值；区带包住整簇） ----
  const pivots = zigzagPivots(bars, from, end, opts.zigzagAtrMult * atr)
  const sorted = [...pivots].sort((a, b) => a.price - b.price)
  for (let i = 0; i < sorted.length; i++) {
    let sum = sorted[i].price
    let lo = sorted[i].price
    let hi = sorted[i].price
    let cnt = 1
    while (i + 1 < sorted.length && sorted[i + 1].price - sorted[i].price <= 0.5 * atr) {
      i++
      sum += sorted[i].price
      lo = Math.min(lo, sorted[i].price)
      hi = Math.max(hi, sorted[i].price)
      cnt++
    }
    const halfWidth = Math.min(1.2 * atr, Math.max(0.3 * atr, binW, (hi - lo) / 2 + 0.1 * atr))
    cands.push({ price: sum / cnt, halfWidth, touches: 0, lastTouch: -1 })
  }
  if (cands.length === 0) return []

  // ---- 触及统计：窗口内在该区带内形成的摆动点数量（每次反转=一次真实考验） ----
  for (const c of cands) {
    for (const p of pivots) {
      if (p.price >= c.price - c.halfWidth && p.price <= c.price + c.halfWidth) {
        c.touches++
        if (p.idx > c.lastTouch) c.lastTouch = p.idx
      }
    }
  }

  // ---- 打分 + NMS（0.5×ATR） + 分类 + 距离过滤 ----
  const scored = cands
    .filter((c) => c.touches >= 2)
    .map((c) => {
      const staleness = c.lastTouch < 0 ? 1 : (end - c.lastTouch) / span
      return { c, score: Math.log1p(c.touches) + 0.8 * staleness }
    })
    .sort((a, b) => b.score - a.score)
  const kept: typeof scored = []
  for (const s of scored) {
    if (kept.every((k) => Math.abs(k.c.price - s.c.price) > 0.5 * atr)) kept.push(s)
  }
  const out: SrLevel[] = []
  let nSup = 0
  let nRes = 0
  for (const { c, score } of kept) {
    const dist = Math.abs(c.price - refClose) / atr
    if (dist < opts.minDistAtr || dist > opts.maxDistAtr) continue
    const kind: SrLevel['kind'] = c.price < refClose ? 'support' : 'resistance'
    if (kind === 'support' && nSup >= opts.maxPerSide) continue
    if (kind === 'resistance' && nRes >= opts.maxPerSide) continue
    if (kind === 'support') nSup++
    else nRes++
    out.push({
      price: c.price,
      lower: c.price - c.halfWidth,
      upper: c.price + c.halfWidth,
      kind,
      touches: c.touches,
      score,
    })
  }
  return out
}

/** 滚动关键位管理器：每 refreshEvery 根刷新一次，刷新以 i-1 为终点（严格因果） */
export class RollingSr {
  private levels: SrLevel[] = []
  private lastRefresh = -Infinity
  private bars: Bar[]
  private opts: SrDetectOptions
  private refreshEvery: number
  constructor(bars: Bar[], opts: SrDetectOptions, refreshEvery: number) {
    this.bars = bars
    this.opts = opts
    this.refreshEvery = refreshEvery
  }

  /** 第 i 根收盘时点可用的关键位（数据 ≤ i-1） */
  at(i: number): SrLevel[] {
    if (i - this.lastRefresh >= this.refreshEvery && i - 1 >= 20) {
      this.levels = computeLevels(this.bars, i - 1, this.opts)
      this.lastRefresh = i
    }
    return this.levels
  }
}

/** 距 price 最近的下/上方关键位 */
export function nearestBelow(levels: SrLevel[], price: number): SrLevel | null {
  let best: SrLevel | null = null
  for (const l of levels) if (l.price < price && (!best || l.price > best.price)) best = l
  return best
}

export function nearestAbove(levels: SrLevel[], price: number): SrLevel | null {
  let best: SrLevel | null = null
  for (const l of levels) if (l.price > price && (!best || l.price < best.price)) best = l
  return best
}
