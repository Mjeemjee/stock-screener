import { rollingMaxPrev, rollingMinPrev, sma } from '../engine'
import type { StrategyModule } from '../types'

/** N日新高突破：收盘创 N 日新高且放量时追入，跌破 M 日低点离场。
 * 动量类策略（海龟交易法则的简化版），牛市捕获大牛股，熊市假突破多。 */
export const strategy: StrategyModule = {
  id: 'breakout',
  name: 'N日新高突破',
  description:
    '收盘价创 N 日新高、且成交量放大到均量 K 倍以上时追入；跌破 M 日最低收盘价离场。海龟法则的简化版——动量突破在牛市能骑上大牛股，但熊市假突破会连续止损。',
  params: [
    { key: 'lookback', label: '突破观察天数', description: '收盘价创多少日新高', default: 20, min: 5, max: 120, step: 5 },
    { key: 'volMult', label: '放量倍数', description: '成交量 ≥ 20日均量 × 此倍数', default: 1.5, min: 1, max: 5, step: 0.1 },
    { key: 'exitLookback', label: '离场观察天数', description: '跌破多少日最低收盘离场', default: 10, min: 3, max: 60, step: 1 },
  ],
  prepare(bars, p) {
    const closes = bars.map((b) => b.c)
    const vols = bars.map((b) => b.v)
    const hi = rollingMaxPrev(closes, Math.round(p.lookback))
    const lo = rollingMinPrev(closes, Math.round(p.exitLookback))
    const avgV = sma(vols, 20)
    const entries = new Array<boolean>(bars.length).fill(false)
    const exits = new Array<boolean>(bars.length).fill(false)
    for (let i = 0; i < bars.length; i++) {
      if (hi[i] != null && avgV[i] != null)
        entries[i] = closes[i] > hi[i]! && vols[i] > avgV[i]! * p.volMult
      if (lo[i] != null) exits[i] = closes[i] < lo[i]!
    }
    return { entries, exits }
  },
}
