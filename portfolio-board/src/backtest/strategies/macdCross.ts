import { crossDown, crossUp, macd } from '../engine'
import type { StrategyModule } from '../types'

/** MACD 金叉：DIF 上穿 DEA 买入，下穿卖出。
 * 与均线交叉同族但信号更平滑（滞后也更明显），中长线趋势跟踪。 */
export const strategy: StrategyModule = {
  id: 'macd-cross',
  name: 'MACD金叉',
  description:
    'DIF 上穿 DEA（金叉）买入，下穿（死叉）卖出。和均线交叉同族，但信号更平滑、假信号更少，代价是滞后更明显——适合中长线趋势，不适合抢反转。',
  params: [
    { key: 'fast', label: '快 EMA 周期', default: 12, min: 5, max: 30, step: 1 },
    { key: 'slow', label: '慢 EMA 周期', default: 26, min: 10, max: 60, step: 1 },
    { key: 'signal', label: '信号线周期', default: 9, min: 3, max: 20, step: 1 },
  ],
  prepare(bars, p) {
    const closes = bars.map((b) => b.c)
    const { dif, dea } = macd(closes, Math.round(p.fast), Math.round(p.slow), Math.round(p.signal))
    return { entries: crossUp(dif, dea), exits: crossDown(dif, dea) }
  },
}
