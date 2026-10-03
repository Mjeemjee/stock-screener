import { rollingStd, sma } from '../engine'
import type { StrategyModule } from '../types'

/** 布林带均值回归：跌破下轨后收回带内买入，回到中轨离场。
 * 假设价格围绕均值波动，适合震荡市；趋势市中会逆势接刀。 */
export const strategy: StrategyModule = {
  id: 'bollinger-revert',
  name: '布林带回归',
  description:
    '收盘价跌破布林带下轨后又收回带内时买入，回到中轨（均线）离场。赚「价格偏离均值后回归」的钱，震荡市好用；单边趋势里会逆势接刀，需配合止损。',
  params: [
    { key: 'period', label: '布林周期', default: 20, min: 10, max: 60, step: 1 },
    { key: 'mult', label: '标准差倍数', description: '上下轨 = 中轨 ± 倍数×标准差', default: 2, min: 1, max: 3.5, step: 0.1 },
  ],
  prepare(bars, p) {
    const closes = bars.map((b) => b.c)
    const period = Math.round(p.period)
    const mid = sma(closes, period)
    const std = rollingStd(closes, period)
    const entries = new Array<boolean>(bars.length).fill(false)
    const exits = new Array<boolean>(bars.length).fill(false)
    for (let i = 1; i < bars.length; i++) {
      if (mid[i] == null || std[i] == null || mid[i - 1] == null || std[i - 1] == null) continue
      const lower = mid[i]! - p.mult * std[i]!
      const prevLower = mid[i - 1]! - p.mult * std[i - 1]!
      entries[i] = closes[i - 1] < prevLower && closes[i] >= lower
      exits[i] = closes[i] >= mid[i]!
    }
    return { entries, exits }
  },
}
