/**
 * 斜率×R²（Slope × R²）：趋势质量因子。
 *
 * 原理（於三水 ETF 三因子轮动中的 slope 因子，权重 0.3）：
 *   1. 取最近 25 天收盘价，除以窗口第一个价格做归一化
 *   2. 对归一化序列做线性回归，得 slope（斜率）和 r²（拟合优度）
 *   3. 得分 = slope × r² × 10000
 * 斜率反映趋势方向与力度，r² 反映趋势的"干净"程度。
 * 高斜率 + 高 r² = 又强又稳的趋势；高斜率 + 低 r² = 波动大、不稳定。
 *
 * 数学实现见 ../threeFactors.ts（与「横截面轮动」共用同一份因子代码）。
 *
 * 本模块适配为单标的回测策略：
 *   - 买入：slope × r² > 阈值（趋势强且稳定）
 *   - 卖出：slope × r² ≤ 阈值
 */
import { slopeR2Score } from '../threeFactors'
import type { StrategyModule } from '../types'

export const strategy: StrategyModule = {
  id: 'slope-r2',
  name: '趋势质量（斜率×R²）',
  description:
    '对最近 25 天归一化收盘价做线性回归：斜率反映趋势方向与强度，R² 反映趋势稳定性。得分 = 斜率 × R² × 10000。高得分 = 又强又稳的上涨趋势，低得分 = 趋势弱或震荡。出自 ETF 三因子轮动策略，在单边上涨/下跌段信号可靠，震荡市噪声大。',
  params: [
    { key: 'period', label: '观察天数', description: '线性回归窗口天数', default: 25, min: 10, max: 60, step: 5 },
    { key: 'threshold', label: '信号阈值', description: 'slope × R² × 10000 超过此值买入', default: 0, min: -100, max: 100, step: 1 },
  ],
  prepare(bars, p) {
    const score = slopeR2Score(
      bars.map((b) => b.c),
      Math.round(p.period),
    )

    const entries = new Array<boolean>(bars.length).fill(false)
    const exits = new Array<boolean>(bars.length).fill(false)
    for (let i = 0; i < bars.length; i++) {
      if (score[i] == null || !isFinite(score[i]!)) continue
      entries[i] = score[i]! > p.threshold
      exits[i] = score[i]! <= p.threshold
    }
    return { entries, exits }
  },
}