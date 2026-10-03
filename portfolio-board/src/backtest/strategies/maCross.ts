import { crossDown, crossUp, sma } from '../engine'
import type { StrategyModule } from '../types'

/** 均线交叉：经典趋势跟踪。快线上穿慢线（金叉）买入，下穿（死叉）卖出。
 * 趋势市表现好，震荡市会反复小亏（拉锯）。 */
export const strategy: StrategyModule = {
  id: 'ma-cross',
  name: '均线交叉',
  description:
    '快线上穿慢线（金叉）买入，下穿（死叉）卖出。最经典的趋势跟踪策略：赚大趋势的钱，震荡市会反复挨打。适合观察股票池整体的趋势环境。',
  params: [
    { key: 'fast', label: '快线周期', description: '短期均线天数', default: 5, min: 2, max: 60, step: 1 },
    { key: 'slow', label: '慢线周期', description: '长期均线天数', default: 20, min: 5, max: 250, step: 1 },
  ],
  prepare(bars, p) {
    const closes = bars.map((b) => b.c)
    const fast = sma(closes, Math.round(p.fast))
    const slow = sma(closes, Math.round(p.slow))
    return { entries: crossUp(fast, slow), exits: crossDown(fast, slow) }
  },
}
