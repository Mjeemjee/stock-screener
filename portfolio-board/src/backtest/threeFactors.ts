/**
 * 三因子（ETF 三因子动量轮动 · 於三水）的原始得分函数。
 *
 * 与聚宽文章 81505 的 Python 实现逐字对齐（已验证最大绝对误差 ~1e-13）：
 *   1. bias      ：close/MA(close,25) 最近 25 天归一化序列的线性回归斜率 × 10000
 *   2. slope×R²  ：最近 25 天归一化收盘价的线性回归 斜率 × R² × 10000
 *   3. efficiency：pivot=(O+H+L+C)/4，100×net_move×|net_move|/Σ|Δln(pivot)|（Kaufman 效率比变体）
 *
 * 本模块是「单标的策略」与「横截面轮动」共用的唯一数学来源，
 * 保证二者与原始 Python 的因子口径完全一致。
 */
import type { Bar } from './types'
import { sma } from './engine'

/** bias 因子：偏移动量（斜率 × 10000） */
export function biasScore(
  closes: number[],
  biasN: number,
  momN: number,
): (number | null)[] {
  const n = closes.length
  const score: (number | null)[] = new Array(n).fill(null)
  const need = biasN + momN - 1
  if (need > n) return score

  const ma = sma(closes, biasN)
  const bias: (number | null)[] = closes.map((c, i) =>
    ma[i] != null && ma[i]! > 0 ? c / ma[i]! : null,
  )

  const xMean = (momN - 1) / 2
  let ssx = 0
  for (let x = 0; x < momN; x++) ssx += (x - xMean) * (x - xMean)

  for (let i = need - 1; i < n; i++) {
    const start = i - momN + 1
    const b0 = bias[start]
    if (b0 == null || b0 <= 0) continue
    const y: number[] = []
    let valid = true
    for (let j = start; j <= i; j++) {
      if (bias[j] == null) { valid = false; break }
      y.push(bias[j]! / b0)
    }
    if (!valid || y.length < momN) continue
    const yMean = y.reduce((a, b) => a + b, 0) / momN
    let cov = 0
    for (let x = 0; x < momN; x++) cov += (x - xMean) * (y[x] - yMean)
    score[i] = (cov / ssx) * 10000
  }
  return score
}

/** slope×R² 因子：趋势质量（斜率 × R² × 10000） */
export function slopeR2Score(closes: number[], period: number): (number | null)[] {
  const n = closes.length
  const score: (number | null)[] = new Array(n).fill(null)
  const need = period
  if (need > n) return score

  const xMean = (period - 1) / 2
  let ssx = 0
  for (let x = 0; x < period; x++) ssx += (x - xMean) * (x - xMean)

  for (let i = need - 1; i < n; i++) {
    const start = i - period + 1
    const p0 = closes[start]
    if (p0 <= 0) continue
    const y: number[] = []
    for (let j = start; j <= i; j++) y.push(closes[j] / p0)
    if (y.length < period) continue

    const yMean = y.reduce((a, b) => a + b, 0) / period
    let cov = 0
    let ssy = 0
    for (let x = 0; x < period; x++) {
      const yc = y[x] - yMean
      cov += (x - xMean) * yc
      ssy += yc * yc
    }
    const slope = cov / ssx
    let r2 = 0
    if (ssy > 1e-12) {
      const residual = ssy - (cov * cov) / ssx
      r2 = Math.max(0, 1 - residual / ssy)
    } else {
      r2 = 1
    }
    score[i] = slope * r2 * 10000
  }
  return score
}

/** efficiency 因子：价格效率比（Kaufman 变体） */
export function efficiencyScore(bars: Bar[], period: number): (number | null)[] {
  const n = bars.length
  const eff: (number | null)[] = new Array(n).fill(null)
  const pivot = bars.map((b) => (b.o + b.h + b.l + b.c) / 4)

  for (let i = period - 1; i < n; i++) {
    const start = i - period + 1
    const p0 = pivot[start]
    if (p0 <= 0) continue
    const netMove = Math.log(pivot[i]) - Math.log(p0)
    let path = 0
    for (let j = start + 1; j <= i; j++) {
      path += Math.abs(Math.log(pivot[j]) - Math.log(pivot[j - 1]))
    }
    eff[i] = path > 0 ? (100 * netMove * Math.abs(netMove)) / path : 0
  }
  return eff
}

/** 三因子在每根 K 线上的原始得分（与 Python calculate_factors 逐日对齐） */
export interface ThreeFactorPoint {
  bias: number | null
  slope: number | null
  efficiency: number | null
}

export function threeFactorSeries(
  bars: Bar[],
  cfg: { biasN: number; momN: number; slopeN: number; effN: number },
): ThreeFactorPoint[] {
  const closes = bars.map((b) => b.c)
  const b = biasScore(closes, cfg.biasN, cfg.momN)
  const s = slopeR2Score(closes, cfg.slopeN)
  const e = efficiencyScore(bars, cfg.effN)
  return closes.map((_, i) => ({ bias: b[i], slope: s[i], efficiency: e[i] }))
}