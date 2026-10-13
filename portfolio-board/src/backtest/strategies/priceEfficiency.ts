/**
 * 价格效率比（Price Efficiency Ratio）：趋势的"干净"程度。
 *
 * 原理（於三水 ETF 三因子轮动中的 efficiency 因子，权重 0.4）：
 *   1. 取最近 25 天的 (O+H+L+C)/4 均值价格
 *   2. net_move = log(最后一天 pivot) - log(第一天 pivot)
 *   3. path = sum(|log(pivot_t) - log(pivot_{t-1})|)（全程波动）
 *   4. efficiency = 100 × net_move × |net_move| / path
 * 正值 = 趋势干净（方向明确、路径直接），负值 = 方向与波动反向（趋势混乱）。
 * net_move 的平方符号保留方向但增大高分差距，让干净趋势更突出。
 *
 * 这是 Kaufman (1995) 效率比思想的变体——趋势越"干净"，后续延续概率越高。
 * 原作权重 0.4，是三因子中最重要的。
 *
 * 数学实现见 ../threeFactors.ts（与「横截面轮动」共用同一份因子代码）。
 */
import { efficiencyScore } from '../threeFactors'
import type { StrategyModule } from '../types'

export const strategy: StrategyModule = {
  id: 'price-efficiency',
  name: '价格效率比',
  description:
    '取最近 25 天 (O+H+L+C)/4 均值价，计算 log 净位移 / log 路径和比例。值越大 = 趋势越干净（方向明确、路径直接），值越小 = 趋势混乱震荡。Kaufman 效率比变体，原作权重 0.4 为三因子最高。适合与其他因子拼图组合——只用 efficiency 单因子在趋势市会漏掉启动早期的弱信号。',
  params: [
    { key: 'period', label: '观察窗口', description: '效率比计算天数', default: 25, min: 10, max: 50, step: 5 },
    { key: 'threshold', label: '买入阈值', description: '效率比超过此值买入', default: 0, min: -20, max: 20, step: 0.5 },
    { key: 'exitThreshold', label: '离场阈值', description: '效率比低于此值卖出', default: 0, min: -20, max: 20, step: 0.5 },
  ],
  prepare(bars, p) {
    const eff = efficiencyScore(bars, Math.round(p.period))

    const entries = new Array<boolean>(bars.length).fill(false)
    const exits = new Array<boolean>(bars.length).fill(false)
    for (let i = 0; i < bars.length; i++) {
      if (eff[i] == null || !isFinite(eff[i]!)) continue
      entries[i] = eff[i]! > p.threshold
      exits[i] = eff[i]! <= p.exitThreshold
    }
    return { entries, exits }
  },
}